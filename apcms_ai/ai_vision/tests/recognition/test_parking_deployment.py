# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_parking_deployment.py

"""손상 파일·읽기 전용 볼륨에서 주차 도구의 실패 응답을 확인합니다."""

import io
import copy
import json
import tempfile
import unittest
import contextlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch
import cv2
import numpy as np

from fastapi import HTTPException
from ai_vision.paths import RESULT_DIR
from ai_vision.parking import parking_event_sender as sender
from ai_vision.parking.parking_api import get_parking_occupancy
from ai_vision.parking.space_editor import SpaceEditorHandler
from ai_vision.parking.parking_validation import validate_occupancy, validate_spaces
from ai_vision.parking.parking_processor import ParkingOccupancyProcessor
from ai_vision.parking import parking_realtime
from ai_vision.parking.check_parking_video import run_check as check_video


class ParkingSceneFixture:
    def setUp(self):
        self.reference = np.zeros((80, 80, 3), dtype=np.uint8)
        self.occupied = self.reference.copy()
        self.occupied[10:65, 10:30] = 255
        self.config = {'image_width': 80, 'image_height': 80, 'spaces': [
            {'id': 'A-01', 'points': [[5, 5], [35, 5], [35, 70], [5, 70]]},
            {'id': 'A-02', 'points': [[45, 5], [75, 5], [75, 70], [45, 70]]}]}

    def processor(self, single=False, detector=None, **kwargs):
        config = {**self.config, 'spaces': self.config['spaces'][:1]} if single else self.config
        return ParkingOccupancyProcessor(self.reference, config, detector or parking_realtime.detect_spaces, **kwargs)

    def sequence(self):
        return [self.reference] * 5 + [self.occupied] * 5 + [self.reference] * 5


class ParkingSequenceTests(ParkingSceneFixture, unittest.TestCase):
    def test_confirmed_changes_reach_sender_with_original_event_ids(self):
        # 1. 점유 처리기에서 생성한 이벤트가 변형 없이 Boot 요청에 전달되는지 확인합니다.
        processor = self.processor()
        events = []
        for index, frame in enumerate(self.sequence()):
            events.extend(processor.process(frame, index * .5)['events'])
        base = RESULT_DIR / 'test_tmp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            root = Path(folder)
            backend_states = {}
            def receive(url, *, json, headers, timeout, allow_redirects):
                self.assertTrue(url.endswith('/occupancy-events'))
                self.assertFalse(allow_redirects)
                response = Mock(status_code=200)
                previous = backend_states.get(json['space_code'], 'AVAILABLE')
                backend_states[json['space_code']] = json['status']
                response.json.return_value = {
                    'eventId': json['event_id'], 'spaceCode': json['space_code'],
                    'outcome': 'UNCHANGED' if previous == json['status'] else 'UPDATED',
                    'previousStatus': previous,
                    'currentStatus': json['status'], 'aiDetectionEventId': 1}
                return response
            with patch.object(sender, 'PENDING_PATH', root / 'pending.json'), \
                    patch.object(sender, 'HELD_PATH', root / 'held.json'), \
                    patch.object(sender, 'SEND_ENABLED', True), patch.object(sender, 'API_KEY', 'test-key'), \
                    patch.object(sender.requests, 'post', side_effect=receive) as post, \
                    contextlib.redirect_stdout(io.StringIO()):
                sender.save_pending_events(events)
                results = sender.retry_pending_events()
                self.assertEqual(sender.load_pending_events(), [])
                self.assertEqual(sender.load_event_list(sender.HELD_PATH), [])
            self.assertEqual(len(results), 4)
            self.assertEqual([row['status'] for row in results], ['UNCHANGED', 'UNCHANGED', 'UPDATED', 'UPDATED'])
            self.assertEqual([call.kwargs['json']['event_id'] for call in post.call_args_list],
                             [event['event_id'] for event in events])

    def test_empty_occupied_released_emit_only_confirmed_state_changes(self):
        processor, events = self.processor(), []
        with patch.object(sender.requests, 'post', side_effect=AssertionError('실제 HTTP 금지')):
            for index, frame in enumerate(self.sequence() + [self.reference] * 5):
                events.extend(processor.process(frame, index * .5)['events'])
        self.assertEqual([(event['space_code'], event['status']) for event in events],
                         [('1F-A01', 'AVAILABLE'), ('1F-A02', 'AVAILABLE'),
                          ('1F-A01', 'OCCUPIED'), ('1F-A01', 'AVAILABLE')])
        self.assertEqual(len({event['event_id'] for event in events}), 4)
        self.assertEqual(processor.occupancy()['empty_count'], 2)

    def test_flicker_and_short_intervals_do_not_confirm(self):
        processor = self.processor(single=True)
        for index in range(8):
            result = processor.process(self.reference if index % 2 == 0 else self.occupied, index * .5)
            self.assertEqual(result['events'], [])
        self.assertIsNone(processor.occupancy())
        processor = self.processor(single=True)
        for seconds in (0, .1, .2, .3, .4, .5):
            self.assertFalse(processor.process(self.reference, seconds)['events'])
        self.assertEqual(processor.statistics()['analyzed_frames'], 2)

    def test_long_gap_requires_five_new_observations(self):
        processor = self.processor(single=True)
        for seconds in (0, .5, 1, 1.5, 8, 8.5, 9, 9.5):
            self.assertEqual(processor.process(self.reference, seconds)['events'], [])
        self.assertEqual(len(processor.process(self.reference, 10)['events']), 1)
        self.assertEqual(processor.statistics()['gap_resets'], 1)

    def test_bad_detection_does_not_partially_advance_state(self):
        detector = Mock()
        processor = self.processor(single=True, detector=detector)
        before = copy.deepcopy(processor.states)
        valid = {'space_id': 'A-01', 'status': 'EMPTY', 'change_ratio': 0}
        for results in ([None], [], [valid, valid], [{**valid, 'change_ratio': float('nan')}],
                        [{**valid, 'space_id': 'A-02'}]):
            detector.return_value = results
            with self.assertRaises(ValueError):
                processor.process(self.reference, 0)
            self.assertEqual(processor.states, before)
            self.assertEqual(processor.statistics()['analyzed_frames'], 0)

    def test_bad_frame_and_reverse_clock_are_rejected(self):
        processor = self.processor()
        processor.process(self.reference, 1)
        before = copy.deepcopy(processor.states)
        for frame, seconds in ((self.reference[:40], 2), (self.reference, .5), (self.reference, True)):
            with self.assertRaises(ValueError):
                processor.process(frame, seconds)
        self.assertEqual(processor.states, before)

    def test_scene_resolution_mapping_and_mask_budget_checked_upfront(self):
        for config, budget in (({**self.config, 'image_width': 81}, 64000),
                               ({**self.config, 'spaces': [{'id': 'A-99', 'points': self.config['spaces'][0]['points']}]}, 64000),
                               (self.config, 1)):
            with self.assertRaises(ValueError):
                ParkingOccupancyProcessor(self.reference, config, parking_realtime.detect_spaces, max_mask_bytes=budget)

    def test_legacy_camera_command_delegates_to_canonical_runner(self):
        from ai_vision.parking import run_parking_camera as camera
        arguments = ['--camera-index', '2', '--seconds', '30']
        with patch.object(camera, 'main', return_value=7) as main:
            self.assertEqual(parking_realtime.run_realtime(arguments), 7)
        main.assert_called_once_with(arguments)


class ParkingVideoCheckTests(ParkingSceneFixture, unittest.TestCase):

    def make_inputs(self, frames=None):
        base = RESULT_DIR / 'test_tmp'
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        reference, config, video = root / 'empty.png', root / 'spaces.json', root / 'scene.avi'
        reference.write_bytes(cv2.imencode('.png', self.reference)[1].tobytes())
        config.write_text(json.dumps(self.config), encoding='utf-8')
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 2, (80, 80))
        self.assertTrue(writer.isOpened())
        try:
            for frame in self.sequence() if frames is None else frames:
                writer.write(frame)
        finally:
            writer.release()
        return root, reference, config, video

    def test_video_to_event_dry_run_never_queues_or_posts_even_if_sender_enabled(self):
        root, reference, config, video = self.make_inputs()
        with patch.object(sender, 'SEND_ENABLED', True), \
                patch.object(sender, 'queue_occupancy_event', side_effect=AssertionError('전송 대기 등록 금지')), \
                patch.object(sender.requests, 'post', side_effect=AssertionError('HTTP 금지')):
            report = check_video(reference, config, video, root / 'check')
        self.assertEqual(report['status'], 'COMPLETED')
        self.assertEqual(report['processed_frames'], 15)
        self.assertEqual([event['status'] for event in report['events']], ['AVAILABLE', 'AVAILABLE', 'OCCUPIED', 'AVAILABLE'])
        self.assertEqual(report['http_requests'], 0)
        self.assertTrue(report['dry_run'])
        self.assertTrue((root / 'check' / 'parking_check.json').is_file())

    def test_short_video_remains_incomplete(self):
        root, reference, config, video = self.make_inputs([self.reference] * 4)
        report = check_video(reference, config, video, root / 'check')
        self.assertEqual(report['status'], 'INCOMPLETE')
        self.assertEqual(report['events'], [])
        self.assertIsNone(report['occupancy'])

    def test_existing_output_is_preserved_before_opening_video(self):
        root, reference, config, video = self.make_inputs()
        with patch('ai_vision.parking.check_parking_video.cv2.VideoCapture') as capture:
            with self.assertRaises(ValueError):
                check_video(reference, config, video, root)
        capture.assert_not_called()

    def test_video_resolution_mismatch_saved_as_failure(self):
        root, reference, config, video = self.make_inputs()
        capture = Mock()
        capture.get.return_value = 2
        capture.read.return_value = (True, np.zeros((100, 100, 3), dtype=np.uint8))
        with patch('ai_vision.parking.check_parking_video.cv2.VideoCapture', return_value=capture):
            report = check_video(reference, config, video, root / 'check')
        self.assertEqual(report['status'], 'FAILED')
        self.assertEqual(report['error_type'], 'ValueError')
        self.assertEqual(report['processed_frames'], 0)
        capture.release.assert_called_once()

    def test_invalid_fps_releases_video_without_creating_output(self):
        root, reference, config, video = self.make_inputs()
        capture = Mock()
        capture.get.return_value = 0
        with patch('ai_vision.parking.check_parking_video.cv2.VideoCapture', return_value=capture):
            with self.assertRaises(ValueError):
                check_video(reference, config, video, root / 'check')
        capture.release.assert_called_once()
        self.assertFalse((root / 'check').exists())


class ParkingCameraTests(ParkingSceneFixture, unittest.TestCase):
    def test_formal_backend_option_reaches_camera_and_report(self):
        from ai_vision.parking import run_parking_camera as camera
        root, reference, config = self.inputs()
        capture, preview = Mock(), Mock()
        preview.wait_until_ready.return_value = None
        with patch('ai_vision.camera_runtime.sys.platform', 'win32'), \
                patch.object(camera, 'open_camera', return_value=capture) as open_camera, \
                patch.object(camera, 'ParkingPreview', return_value=preview) as view:
            report = camera.run_camera(reference, config, root / 'session', camera_index=1, camera_backend='msmf')
        open_camera.assert_called_once_with(1, backend='msmf')
        self.assertEqual(report['camera_backend'], 'msmf')
        self.assertEqual(view.call_args.kwargs['source_label'], 'Camera 1 / msmf')
        self.assertEqual(report['http_requests'], 0)

    def test_capture_backend_cli_reaches_capture_function(self):
        from ai_vision.parking import capture_empty_reference as capture
        with patch.object(capture, 'capture_empty_reference') as run:
            self.assertEqual(capture.main(['--camera-index', '1', '--camera-backend', 'msmf',
                                           '--output', 'new.png']), 0)
        self.assertEqual(run.call_args.args[-1], 'msmf')

    def test_canonical_runner_preserves_optional_api_snapshot_output(self):
        from ai_vision.parking import run_parking_camera as camera
        for publish in (False, True):
            with self.subTest(publish=publish):
                root, reference, config = self.inputs()
                capture = Mock()
                capture.read.side_effect = [(True, frame) for frame in self.sequence()] + [(False, None)]
                with patch.object(camera, 'open_camera', return_value=capture), \
                        patch.object(camera.time, 'monotonic', side_effect=[0] + [i * .5 for i in range(40)]), \
                        patch.object(parking_realtime, 'save_results') as save:
                    camera.run_camera(reference, config, root / 'session', preview=False, publish_results=publish)
                self.assertEqual(save.call_count, 3 if publish else 0)

    def inputs(self):
        base = RESULT_DIR / 'test_tmp'
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        reference, config = root / 'empty.png', root / 'spaces.json'
        cv2.imwrite(str(reference), self.reference)
        config.write_text(json.dumps(self.config), encoding='utf-8')
        return root, reference, config

    def test_camera_cancel_has_no_events_and_releases_resources(self):
        from ai_vision.parking import run_parking_camera as camera
        root, reference, config = self.inputs()
        capture, preview = Mock(), Mock()
        preview.wait_until_ready.return_value = None
        with patch.object(camera, 'open_camera', return_value=capture), \
                patch.object(camera, 'ParkingPreview', return_value=preview), \
                patch.object(sender, 'queue_occupancy_event') as queue:
            report = camera.run_camera(reference, config, root / 'check', camera_index=2)
        self.assertEqual(report['status'], 'CANCELLED')
        self.assertEqual(report['http_requests'], 0)
        queue.assert_not_called()
        capture.release.assert_called_once()
        preview.close.assert_called_once()

    def test_camera_sequence_is_dry_run_and_records_confirmed_events(self):
        from ai_vision.parking import run_parking_camera as camera
        root, reference, config = self.inputs()
        capture = Mock()
        capture.read.side_effect = [(True, frame) for frame in self.sequence()] + [(False, None)]
        with patch.object(camera, 'open_camera', return_value=capture), \
                patch.object(camera.time, 'monotonic', side_effect=[0] + [i * .5 for i in range(40)]), \
                patch.object(sender, 'queue_occupancy_event') as queue:
            report = camera.run_camera(reference, config, root / 'check', preview=False)
        self.assertEqual(report['status'], 'FAILED')
        self.assertEqual(report['error_type'], 'OSError')
        self.assertEqual(len(report['events']), 4)
        self.assertEqual(report['occupancy']['empty_count'], 2)
        self.assertEqual(report['http_requests'], 0)
        queue.assert_not_called()
        capture.release.assert_called_once()
        self.assertTrue((root / 'check' / 'parking_camera_check.json').is_file())

    def test_existing_output_rejected_before_opening_camera(self):
        from ai_vision.parking import run_parking_camera as camera
        root, reference, config = self.inputs()
        with patch.object(camera, 'open_camera') as capture:
            with self.assertRaises(ValueError):
                camera.run_camera(reference, config, root)
        capture.assert_not_called()

    def test_measurement_clock_starts_after_manual_preparation(self):
        from ai_vision.parking import run_parking_camera as camera
        root, reference, config = self.inputs()
        capture, preview = Mock(), Mock()
        clock = Mock(side_effect=[100, 101])
        def prepared(_):
            clock.assert_not_called()
            return self.reference
        preview.wait_until_ready.side_effect = prepared
        with patch.object(camera, 'open_camera', return_value=capture), \
                patch.object(camera, 'ParkingPreview', return_value=preview), \
                patch.object(camera.time, 'monotonic', clock):
            report = camera.run_camera(reference, config, root / 'check', seconds=1)
        self.assertEqual(report['status'], 'INCOMPLETE')
        capture.read.assert_not_called()

    def test_preview_rejects_wrong_resolution_before_display(self):
        from ai_vision.parking import parking_preview as preview
        with patch.object(preview, 'require_display'), patch.object(preview.cv2, 'imshow') as show:
            view = preview.ParkingPreview(self.config)
            with self.assertRaises(ValueError):
                view.show(np.zeros((100, 100, 3), dtype=np.uint8), preparing=True)
        show.assert_not_called()

    def test_editor_rejects_existing_coordinates_before_binding(self):
        from ai_vision.parking import space_editor as editor
        _, reference, config = self.inputs()
        with patch.object(editor, 'HTTPServer') as server, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                editor.main(['--image', str(reference), '--output', str(config)])
        server.assert_not_called()

    def test_reference_capture_preserves_existing_file(self):
        from ai_vision.parking import capture_empty_reference as capture
        root, reference, _ = self.inputs()
        original = reference.read_bytes()
        with patch.object(capture, 'open_camera') as camera:
            with self.assertRaises(ValueError):
                capture.capture_empty_reference(output_path=reference)
        camera.assert_not_called()
        self.assertEqual(reference.read_bytes(), original)

    def test_reference_capture_manual_start_and_cancel(self):
        from ai_vision.parking import capture_empty_reference as capture
        root, _, _ = self.inputs()
        for cancelled in (True, False):
            with self.subTest(cancelled=cancelled):
                output = root / f'capture_{cancelled}.png'
                camera, preview = Mock(), Mock()
                preview.wait_until_ready.return_value = None if cancelled else self.reference
                with patch.object(capture, 'open_camera', return_value=camera), \
                        patch.object(capture, 'ParkingPreview', return_value=preview):
                    result = capture.capture_empty_reference(output_path=output)
                self.assertEqual(result, not cancelled)
                self.assertEqual(output.exists(), not cancelled)
                camera.release.assert_called_once()
                preview.close.assert_called_once()


class OccupancyDeliveryTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / 'test_tmp'
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name, value in {'PENDING_PATH': root / 'pending.json', 'HELD_PATH': root / 'held.json',
                            'REJECTED_PATH': root / 'rejected.json', 'SEND_ENABLED': True,
                            'API_KEY': 'test-key'}.items():
            patcher = patch.object(sender, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.event = sender.create_occupancy_event('A-01', 'OCCUPIED', .6)

    def response(self, outcome='UPDATED', **changes):
        row = {'eventId': self.event['event_id'], 'spaceCode': self.event['space_code'],
               'outcome': outcome, 'previousStatus': 'AVAILABLE', 'currentStatus': 'OCCUPIED',
               'aiDetectionEventId': 123}
        row.update(changes)
        response = Mock(status_code=200, text='')
        response.json.return_value = row
        return response

    def deliver(self, response, events=None):
        sender.save_pending_events(events or [self.event])
        with patch.object(sender.requests, 'post', return_value=response) as post, \
                contextlib.redirect_stdout(io.StringIO()):
            result = sender.retry_pending_events()
        return result, post

    def test_completed_occupancy_response_is_removed_once(self):
        result, post = self.deliver(self.response())
        self.assertEqual(result[0]['status'], 'UPDATED')
        self.assertEqual(sender.load_pending_events(), [])
        self.assertEqual(sender.load_event_list(sender.HELD_PATH), [])
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs['json'], self.event)

    def test_unchanged_and_duplicate_are_valid_without_state_change(self):
        for outcome in ('UNCHANGED', 'DUPLICATE'):
            with self.subTest(outcome=outcome):
                result, _ = self.deliver(self.response(outcome, previousStatus='OCCUPIED',
                                                     aiDetectionEventId=None if outcome == 'DUPLICATE' else 123))
                self.assertEqual(result[0]['status'], outcome)
                self.assertEqual(sender.load_pending_events(), [])

    def test_protected_and_old_detection_are_held_without_retry(self):
        for outcome, state in [('SKIPPED_PROTECTED', 'RESERVED'), ('SKIPPED_PROTECTED', 'DISABLED'),
                               ('SKIPPED_BEFORE_CORRECTION', 'AVAILABLE')]:
            with self.subTest(outcome=outcome, state=state):
                result, _ = self.deliver(self.response(outcome, previousStatus=state, currentStatus=state))
                self.assertEqual(result[0]['status'], outcome)
                self.assertEqual(sender.load_pending_events(), [])
                self.assertEqual(sender.load_event_list(sender.HELD_PATH)[-1]['reason'], outcome)
                with patch.object(sender.requests, 'post') as post:
                    self.assertEqual(sender.retry_pending_events(), [])
                post.assert_not_called()

    def test_mismatched_or_malformed_receipts_are_not_success(self):
        variants = [{'eventId': 'different'}, {'spaceCode': '1F-A02'}, {'outcome': 'PROCESSED'},
                    {'currentStatus': 'AVAILABLE'}, {'previousStatus': 'DISABLED'},
                    {'aiDetectionEventId': True}, {'aiDetectionEventId': None},
                    {'outcome': []}, {'previousStatus': []}, {'currentStatus': []}]
        for changes in variants:
            with self.subTest(changes=changes):
                result, _ = self.deliver(self.response(**changes))
                self.assertEqual(result[0]['status'], 'HELD')
                self.assertEqual(sender.load_pending_events(), [])
                self.assertEqual(sender.load_event_list(sender.HELD_PATH)[-1]['reason'], 'INVALID_OCCUPANCY_RESPONSE')

    def test_invalid_receipt_stops_before_sending_next_event(self):
        second = sender.create_occupancy_event('A-02', 'EMPTY', .01)
        _, post = self.deliver(self.response(eventId='different'), [self.event, second])
        self.assertEqual(post.call_count, 1)
        self.assertEqual(sender.load_pending_events(), [second])

    def test_http_conflict_is_rejected_and_timeout_preserves_original_id(self):
        result, _ = self.deliver(Mock(status_code=409, text='conflict'))
        self.assertEqual(result[0]['status'], 'REJECTED')
        self.assertEqual(sender.load_event_list(sender.REJECTED_PATH)[0]['event'], self.event)
        sender.save_pending_events([self.event])
        with patch.object(sender.requests, 'post', side_effect=sender.requests.ReadTimeout()), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sender.retry_pending_events(), [])
        self.assertEqual(sender.load_pending_events(), [self.event])

    def loopback(self, mode='UPDATED'):
        # 1. 실제 requests 전송을 임시 로컬 서버로 연결하고 운영 파일은 사용하지 않습니다.
        received = []
        unblock = threading.Event()
        event = self.event
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append({'path': self.path, 'event': body,
                                 'key_matches': self.headers.get('X-AI-API-Key') == 'test-key'})
                if mode == 'TIMEOUT':
                    unblock.wait(2)
                if mode == 'REDIRECT':
                    self.send_response(307)
                    self.send_header('Location', '/unexpected-target')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                state = 'RESERVED' if mode == 'SKIPPED_PROTECTED' else 'AVAILABLE'
                data = {'eventId': body['event_id'], 'spaceCode': body['space_code'],
                        'outcome': mode, 'previousStatus': state,
                        'currentStatus': 'OCCUPIED' if mode == 'UPDATED' else state,
                        'aiDetectionEventId': None if mode == 'DUPLICATE' else 123}
                if mode == 'MISMATCH':
                    data.update(eventId='different', outcome='UPDATED', currentStatus='OCCUPIED')
                raw = b'not-json' if mode == 'INVALID_JSON' else json.dumps(data).encode('utf-8')
                try:
                    self.send_response(409 if mode == 'CONFLICT' else 200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        actual_post = sender.requests.post
        def post(url, **kwargs):
            # 2. 시간 제한만 줄이고 HTTP 직렬화·헤더·응답 처리는 실제 라이브러리를 사용합니다.
            kwargs['timeout'] = (1, .1 if mode == 'TIMEOUT' else 2)
            return actual_post(url, **kwargs)
        try:
            sender.save_pending_events([event])
            with patch.dict(sender.API_URLS, {'PARKING_OCCUPANCY':
                    f'http://127.0.0.1:{server.server_port}/alpharking/admin/api/parking/ai/occupancy-events'}), \
                    patch.object(sender.requests, 'post', side_effect=post), \
                    contextlib.redirect_stdout(io.StringIO()):
                results = sender.retry_pending_events()
            return results, received
        finally:
            unblock.set()
            server.shutdown()
            server.server_close()
            thread.join(2)

    def test_real_http_occupancy_payload_and_receipt(self):
        results, received = self.loopback()
        self.assertEqual(results[0]['status'], 'UPDATED')
        self.assertEqual(len(received), 1)
        self.assertTrue(received[0]['key_matches'])
        self.assertEqual(received[0]['path'], '/alpharking/admin/api/parking/ai/occupancy-events')
        self.assertEqual(received[0]['event'], self.event)
        self.assertEqual(sender.load_pending_events(), [])

    def test_real_http_duplicate_and_skipped_receipts(self):
        for outcome in ('DUPLICATE', 'SKIPPED_PROTECTED', 'SKIPPED_BEFORE_CORRECTION'):
            with self.subTest(outcome=outcome):
                results, received = self.loopback(outcome)
                self.assertEqual(results[0]['status'], outcome)
                self.assertEqual(len(received), 1)
                self.assertEqual(sender.load_pending_events(), [])

    def test_real_http_invalid_receipt_is_held(self):
        for mode in ('MISMATCH', 'INVALID_JSON'):
            with self.subTest(mode=mode):
                results, received = self.loopback(mode)
                self.assertEqual(results[0]['status'], 'HELD')
                self.assertEqual(len(received), 1)
                self.assertEqual(sender.load_pending_events(), [])

    def test_real_http_timeout_retains_exact_original_event(self):
        results, received = self.loopback('TIMEOUT')
        self.assertEqual(results, [])
        self.assertEqual(len(received), 1)
        self.assertEqual(sender.load_pending_events(), [self.event])

    def test_real_http_redirect_is_not_followed(self):
        results, received = self.loopback('REDIRECT')
        self.assertEqual(results, [])
        self.assertEqual(len(received), 1)
        self.assertEqual(sender.load_pending_events(), [self.event])

    def test_real_http_conflict_is_rejected(self):
        results, received = self.loopback('CONFLICT')
        self.assertEqual(results[0]['status'], 'REJECTED')
        self.assertEqual(len(received), 1)
        self.assertEqual(sender.load_pending_events(), [])


class ParkingOperationalTests(ParkingSceneFixture, unittest.TestCase):
    def test_interrupt_during_http_is_not_a_clean_user_stop(self):
        from ai_vision.parking import run_parking_camera as camera
        base = RESULT_DIR / 'test_tmp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            capture = Mock()
            capture.read.return_value = (True, self.reference)
            client = self.client()
            with patch.object(camera, 'read_json', return_value=self.config), \
                    patch.object(camera, 'load_reference', return_value=self.reference), \
                    patch.object(camera, 'open_camera', return_value=capture), \
                    patch.object(camera, 'ParkingDelivery', return_value=client), \
                    patch.object(client.session, 'post', side_effect=KeyboardInterrupt), \
                    patch.object(camera.time, 'monotonic', side_effect=[0] + [i * .5 for i in range(50)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                report = camera.run_camera('empty.png', 'spaces.json', Path(folder) / 'session', preview=False,
                                           enable_http=True, allowed_codes=['1F-A01'],
                                           environment={'AI_OCCUPANCY_API_KEY': 'secret'})
            self.assertEqual(report['status'], 'DELIVERY_STOPPED')
            self.assertEqual(report['deliveries'][0]['status'], 'DELIVERY_UNKNOWN')
            self.assertEqual(report['http_requests'], 1)
            capture.release.assert_called_once()

    def test_live_camera_stops_on_uncertain_delivery_and_saves_report(self):
        from ai_vision.parking import run_parking_camera as camera
        base = RESULT_DIR / 'test_tmp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            root = Path(folder)
            capture = Mock()
            capture.read.return_value = (True, self.reference)
            client = self.client()
            with patch.object(camera, 'read_json', return_value=self.config), \
                    patch.object(camera, 'load_reference', return_value=self.reference), \
                    patch.object(camera, 'open_camera', return_value=capture), \
                    patch.object(camera, 'ParkingDelivery', return_value=client), \
                    patch.object(client.session, 'post', side_effect=sender.requests.ReadTimeout()) as post, \
                    patch.object(camera.time, 'monotonic', side_effect=[0] + [i * .5 for i in range(50)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                report = camera.run_camera('empty.png', 'spaces.json', root / 'session', preview=False,
                                           enable_http=True, allowed_codes=['1F-A01'],
                                           environment={'AI_OCCUPANCY_API_KEY': 'secret'})
            self.assertEqual(report['status'], 'DELIVERY_STOPPED')
            self.assertEqual(report['http_requests'], 1)
            self.assertEqual(report['deliveries'][0]['status'], 'DELIVERY_UNKNOWN')
            self.assertEqual(post.call_count, 1)
            capture.release.assert_called_once()
            saved = json.loads((root / 'session' / 'parking_camera_check.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['status'], 'DELIVERY_STOPPED')
            self.assertFalse(saved['dry_run'])

    def test_response_size_and_redirect_are_never_success(self):
        for status, chunks in [(307, []), (200, [b'x' * 65537]), (200, [b'{}'])]:
            with self.subTest(status=status, size=sum(map(len, chunks))):
                client = self.client()
                response = Mock(status_code=status)
                response.iter_content.return_value = chunks
                context = Mock()
                context.__enter__ = Mock(return_value=response)
                context.__exit__ = Mock(return_value=False)
                with patch.object(client.session, 'post', return_value=context):
                    result = client.send(sender.create_occupancy_event('A-01', 'EMPTY', 0))
                self.assertEqual(result['status'], 'DELIVERY_UNKNOWN')
                self.assertTrue(client.blocked)

    def test_preflight_requires_explicit_mode_key_and_configured_spaces(self):
        from ai_vision.parking.parking_delivery import delivery_settings
        env = {'AI_OCCUPANCY_API_KEY': 'secret', 'PARKING_AI_SEND_ENABLED': 'true'}
        self.assertIsNone(delivery_settings(self.config, False, [], env))
        for enabled, codes, environment in [(True, [], env), (True, ['1F-A04'], env),
                                             (True, ['1F-A01'], {}), (False, ['1F-A01'], env)]:
            with self.subTest(codes=codes, enabled=enabled), self.assertRaises(ValueError):
                delivery_settings(self.config, enabled, codes, environment)
        settings = delivery_settings(self.config, True, ['1F-A01'], env)
        self.assertEqual(settings['allowed_codes'], frozenset({'1F-A01'}))
        self.assertTrue(settings['url'].endswith('/occupancy-events'))

    def client(self):
        from ai_vision.parking.parking_delivery import ParkingDelivery
        client = ParkingDelivery({'url': 'http://127.0.0.1:81/events', 'key': 'secret',
                                  'allowed_codes': frozenset({'1F-A01'})})
        self.addCleanup(client.close)
        return client

    def test_delivery_forbidden_space_makes_no_http_request(self):
        client = self.client()
        with patch.object(client.session, 'post') as post:
            result = client.send(sender.create_occupancy_event('A-02', 'EMPTY', 0))
        self.assertEqual(result['status'], 'NOT_ALLOWED')
        post.assert_not_called()

    def test_delivery_timeout_stops_and_never_retries(self):
        client = self.client()
        event = sender.create_occupancy_event('A-01', 'EMPTY', 0)
        with patch.object(client.session, 'post', side_effect=sender.requests.ReadTimeout()) as post:
            result = client.send(event)
            with self.assertRaises(RuntimeError):
                client.send(event)
        self.assertEqual(result['status'], 'DELIVERY_UNKNOWN')
        self.assertTrue(client.blocked)
        self.assertEqual(post.call_count, 1)

    def test_delivery_validates_real_response_contract(self):
        client = self.client()
        event = sender.create_occupancy_event('A-01', 'OCCUPIED', .6)
        body = {'eventId': event['event_id'], 'spaceCode': '1F-A01', 'outcome': 'UPDATED',
                'previousStatus': 'AVAILABLE', 'currentStatus': 'OCCUPIED', 'aiDetectionEventId': 1}
        response = Mock(status_code=200)
        response.iter_content.return_value = [json.dumps(body).encode()]
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        with patch.object(client.session, 'post', return_value=context) as post:
            result = client.send(event)
        self.assertEqual(result['status'], 'UPDATED')
        self.assertFalse(client.blocked)
        self.assertFalse(post.call_args.kwargs['allow_redirects'])
        self.assertFalse(client.session.trust_env)

    def test_report_persists_intent_before_request_without_secret(self):
        from ai_vision.parking.inspect_parking_camera import deliver_changes
        base = RESULT_DIR / 'test_tmp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            root = Path(folder)
            event = sender.create_occupancy_event('A-01', 'EMPTY', 0)
            client = self.client()
            report = {'deliveries': [], 'http_requests': 0, 'status': 'RUNNING'}
            def send(value):
                saved = json.loads((root / 'parking_camera_check.json').read_text(encoding='utf-8'))
                self.assertEqual(saved['deliveries'][0]['status'], 'IN_FLIGHT')
                client.attempts = 1
                client.blocked = True
                return {'event_id': value['event_id'], 'status': 'DELIVERY_UNKNOWN'}
            with patch.object(client, 'send', side_effect=send):
                self.assertFalse(deliver_changes(root, report, self.processor(), client, [event, event]))
            self.assertEqual(len(report['deliveries']), 1)
            self.assertEqual(report['status'], 'DELIVERY_STOPPED')
            self.assertNotIn('secret', (root / 'parking_camera_check.json').read_text(encoding='utf-8'))

    def test_camera_rejects_invalid_live_settings_before_camera_open(self):
        from ai_vision.parking import run_parking_camera as camera
        with patch.object(camera, 'read_json', return_value=self.config), \
                patch.object(camera, 'load_reference', return_value=self.reference), \
                patch.object(camera, 'open_camera') as capture:
            with self.assertRaises(ValueError):
                camera.run_camera('empty.png', 'spaces.json', RESULT_DIR / 'unused_live_test',
                                  enable_http=True, environment={})
        capture.assert_not_called()


class ParkingReportRecoveryTests(unittest.TestCase):
    def test_live_event_without_receipt_requires_review_even_after_stop(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        self.save(status='STOPPED')
        summary = inspect_report(self.path)
        self.assertTrue(summary['requires_review'])
        self.assertEqual(summary['unrecorded_count'], 1)

    def test_failed_intent_write_prevents_http_call(self):
        from ai_vision.parking.inspect_parking_camera import deliver_changes
        delivery = Mock(settings={'allowed_codes': {'1F-A01'}})
        event = sender.create_occupancy_event('A-01', 'EMPTY', 0)
        report = {'deliveries': []}
        with patch('ai_vision.parking.inspect_parking_camera.checkpoint', side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                deliver_changes(Path('.'), report, Mock(), delivery, [event])
        delivery.send.assert_not_called()

    def test_failure_to_save_receipt_keeps_durable_in_flight_record(self):
        from ai_vision.parking import inspect_parking_camera as reports
        event = sender.create_occupancy_event('A-01', 'EMPTY', 0)
        delivery = Mock(settings={'allowed_codes': {'1F-A01'}}, attempts=0)
        delivery.send.return_value = {'event_id': event['event_id'], 'status': 'UPDATED'}
        durable = []
        def save(folder, report, processor, client):
            if durable:
                raise OSError('storage unavailable')
            durable.append(copy.deepcopy(report))
        with patch.object(reports, 'checkpoint', side_effect=save):
            with self.assertRaises(OSError):
                reports.deliver_changes(Path('.'), {'deliveries': []}, Mock(), delivery, [event])
        self.assertEqual(durable[0]['deliveries'][0]['status'], 'IN_FLIGHT')
        delivery.send.assert_called_once()

    def setUp(self):
        base = RESULT_DIR / 'test_tmp'
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'report.json'

    def save(self, status='STOPPED', receipt=None, dry_run=False):
        event = sender.create_occupancy_event('A-01', 'EMPTY', 0)
        report = {'status': status, 'dry_run': dry_run, 'http_requests': 0 if dry_run else 1,
                  'events': [event], 'deliveries': [] if receipt is None else [
                      {'event_id': event['event_id'], 'status': receipt}]}
        self.path.write_text(json.dumps(report), encoding='utf-8')
        return report

    def test_unknown_delivery_remains_review_required_after_user_stop(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        self.save(receipt='IN_FLIGHT')
        summary = inspect_report(self.path)
        self.assertTrue(summary['requires_review'])
        self.assertEqual(summary['uncertain_count'], 1)

    def test_interrupted_live_report_is_not_reported_as_clean(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        self.save(status='RUNNING')
        self.assertTrue(inspect_report(self.path)['requires_review'])

    def test_completed_live_receipt_and_dry_run_need_no_delivery_review(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        self.save(status='COMPLETED', receipt='UPDATED')
        self.assertFalse(inspect_report(self.path)['requires_review'])
        self.save(status='COMPLETED', dry_run=True)
        self.assertFalse(inspect_report(self.path)['requires_review'])

    def test_skipped_and_rejected_receipts_require_operator_review(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        for receipt in ('SKIPPED_PROTECTED', 'SKIPPED_BEFORE_CORRECTION', 'REJECTED'):
            with self.subTest(receipt=receipt):
                self.save(receipt=receipt)
                self.assertTrue(inspect_report(self.path)['requires_review'])

    def test_queued_cancelled_and_overflow_records_require_review(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        for receipt in ('QUEUED', 'CANCELLED_BEFORE_SEND', 'NOT_SENT_QUEUE_FULL'):
            with self.subTest(receipt=receipt):
                self.save(receipt=receipt)
                self.assertTrue(inspect_report(self.path)['requires_review'])

    def test_report_rejects_broken_links_duplicates_and_fake_dry_run(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        for variant in ('broken_link', 'duplicate', 'fake_dry_run', 'invalid_status'):
            report = self.save(receipt='UPDATED')
            if variant == 'broken_link':
                report['deliveries'][0]['event_id'] = 'different'
            elif variant == 'duplicate':
                report['deliveries'] *= 2
            elif variant == 'fake_dry_run':
                report['dry_run'] = True
            else:
                report['status'] = []
            self.path.write_text(json.dumps(report), encoding='utf-8')
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                inspect_report(self.path)

    def test_previous_uncertain_report_blocks_new_live_session(self):
        from ai_vision.parking.parking_delivery import check_previous_report
        self.save(receipt='DELIVERY_UNKNOWN')
        with self.assertRaises(ValueError):
            check_previous_report(self.path, True)
        check_previous_report(self.path, False)

    def test_inspector_exit_codes_and_missing_report(self):
        from ai_vision.parking.inspect_parking_camera import main
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(self.path)]), 1)
            self.save(receipt='IN_FLIGHT')
            self.assertEqual(main([str(self.path)]), 2)
            self.save(receipt='UPDATED')
            self.assertEqual(main([str(self.path)]), 0)


class ParkingCalibrationTests(ParkingSceneFixture, unittest.TestCase):
    def test_result_image_failure_does_not_publish_new_json(self):
        processor = self.processor()
        for index in range(5):
            processor.process(self.reference, index * .5)
        with patch.object(parking_realtime, 'SAVE_DIR', self.root), \
                patch.object(parking_realtime.cv2, 'imencode', return_value=(False, None)), \
                patch.object(parking_realtime, 'write_json_atomic') as write:
            with self.assertRaises(OSError):
                parking_realtime.save_results(self.reference, processor.spaces, processor.confirmed_results())
        write.assert_not_called()

    def test_result_snapshot_supports_korean_image_path(self):
        processor = self.processor()
        for index in range(5):
            processor.process(self.reference, index * .5)
        image, output = self.root / '점유 결과.jpg', self.root / '점유 결과.json'
        with patch.object(parking_realtime, 'SAVE_DIR', self.root), \
                patch.object(parking_realtime, 'IMAGE_PATH', image), \
                patch.object(parking_realtime, 'OUTPUT_PATH', output), contextlib.redirect_stdout(io.StringIO()):
            parking_realtime.save_results(self.reference, processor.spaces, processor.confirmed_results())
        self.assertGreater(image.stat().st_size, 0)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['empty_count'], 2)

    def setUp(self):
        super().setUp()
        base = RESULT_DIR / 'test_tmp'
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.image = self.root / '빈 주차면.png'
        ok, encoded = cv2.imencode('.png', self.reference)
        self.assertTrue(ok)
        self.image.write_bytes(encoded.tobytes())

    def test_shared_loader_reads_korean_path_without_resizing(self):
        from ai_vision.parking.parking_calibration import load_reference
        actual = load_reference(self.image, self.config)
        np.testing.assert_array_equal(actual, self.reference)

    def test_invalid_image_and_wrong_dimensions_fail_before_opencv_decode(self):
        from ai_vision.parking import parking_calibration as calibration
        with patch.object(calibration.cv2, 'imdecode') as decode:
            with self.assertRaises(ValueError):
                calibration.load_reference(self.image, {**self.config, 'image_width': 81})
            self.image.write_bytes(b'not an image')
            with self.assertRaises(ValueError):
                calibration.load_reference(self.image)
        decode.assert_not_called()

    def test_compressed_image_and_pixel_limits_are_checked_upfront(self):
        from ai_vision.parking import parking_calibration as calibration
        with patch.object(calibration, 'MAX_IMAGE_BYTES', 16):
            with self.assertRaises(ValueError):
                calibration.load_reference(self.image)
        for width, height in ((True, 480), (0, 480), (8192, 8192)):
            with self.subTest(width=width, height=height), self.assertRaises(ValueError):
                calibration.validate_resolution(width, height)

    def test_resolution_request_checks_actual_frame_separately(self):
        from ai_vision.parking.parking_calibration import configure_resolution, validate_frame_resolution
        capture = Mock()
        configure_resolution(capture, 80, 80)
        self.assertEqual(capture.set.call_count, 2)
        validate_frame_resolution(self.reference, 80, 80)
        with self.assertRaises(ValueError):
            validate_frame_resolution(self.reference, 640, 480)

    def test_reference_capture_rejects_driver_resolution_fallback(self):
        from ai_vision.parking import capture_empty_reference as capture
        preview, camera = Mock(), Mock()
        preview.wait_until_ready.return_value = self.reference
        output = self.root / 'new.png'
        with patch.object(capture, 'ParkingPreview', return_value=preview), \
                patch.object(capture, 'open_camera', return_value=camera):
            with self.assertRaises(ValueError):
                capture.capture_empty_reference(output_path=output, width=640, height=480)
        self.assertFalse(output.exists())
        camera.release.assert_called_once()
        preview.close.assert_called_once()

    def test_reference_capture_requires_width_height_pair_before_open(self):
        from ai_vision.parking import capture_empty_reference as capture
        with patch.object(capture, 'open_camera') as camera:
            with self.assertRaises(ValueError):
                capture.capture_empty_reference(output_path=self.root / 'new.png', width=640)
        camera.assert_not_called()

    def test_editor_rejects_dimensions_different_from_displayed_image(self):
        from types import SimpleNamespace
        payload = json.dumps(self.config).encode()
        handler = object.__new__(SpaceEditorHandler)
        handler.path, handler.headers = '/save', {'Content-Length': str(len(payload))}
        handler.rfile, handler.wfile = io.BytesIO(payload), io.BytesIO()
        handler.server = SimpleNamespace(image_dimensions=(640, 480), save_path=self.root / 'spaces.json')
        handler.send_response, handler.send_header, handler.end_headers = Mock(), Mock(), Mock()
        handler.do_POST()
        handler.send_response.assert_called_once_with(400)
        self.assertFalse(handler.server.save_path.exists())

    def test_editor_rejects_corrupt_image_before_starting_server(self):
        from ai_vision.parking import space_editor as editor
        self.image.write_bytes(b'corrupt')
        with patch.object(editor, 'HTTPServer') as server, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                editor.main(['--image', str(self.image), '--output', str(self.root / 'spaces.json')])
        server.assert_not_called()


class ParkingDeploymentTests(unittest.TestCase):
    def test_event_urls_accept_origin_context_and_ai_root_without_duplicate_paths(self):
        expected = 'http://localhost:81/alpharking/admin/api/parking/ai'
        for base in ('http://localhost:81', 'http://localhost:81/',
                     'http://localhost:81/alpharking/admin/', expected + '/'):
            with self.subTest(base=base):
                urls = sender._build_event_urls(base)
                self.assertEqual(urls['PARKING_OCCUPANCY'], expected + '/occupancy-events')
                self.assertEqual(urls['VEHICLE_PASSAGE'], expected + '/vehicle-events')
                self.assertEqual(urls['VEHICLE_SPACE_MATCH'], expected + '/space-match-events')

    def test_custom_context_and_occupancy_override_remain_separate(self):
        urls = sender._build_event_urls('https://boot.example/custom-admin', 'https://occupancy.example/events')
        self.assertEqual(urls['VEHICLE_PASSAGE'], 'https://boot.example/custom-admin/api/parking/ai/vehicle-events')
        self.assertEqual(urls['PARKING_OCCUPANCY'], 'https://occupancy.example/events')
        self.assertEqual(sender._build_event_urls('http://localhost:81', 'https://occupancy.example/events/')['PARKING_OCCUPANCY'],
                         'https://occupancy.example/events/')

    def test_unsafe_urls_rejected_without_network(self):
        with patch.object(sender.requests, 'post') as post:
            for value in ('', 'file:///tmp/events', 'http://user:secret@localhost',
                          'http://localhost?key=x', 'http://localhost#', 'http://localhost:bad',
                          'http://localhost:70000', 'http://localhost:0', 'http://local host'):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    sender._build_event_urls(value)
            with self.assertRaises(ValueError):
                sender._build_event_urls('http://localhost:81', 'http://user:secret@localhost/events')
        post.assert_not_called()

    def test_event_key_priority_and_empty_legacy_key_fallback(self):
        self.assertEqual(sender._configured_api_key({'PARKING_AI_API_KEY': 'old-key', 'AI_OCCUPANCY_API_KEY': 'shared-key'}), 'old-key')
        self.assertEqual(sender._configured_api_key({'PARKING_AI_API_KEY': '', 'AI_OCCUPANCY_API_KEY': 'shared-key'}), 'shared-key')
        self.assertEqual(sender._configured_api_key({'AI_OCCUPANCY_API_KEY': 'shared-key'}), 'shared-key')
        self.assertEqual(sender._configured_api_key({}), '')

    def test_invalid_counts_states_and_duplicate_ids_are_rejected(self):
        valid = {"total_spaces": 1, "occupied_count": 1, "empty_count": 0,
                 "spaces": [{"space_id": "A", "status": "OCCUPIED", "change_ratio": .5}]}
        self.assertIs(validate_occupancy(valid), valid)
        for change in ({"occupied_count": True}, {"empty_count": 1}, {"spaces": [None]},
                       {"spaces": [{"space_id": "A", "status": "UNKNOWN", "change_ratio": .5}]},
                       {"spaces": [{"space_id": "A", "status": "OCCUPIED", "change_ratio": float("nan")}]},
                       {"total_spaces": 2, "occupied_count": 2, "spaces": valid["spaces"] * 2}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_occupancy({**valid, **change})

    def test_invalid_coordinate_shapes_and_ids_are_rejected(self):
        valid = {"image_width": 10, "image_height": 10,
                 "spaces": [{"id": "A", "points": [[0, 0], [9, 0], [9, 9], [0, 9]]}]}
        self.assertIs(validate_spaces(valid), valid)
        variants = [{**valid, "image_width": True}, {**valid, "spaces": []},
                    {**valid, "spaces": valid["spaces"] * 2}, {**valid, "spaces": [None]}]
        for points in ([[0, 0]] * 4, [[0, 0], [1, 1], [2, 2], [3, 3]],
                       [[0, 0], [11, 0], [9, 9], [0, 9]], [[0, 0], [9.5, 0], [9, 9], [0, 9]]):
            row = copy.deepcopy(valid)
            row["spaces"][0]["points"] = points
            variants.append(row)
        for row in variants:
            with self.subTest(row=row), self.assertRaises(ValueError):
                validate_spaces(row)

    def test_structurally_invalid_json_result_is_service_unavailable(self):
        self.path.write_text('{"total_spaces":1,"occupied_count":0,"empty_count":0,"spaces":[]}', encoding="utf-8")
        with self.assertRaises(HTTPException) as caught:
            get_parking_occupancy()
        self.assertEqual(caught.exception.status_code, 503)

    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "result.json"
        patcher = patch("ai_vision.parking.parking_api.RESULT_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_valid_result_is_returned_without_changes(self):
        value = {"total_spaces": 0, "occupied_count": 0, "empty_count": 0, "spaces": []}
        self.path.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(get_parking_occupancy(), value)

    def test_missing_corrupt_and_nonfinite_results_are_service_unavailable(self):
        for content in (None, b"\xff", b'{"total": NaN}', b'{"total":1,"total":2}', b"[]", b"{"):
            if content is not None:
                self.path.write_bytes(content)
            with self.subTest(content=content), self.assertRaises(HTTPException) as caught:
                get_parking_occupancy()
            self.assertEqual(caught.exception.status_code, 503)

    def test_read_permission_failure_is_service_unavailable(self):
        with patch("ai_vision.parking.parking_api.read_json", side_effect=PermissionError("private-path")):
            with self.assertRaises(HTTPException) as caught:
                get_parking_occupancy()
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn("private-path", caught.exception.detail)

    def test_editor_write_permission_failure_returns_response(self):
        payload = json.dumps({"image_width": 10, "image_height": 10,
                              "spaces": [{"id": "A", "points": [[0, 0], [9, 0], [9, 9], [0, 9]]}]}).encode()
        handler = object.__new__(SpaceEditorHandler)
        handler.path, handler.headers = "/save", {"Content-Length": str(len(payload))}
        handler.rfile, handler.wfile = io.BytesIO(payload), io.BytesIO()
        handler.send_response, handler.send_header, handler.end_headers = Mock(), Mock(), Mock()
        with patch("ai_vision.parking.space_editor.write_json_atomic", side_effect=PermissionError):
            handler.do_POST()
        handler.send_response.assert_called_once_with(503)
        self.assertEqual(json.loads(handler.wfile.getvalue()), {"success": False})

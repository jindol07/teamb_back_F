# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_parking_delivery_worker.py
"""느린 점유 전송 중 프레임 처리·순서·중단·저장 실패를 확인합니다."""

import contextlib
import io
import itertools
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from ai_vision.paths import RESULT_DIR
from ai_vision.parking.parking_delivery import ParkingDelivery, ParkingDeliveryWorker
from ai_vision.parking.parking_event_sender import create_occupancy_event
from ai_vision.parking import run_parking_camera as camera


class SlowClient:
    def __init__(self, failure=False):
        self.settings = {'allowed_codes': {'1F-A01'}}
        self.blocked = False
        self.attempts = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = []
        self.failure = failure

    def send(self, event):
        self.calls.append(event['event_id'])
        self.attempts += 1
        self.started.set()
        if not self.release.wait(3):
            raise TimeoutError('검사에서 응답을 해제하지 않았습니다.')
        self.blocked = self.failure
        return {'event_id': event['event_id'], 'status': 'DELIVERY_UNKNOWN' if self.failure else 'UPDATED'}

    def close(self):
        pass


class ParkingDeliveryWorkerTests(unittest.TestCase):
    def setup_worker(self, limit=8, failure=False):
        client = SlowClient(failure)
        worker = ParkingDeliveryWorker(client, limit)
        self.addCleanup(worker.close)
        self.addCleanup(client.release.set)
        return client, worker

    def item(self, identifier):
        return {'event_id': identifier}, {'event_id': identifier, 'status': 'QUEUED'}

    def test_slow_request_does_not_block_main_processing(self):
        client, worker = self.setup_worker()
        event, receipt = self.item('first')
        self.assertTrue(worker.enqueue(event, receipt))
        worker.poll(lambda: None)
        self.assertTrue(client.started.wait(1))
        processed = 0
        for _ in range(100):
            self.assertTrue(worker.poll(lambda: None))
            processed += 1
        self.assertEqual(processed, 100)
        self.assertEqual(receipt['status'], 'IN_FLIGHT')
        self.assertEqual(worker.pending, 1)
        client.release.set()
        worker.future.result(timeout=2)
        worker.poll(lambda: None)
        self.assertEqual(receipt['status'], 'UPDATED')

    def test_requests_keep_order_and_next_send_requires_main_poll(self):
        client, worker = self.setup_worker()
        first, receipt1 = self.item('first')
        second, receipt2 = self.item('second')
        worker.enqueue(first, receipt1)
        worker.enqueue(second, receipt2)
        worker.poll(lambda: None)
        self.assertTrue(client.started.wait(1))
        client.release.set()
        worker.future.result(timeout=2)
        self.assertEqual(client.calls, ['first'])
        worker.poll(lambda: None)
        worker.future.result(timeout=2)
        worker.poll(lambda: None)
        self.assertEqual(client.calls, ['first', 'second'])
        self.assertEqual([receipt1['status'], receipt2['status']], ['UPDATED', 'UPDATED'])

    def test_unknown_result_cancels_remaining_events_without_retry(self):
        client, worker = self.setup_worker(failure=True)
        first, receipt1 = self.item('first')
        second, receipt2 = self.item('second')
        worker.enqueue(first, receipt1)
        worker.enqueue(second, receipt2)
        worker.poll(lambda: None)
        client.release.set()
        worker.future.result(timeout=2)
        self.assertFalse(worker.poll(lambda: None))
        self.assertEqual(client.calls, ['first'])
        self.assertEqual(receipt2['status'], 'CANCELLED_BEFORE_SEND')

    def test_close_finishes_started_request_but_cancels_unsent_event(self):
        client, worker = self.setup_worker()
        first, receipt1 = self.item('first')
        second, receipt2 = self.item('second')
        worker.enqueue(first, receipt1)
        worker.enqueue(second, receipt2)
        worker.poll(lambda: None)
        client.release.set()
        worker.close()
        self.assertEqual(client.calls, ['first'])
        self.assertEqual(receipt1['status'], 'UPDATED')
        self.assertEqual(receipt2['status'], 'CANCELLED_BEFORE_SEND')

    def test_pending_bound_includes_active_request(self):
        client, worker = self.setup_worker(limit=2)
        worker.enqueue(*self.item('first'))
        worker.poll(lambda: None)
        self.assertTrue(client.started.wait(1))
        self.assertTrue(worker.enqueue(*self.item('second')))
        self.assertFalse(worker.enqueue(*self.item('third')))
        self.assertTrue(worker.blocked)
        self.assertEqual(worker.pending, 2)

    def test_closed_worker_does_not_accept_new_event(self):
        _, worker = self.setup_worker()
        worker.close()
        with self.assertRaises(RuntimeError):
            worker.enqueue(*self.item('late'))

    def test_failed_intent_save_prevents_worker_submission(self):
        client, worker = self.setup_worker()
        worker.enqueue(*self.item('first'))
        with self.assertRaises(PermissionError):
            worker.poll(Mock(side_effect=PermissionError))
        self.assertEqual(client.calls, [])
        self.assertIsNone(worker.future)

    def test_real_http_wait_does_not_hold_main_loop(self):
        received, release = threading.Event(), threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                event = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.set()
                release.wait(3)
                body = json.dumps({'eventId': event['event_id'], 'spaceCode': event['space_code'],
                                   'outcome': 'UPDATED', 'previousStatus': 'AVAILABLE',
                                   'currentStatus': 'OCCUPIED', 'aiDetectionEventId': 1}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client = ParkingDelivery({'url': f'http://127.0.0.1:{server.server_port}/events',
                                  'key': 'TEST_ONLY', 'allowed_codes': {'1F-A01'}})
        worker = ParkingDeliveryWorker(client)
        try:
            event = create_occupancy_event('A-01', 'OCCUPIED', .8)
            receipt = {'event_id': event['event_id'], 'status': 'QUEUED'}
            worker.enqueue(event, receipt)
            worker.poll(lambda: None)
            self.assertTrue(received.wait(2))
            for _ in range(20):
                self.assertTrue(worker.poll(lambda: None))
            self.assertEqual(receipt['status'], 'IN_FLIGHT')
            release.set()
            worker.future.result(timeout=2)
            worker.poll(lambda: None)
            self.assertEqual(receipt['status'], 'UPDATED')
        finally:
            release.set()
            worker.close()
            client.close()
            server.shutdown()
            server.server_close()
            thread.join(2)

    def test_camera_keeps_reading_and_closes_before_waiting_for_http(self):
        reference = np.zeros((80, 80, 3), dtype=np.uint8)
        config = {'image_width': 80, 'image_height': 80, 'spaces': [
            {'id': 'A-01', 'points': [[5, 5], [75, 5], [75, 75], [5, 75]]}]}
        client = SlowClient()
        capture, preview = Mock(), Mock()
        capture.read.return_value = (True, reference)
        capture.release.side_effect = client.release.set
        preview.wait_until_ready.return_value = reference
        def show(*args, **kwargs):
            if capture.read.call_count >= 5:
                self.assertTrue(client.started.wait(1))
            return ord('q') if capture.read.call_count >= 8 else -1
        preview.show.side_effect = show
        root = RESULT_DIR / 'test_tmp'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder, \
                patch.object(camera, 'read_json', return_value=config), \
                patch.object(camera, 'load_reference', return_value=reference), \
                patch.object(camera, 'open_camera', return_value=capture), \
                patch.object(camera, 'ParkingPreview', return_value=preview), \
                patch.object(camera, 'ParkingDelivery', return_value=client), \
                patch.object(camera.time, 'monotonic', side_effect=itertools.count(0, .5)), \
                contextlib.redirect_stdout(io.StringIO()):
            report = camera.run_camera('empty.png', 'spaces.json', Path(folder) / 'session',
                                       enable_http=True, allowed_codes=['1F-A01'],
                                       environment={'AI_OCCUPANCY_API_KEY': 'TEST_ONLY'})
        self.assertGreaterEqual(report['read_frames'], 8)
        self.assertEqual(report['status'], 'STOPPED')
        self.assertEqual(report['http_requests'], 1)
        self.assertEqual(report['deliveries'][0]['status'], 'UPDATED')
        capture.release.assert_called_once()
        preview.close.assert_called_once()


class SpaceMatchReportTests(unittest.TestCase):
    def test_applied_match_without_release_version_is_reviewed_not_replayed(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        from ai_vision.recognition.local_io import write_json_atomic
        with tempfile.TemporaryDirectory(dir=RESULT_DIR) as folder:
            target = Path(folder) / 'report.json'
            write_json_atomic(target, {'status': 'COMPLETED', 'dry_run': False,
                'http_requests': 0, 'events': [], 'deliveries': [], 'vehicle_space': {
                    'http_enabled': True, 'release_http_enabled': True, 'deliveries': [{
                        'status': 'APPLIED', 'blocking_reason': 'SPACE_RELEASE_VERSION_UNAVAILABLE'}]}})
            result = inspect_report(target)
            self.assertTrue(result['requires_review'])
            self.assertEqual(result['uncertain_count'], 0)
            self.assertEqual(result['space_match_receipt_counts'], {'APPLIED': 1})
            self.assertEqual(result['space_delivery_blocking_reasons'], {'SPACE_RELEASE_VERSION_UNAVAILABLE': 1})
            self.assertIn('재전송하지', result['next_action'])

    def test_restart_inspection_includes_assignment_unknown_and_pending(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        from ai_vision.recognition.local_io import write_json_atomic
        with tempfile.TemporaryDirectory(dir=RESULT_DIR) as folder:
            target = Path(folder) / 'report.json'
            for state, review, uncertain in [('DISABLED', False, 0), ('APPLIED', False, 0),
                    ('IN_FLIGHT', True, 1), ('DELIVERY_UNKNOWN', True, 1), ('HELD', True, 0)]:
                report = {'status': 'COMPLETED', 'dry_run': state == 'DISABLED', 'http_requests': 0,
                          'events': [], 'deliveries': [], 'vehicle_space': {
                          'http_enabled': state != 'DISABLED', 'deliveries': [{'status': state}]}}
                write_json_atomic(target, report)
                result = inspect_report(target)
                self.assertEqual(result['requires_review'], review, state)
                self.assertEqual(result['uncertain_count'], uncertain, state)

    def test_disabled_report_cannot_hide_assignment_attempt(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        from ai_vision.recognition.local_io import write_json_atomic
        with tempfile.TemporaryDirectory(dir=RESULT_DIR) as folder:
            target = Path(folder) / 'report.json'
            write_json_atomic(target, {'status': 'COMPLETED', 'dry_run': True, 'http_requests': 0,
                'events': [], 'deliveries': [], 'vehicle_space': {
                'http_enabled': False, 'deliveries': [{'status': 'IN_FLIGHT'}]}})
            with self.assertRaises(ValueError):
                inspect_report(target)


    def test_release_unknown_is_reviewed_and_requires_explicit_release_mode(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        from ai_vision.recognition.local_io import write_json_atomic
        with tempfile.TemporaryDirectory(dir=RESULT_DIR) as folder:
            target = Path(folder) / 'report.json'
            report = {'status': 'COMPLETED', 'dry_run': False, 'http_requests': 0, 'events': [],
                'deliveries': [], 'vehicle_space': {'http_enabled': True, 'release_http_enabled': True,
                'deliveries': [{'status': 'DELIVERY_UNKNOWN', 'payload': {'event_type': 'VEHICLE_SPACE_RELEASE'}}]}}
            write_json_atomic(target, report)
            result = inspect_report(target)
            self.assertTrue(result['requires_review'])
            self.assertEqual(result['uncertain_count'], 1)
            report['vehicle_space']['release_http_enabled'] = False
            write_json_atomic(target, report)
            with self.assertRaises(ValueError):
                inspect_report(target)


    def test_old_and_new_withdrawal_reasons_are_separated_without_changing_http_review(self):
        from ai_vision.parking.inspect_parking_camera import inspect_report
        from ai_vision.recognition.local_io import write_json_atomic
        with tempfile.TemporaryDirectory(dir=RESULT_DIR) as folder:
            path = Path(folder)/'report.json'
            write_json_atomic(path,{'status':'COMPLETED','dry_run':True,'http_requests':0,
                'events':[],'deliveries':[],'vehicle_space':{'http_enabled':False,'events':[
                {'kind':'MATCH_REVIEW','reason':'POSITION_MOVED'},
                {'kind':'TRACK_LOST','reason':'OBSERVATION_GAP'},
                {'kind':'MATCH_REVIEW'}, {'kind':'LOCAL_SPACE_MATCH'}]}})
            result = inspect_report(path)
            self.assertEqual(result['connection_withdrawal_counts'],
                             {'POSITION_MOVED':1,'OBSERVATION_GAP':1,'UNKNOWN_LEGACY':1})
            self.assertFalse(result['requires_review'])
            self.assertEqual(result['uncertain_count'],0)

    def test_invalid_observation_event_list_is_rejected(self):
        from ai_vision.parking.inspect_parking_camera import summarize_connection_reviews
        for events in (None,{},[None]):
            with self.assertRaises(ValueError):
                summarize_connection_reviews(events)

# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_run_live_gate.py

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import requests
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.live_gate_clock import LiveGateClock
from ai_vision.recognition.live_gate_processor import LiveGateProcessor
from ai_vision.recognition.live_gate_session import LiveGateSession
from ai_vision.recognition.run_live_gate import execute, main, _create_http_client
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.live_gate_report import load_report
from ai_vision.tests.recognition.test_live_gate_processor import CONFIG
from ai_vision.recognition.vehicle_http import VehicleHTTPClient
from ai_vision.recognition.vehicle_delivery_flow import VehicleDeliveryFlow


class FakeCapture:
    def __init__(self, frames, opened=True):
        self.frames, self.opened, self.released, self.reads = iter(frames), opened, False, 0

    def isOpened(self):
        return self.opened

    def read(self):
        self.reads += 1
        try:
            return True, next(self.frames)
        except StopIteration:
            return False, None

    def release(self):
        self.released = True


class RunLiveGateTests(unittest.TestCase):
    def test_handoff_requires_real_explicit_http_before_opening_camera(self):
        with patch('cv2.VideoCapture') as opened:
            for flags in (['--single-vehicle-handoff'], ['--demo','--single-vehicle-handoff']):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(flags+['--output-dir','unused_handoff'])
            opened.assert_not_called()

    def test_cancelled_preparation_does_not_read_or_process_measurement_frames(self):
        capture, processor, preview = Mock(), Mock(), Mock()
        report = execute(capture, processor, self.session(), preview=preview, start_cancelled=True)
        self.assertEqual(report['stop_reason'], 'USER_INTERRUPTED')
        self.assertEqual(report['status'], 'STOPPED')
        self.assertEqual(report['captured_frames'], 0)
        self.assertEqual(report['request_attempts'], 0)
        capture.read.assert_not_called()
        processor.process.assert_not_called()

    def test_cli_creates_session_only_after_user_preparation(self):
        root = self.output_folder()
        config = root / 'ready_config.json'
        config.write_text(json.dumps(CONFIG), encoding='utf-8')
        state = {'ready': False}
        def ready(capture):
            state['ready'] = True
            return True
        def make_session(*args, **kwargs):
            self.assertTrue(state['ready'])
            return LiveGateSession(*args, **kwargs)
        def finish(capture, processor, session, **kwargs):
            self.assertEqual(kwargs['seconds'], 60)
            capture.release()
            processor.close()
            session.close()
            kwargs['preview'].close()
            return {**session.summary(), 'status': 'STOPPED'}
        with patch('ai_vision.recognition.preview_gate_config.LiveGatePreview') as preview, \
                patch('ai_vision.recognition.run_live_gate.LiveGateSession', side_effect=make_session), \
                patch('ai_vision.recognition.run_live_gate.LiveGateProcessor'), patch('cv2.VideoCapture'), \
                patch('ai_vision.recognition.run_live_gate.execute', side_effect=finish), \
                contextlib.redirect_stdout(io.StringIO()):
            preview.return_value.wait_until_ready.side_effect = ready
            main(['--config', str(config), '--camera-id', 'TEST', '--down-direction', 'ENTRY', '--preview',
                  '--seconds', '60', '--output-dir', str(root / 'ready_run')])
        preview.return_value.wait_until_ready.assert_called_once()

    def test_preview_q_stops_before_processing_and_closes_before_processor(self):
        capture = FakeCapture([np.zeros((100, 100, 3), dtype=np.uint8)])
        processor, preview = Mock(), Mock(return_value=False)
        events = []
        preview.close.side_effect = lambda: events.append('preview')
        processor.close.side_effect = lambda: events.append('processor')
        report = execute(capture, processor, self.session(), monotonic_reader=lambda: .1,
                         deadline_reader=lambda: 0, preview=preview)
        self.assertEqual(report['stop_reason'], 'USER_INTERRUPTED')
        self.assertEqual(report['status'], 'STOPPED')
        self.assertEqual(events, ['preview', 'processor'])
        self.assertTrue(capture.released)
        processor.process.assert_not_called()
        self.assertEqual(report['request_attempts'], 0)

    def test_preview_error_reports_failure_and_releases_camera(self):
        capture = FakeCapture([np.zeros((100, 100, 3), dtype=np.uint8)])
        preview = Mock(side_effect=RuntimeError('화면 표시 오류'))
        report = execute(capture, Mock(), self.session(), monotonic_reader=lambda: .1,
                         deadline_reader=lambda: 0, preview=preview)
        self.assertEqual(report['status'], 'FAILED')
        self.assertTrue(capture.released)
        preview.close.assert_called_once()

    def test_preview_close_failure_does_not_prevent_other_cleanup(self):
        capture = FakeCapture([])
        preview, processor = Mock(), Mock()
        preview.close.side_effect = RuntimeError('창 닫기 오류')
        report = execute(capture, processor, self.session(), allow_source_end=True, preview=preview)
        self.assertEqual(report['status'], 'FAILED')
        self.assertEqual(report['cleanup_errors'], 1)
        self.assertTrue(capture.released)
        processor.close.assert_called_once()

    def test_headless_preview_failure_happens_before_model_or_camera(self):
        root = self.output_folder()
        config = root / 'preview_config.json'
        config.write_text(json.dumps(CONFIG), encoding='utf-8')
        with patch('ai_vision.recognition.preview_gate_config.LiveGatePreview', side_effect=RuntimeError('화면 없음')), \
                patch('cv2.VideoCapture') as capture, \
                patch('ai_vision.recognition.run_live_gate.LiveGateProcessor') as processor, \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['--config', str(config), '--camera-id', 'TEST', '--down-direction', 'ENTRY',
                  '--preview', '--output-dir', str(root / 'preview_run')])
        capture.assert_not_called()
        processor.assert_not_called()

    def test_remote_samples_reach_consensus_and_single_boot_attempt(self):
        from ai_vision.recognition.remote_plate_reader import RemotePlateReader
        from ai_vision.tests.recognition.test_remote_plate_reader import make_session
        cloud = make_session([{'plate_number': '91소6408', 'plate_type': 'KOREAN_VALID', 'plate_confidence': .9}])
        reader = RemotePlateReader('http://vision', session_factory=lambda: cloud)
        frames = [np.full((100, 100, 3), i, dtype=np.uint8) for i in range(7)]
        def tracker(frame):
            index = int(frame[0, 0, 0])
            y = 20 if index < 3 else (50 if index == 3 else 80)
            return [{'track_id': 7, 'box': [40, y - 10, 60, y + 10]}]
        processor = LiveGateProcessor(CONFIG, tracker, reader.read)
        boot = Mock()
        boot.post.side_effect = requests.Timeout()
        client = VehicleHTTPClient('http://boot/alpharking/admin', 'BOOT_KEY', True, session_factory=lambda: boot)
        session = self.session()
        session.flow = VehicleDeliveryFlow(client)
        result = execute(FakeCapture(frames), processor, session,
                         monotonic_reader=iter(i * .3 for i in range(7)).__next__, allow_source_end=True)
        self.assertGreaterEqual(cloud.post.call_count, 2)
        self.assertEqual(result['processed_passages'], 1)
        self.assertEqual(result['request_attempts'], 1)
        self.assertEqual(result['results'][0]['plate_consensus']['plate_number'], '91소6408')
        self.assertEqual(result['results'][0]['receipt_state'], 'DELIVERY_UNKNOWN')
        boot.post.assert_called_once()
        self.assertNotIn('headers', cloud.post.call_args.kwargs)

    def test_remote_mode_injects_reader_without_local_ocr_or_boot_requests(self):
        root = self.output_folder()
        config = root / 'config.json'
        config.write_text(json.dumps(CONFIG), encoding='utf-8')
        def finish(capture, processor, session, **kwargs):
            self.assertFalse(session.flow.client.enabled)
            session.close()
            return {**session.summary(), 'status': 'STOPPED'}
        with patch('ai_vision.recognition.remote_plate_reader.RemotePlateReader') as remote, \
                patch('ai_vision.recognition.run_live_gate.LiveGateProcessor') as processor, \
                patch('cv2.VideoCapture'), patch('ai_vision.recognition.run_live_gate.execute', side_effect=finish), \
                contextlib.redirect_stdout(io.StringIO()):
            main(['--config', str(config), '--camera-id', 'TEST', '--down-direction', 'ENTRY',
                  '--vision-api-url', 'http://cloud-private:8000', '--output-dir', str(root / 'run')])
        processor.assert_called_once_with(CONFIG, plate_reader=remote.return_value.read)
        remote.assert_called_once_with('http://cloud-private:8000')
        summary = (root / 'run' / 'summary.json').read_text(encoding='utf-8')
        self.assertEqual(json.loads(summary)['recognition_mode'], 'REMOTE_API')
        self.assertNotIn('cloud-private', summary)

    def test_demo_rejects_remote_camera_inference(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['--demo', '--vision-api-url', 'http://cloud', '--output-dir', str(self.output_folder() / 'run')])

    def test_enabled_http_reads_project_settings_without_mutating_process_environment(self):
        path = self.output_folder() / ".env"
        path.write_text('VISION_BOOT_CONTEXT_URL=http://file-host:81/alpharking/admin\nAI_OCCUPANCY_API_KEY=FILE_KEY\n', encoding="utf-8-sig")
        with patch.dict("os.environ", {}, clear=True):
            client = _create_http_client(True, env_file=path)
            self.assertTrue(client.enabled)
            self.assertEqual(client._url, "http://file-host:81/alpharking/admin/api/parking/ai/vehicle-events")
            self.assertEqual(client._api_key, "FILE_KEY")
            self.assertNotIn("AI_OCCUPANCY_API_KEY", os.environ)

    def test_explicit_environment_and_command_override_file_settings(self):
        path = self.output_folder() / ".env"
        path.write_text('VISION_BOOT_CONTEXT_URL=http://file-host\nAI_OCCUPANCY_API_KEY=FILE_KEY\n', encoding="utf-8")
        with patch.dict("os.environ", {"VISION_BOOT_CONTEXT_URL": "http://env-host", "AI_OCCUPANCY_API_KEY": "ENV_KEY"}, clear=True):
            client = _create_http_client(True, "http://command-host", path)
            self.assertEqual(client._url, "http://command-host/api/parking/ai/vehicle-events")
            self.assertEqual(client._api_key, "ENV_KEY")
            self.assertEqual(_create_http_client(True, env_file=path)._url, "http://env-host/api/parking/ai/vehicle-events")
            with patch.dict("os.environ", {"AI_OCCUPANCY_API_KEY": ""}):
                with self.assertRaises(ValueError):
                    _create_http_client(True, env_file=path)

    def test_disabled_http_does_not_read_env_file(self):
        with patch("dotenv.dotenv_values", side_effect=AssertionError("설정 파일 접근 금지")):
            self.assertFalse(_create_http_client(False).enabled)

    def test_existing_real_output_stops_before_model_preparation(self):
        root = self.output_folder()
        config = root / "config.json"
        config.write_text(json.dumps(CONFIG), encoding="utf-8")
        output = root / "run"
        output.mkdir()
        with patch("ai_vision.recognition.run_live_gate.LiveGateProcessor") as processor, \
                patch("cv2.VideoCapture") as camera, contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--config", str(config), "--camera-id", "TEST", "--down-direction", "ENTRY", "--output-dir", str(output)])
        processor.assert_not_called()
        camera.assert_not_called()

    def test_session_clock_starts_after_camera_creation(self):
        root = self.output_folder()
        config = root / "config.json"
        config.write_text(json.dumps(CONFIG), encoding="utf-8")
        order = []
        def camera(index):
            order.append("camera")
            return Mock()
        def session(*args, **kwargs):
            order.append("session")
            return LiveGateSession(*args, **kwargs)
        def finish(capture, processor, session, **kwargs):
            session.close()
            return {**session.summary(), "status": "STOPPED"}
        with patch("ai_vision.recognition.run_live_gate.LiveGateProcessor") as factory, \
                patch("cv2.VideoCapture", side_effect=camera), \
                patch("ai_vision.recognition.run_live_gate.LiveGateSession", side_effect=session), \
                patch("ai_vision.recognition.run_live_gate.execute", side_effect=finish), contextlib.redirect_stdout(io.StringIO()):
            factory.return_value.prepare.side_effect = lambda: order.append("prepare")
            main(["--config", str(config), "--camera-id", "TEST", "--down-direction", "ENTRY",
                  "--output-dir", str(root / "run")])
        self.assertEqual(order, ["prepare", "camera", "session"])

    def test_both_crossing_directions_and_uncertain_plates_with_enabled_http(self):
        # 실제 영상 정확도가 아니라 프레임 처리부터 송신 판단까지의 연결을 확인합니다.
        for reverse, down, text, kind in ((False, "EXIT", "91소6408", "KOREAN_VALID"),
                                          (True, "ENTRY", "91소6408", "KOREAN_VALID"),
                                          (True, "EXIT", "91소6408", "KOREAN_VALID"),
                                          (False, "ENTRY", "10-1557", "REVIEW"),
                                          (False, "ENTRY", "ABC123", "FOREIGN_OR_OTHER")):
            with self.subTest(reverse=reverse, down=down, kind=kind):
                frames = [np.full((100, 100, 3), i, dtype=np.uint8) for i in range(7)]
                def tracker(frame):
                    index = int(frame[0, 0, 0])
                    y = 20 if index < 3 else (50 if index == 3 else 80)
                    y = 100 - y if reverse else y
                    return [{"track_id": 7, "box": [40, y - 10, 60, y + 10]}]
                processor = LiveGateProcessor(CONFIG, tracker, lambda crop: {
                    "plate_number": text, "plate_type": kind, "plate_detection_confidence": .8})
                network = Mock()
                network.post.side_effect = requests.Timeout()
                client = VehicleHTTPClient("http://boot:81/alpharking/admin", "TEST", True, session_factory=lambda: network)
                session = LiveGateSession("TEST", down, self.session().clock, VehicleDeliveryFlow(client))
                result = execute(FakeCapture(frames), processor, session,
                                 monotonic_reader=iter(i * .3 for i in range(7)).__next__, allow_source_end=True)
                self.assertEqual(result["processed_passages"], 1)
                if kind == "KOREAN_VALID":
                    network.post.assert_called_once()
                    expected = down if not reverse else {"ENTRY": "EXIT", "EXIT": "ENTRY"}[down]
                    self.assertEqual(network.post.call_args.kwargs["json"]["direction"], expected)
                    self.assertEqual(result["results"][0]["receipt_state"], "DELIVERY_UNKNOWN")
                else:
                    network.post.assert_not_called()
                    self.assertEqual(result["decision_counts"], {"BLOCKED": 1})

    def test_model_preparation_failure_does_not_start_clock_or_camera(self):
        root = self.output_folder()
        config = root / "config.json"
        config.write_text(json.dumps(CONFIG), encoding="utf-8")
        with patch("ai_vision.recognition.run_live_gate.LiveGateProcessor") as factory, \
                patch("ai_vision.recognition.run_live_gate.LiveGateSession") as session, \
                patch("cv2.VideoCapture") as camera:
            factory.return_value.prepare.side_effect = RuntimeError("private model path")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--config", str(config), "--camera-id", "TEST", "--down-direction", "ENTRY",
                      "--output-dir", str(root / "run")])
            session.assert_not_called()
            camera.assert_not_called()
            factory.return_value.close.assert_called_once()

    def test_prepare_with_injected_functions_keeps_models_unloaded(self):
        processor = LiveGateProcessor(CONFIG, lambda frame: [], lambda crop: {})
        with patch.object(processor, "_prepare_tracker") as tracker:
            processor.prepare()
            tracker.assert_not_called()
        processor.close()
        with self.assertRaises(ValueError):
            processor.prepare()

    def test_demo_rejects_http_options_before_camera_or_network(self):
        for options in (["--enable-http"], ["--boot-context-url", "http://localhost:81/alpharking/admin"]):
            with patch("cv2.VideoCapture") as camera, patch("requests.Session") as network:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(["--demo", "--output-dir", str(self.output_folder() / "run"), *options])
                camera.assert_not_called()
                network.assert_not_called()

    def test_http_requires_key_and_url_before_models_and_camera(self):
        root = self.output_folder()
        config = root / "config.json"
        config.write_text(json.dumps(CONFIG), encoding="utf-8")
        for environment in ({}, {"VISION_BOOT_CONTEXT_URL": "http://localhost:81/alpharking/admin"},
                            {"AI_OCCUPANCY_API_KEY": "PRIVATE_KEY"}):
            with patch.dict("os.environ", environment, clear=True), patch("cv2.VideoCapture") as camera, \
                    patch("ai_vision.recognition.run_live_gate.LiveGateProcessor") as processor, \
                    patch("ai_vision.recognition.run_live_gate.BASE_DIR", root / "ai_vision"):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(["--enable-http", "--config", str(config), "--camera-id", "TEST", "--down-direction", "ENTRY",
                          "--output-dir", str(root / "run")])
                camera.assert_not_called()
                processor.assert_not_called()

    def test_cli_wires_enabled_flow_without_exposing_key_or_url(self):
        root = self.output_folder()
        config = root / "config.json"
        config.write_text(json.dumps(CONFIG), encoding="utf-8")
        seen = []
        prepared = []
        def finish(capture, processor, session, **kwargs):
            self.assertEqual(prepared, [True])
            seen.append(session.flow.client.enabled)
            session.close()
            return {**session.summary(), "status": "STOPPED"}
        with patch.dict("os.environ", {"AI_OCCUPANCY_API_KEY": "PRIVATE_KEY"}), \
                patch("ai_vision.recognition.run_live_gate.LiveGateProcessor") as processor_factory, patch("cv2.VideoCapture"), \
                patch("ai_vision.recognition.run_live_gate.execute", side_effect=finish), \
                contextlib.redirect_stdout(io.StringIO()) as stdout:
            processor_factory.return_value.prepare.side_effect = lambda: prepared.append(True)
            main(["--enable-http", "--boot-context-url", "http://private-host:81/alpharking/admin", "--config", str(config),
                  "--camera-id", "TEST", "--down-direction", "ENTRY", "--output-dir", str(root / "run")])
        self.assertEqual(seen, [True])
        summary = (root / "run" / "summary.json").read_text(encoding="utf-8")
        self.assertTrue(json.loads(summary)["http_enabled"])
        for private in ("PRIVATE_KEY", "private-host"):
            self.assertNotIn(private, summary + stdout.getvalue())

    def test_confirmed_crossing_reaches_admin_contract_once_with_mock_http(self):
        frames = [np.full((100, 100, 3), i, dtype=np.uint8) for i in range(7)]
        def tracker(frame):
            index = int(frame[0, 0, 0])
            y = 20 if index < 3 else (50 if index == 3 else 80)
            return [{"track_id": 7, "box": [40, y - 10, 60, y + 10]}]
        processor = LiveGateProcessor(CONFIG, tracker, lambda crop: {
            "plate_number": "91소6408", "plate_type": "KOREAN_VALID", "plate_detection_confidence": .8})
        network = Mock()
        def post(url, **kwargs):
            event = kwargs["json"]
            response = Mock(status_code=200)
            response.iter_content.return_value = [json.dumps({"eventId": event["event_id"], "eventType": "VEHICLE_PASSAGE",
                "plateNumber": event["plate_number"], "spaceCode": None, "parkingUsageId": 1, "outcome": "PROCESSED"}).encode("utf-8")]
            return response
        network.post.side_effect = post
        client = VehicleHTTPClient("http://boot:81/alpharking/admin", "TEST_KEY", True, session_factory=lambda: network)
        session = self.session()
        session.flow = VehicleDeliveryFlow(client)
        report = execute(FakeCapture(frames), processor, session, monotonic_reader=iter(i * .3 for i in range(7)).__next__,
                         allow_source_end=True)
        self.assertEqual(report["request_attempts"], 1)
        self.assertEqual(report["results"][0]["receipt_state"], "APPLIED")
        network.post.assert_called_once()
        self.assertEqual(network.post.call_args.args[0], "http://boot:81/alpharking/admin/api/parking/ai/vehicle-events")
        self.assertEqual(network.post.call_args.kwargs["json"]["direction"], "ENTRY")
        self.assertEqual(network.post.call_args.kwargs["headers"], {"X-AI-API-Key": "TEST_KEY"})

    def output_folder(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        assert root.resolve().is_relative_to(base.resolve())
        return root

    def session(self):
        return LiveGateSession("TEST_GATE", "ENTRY", LiveGateClock(datetime(2020, 1, 1, tzinfo=timezone.utc), 0))

    def test_frames_tracking_crossing_ocr_session_and_disabled_delivery_connect(self):
        frames = [np.full((100, 100, 3), i, dtype=np.uint8) for i in range(7)]
        def tracker(frame):
            index = int(frame[0, 0, 0])
            y = 20 if index < 3 else (50 if index == 3 else 80)
            return [{"track_id": 7, "box": [40, y - 10, 60, y + 10]}]
        processor = LiveGateProcessor(CONFIG, tracker, lambda crop: {
            "plate_number": "91소6408", "plate_type": "KOREAN_VALID", "plate_detection_confidence": .8})
        capture, session = FakeCapture(frames), self.session()
        loaded = "ai_vision.recognition.recognizer" in sys.modules
        report = execute(capture, processor, session, monotonic_reader=iter(i * .3 for i in range(7)).__next__, allow_source_end=True)
        self.assertEqual((report["captured_frames"], report["processed_passages"], report["request_attempts"]), (7, 1, 0))
        self.assertEqual(report["decision_counts"], {"DISABLED": 1})
        self.assertEqual(report["results"][0]["plate_consensus"]["plate_number"], "91소6408")
        self.assertTrue(capture.released)
        self.assertTrue(report["closed"])
        self.assertEqual(processor._bytes, 0)
        self.assertEqual("ai_vision.recognition.recognizer" in sys.modules, loaded)

    def test_camera_open_or_processor_failure_releases_all_resources(self):
        for opened in (False, True):
            capture, processor, session = FakeCapture([object()], opened), Mock(), self.session()
            processor.process.side_effect = RuntimeError("private path")
            processor.dropped_crops = processor.dropped_tracks = 0
            report = execute(capture, processor, session, monotonic_reader=lambda: 0)
            self.assertEqual(report["status"], "FAILED")
            self.assertTrue(capture.released)
            self.assertTrue(session.summary()["closed"])
            processor.close.assert_called_once()
            self.assertNotIn("private", str(report))

    def test_time_frame_and_invalid_limits_always_close(self):
        for options, expected in (({"seconds": .2}, "TIME_LIMIT"), ({"max_frames": 1}, "FRAME_LIMIT"),
                                  ({"seconds": 0}, "CAPTURE_OR_PROCESSING_FAILED")):
            capture, processor, session = FakeCapture([object()] * 3), Mock(), self.session()
            processor.process.return_value = []
            processor.dropped_crops = processor.dropped_tracks = 0
            report = execute(capture, processor, session, monotonic_reader=iter((0, .3, .6)).__next__, **options)
            self.assertEqual(report["stop_reason"], expected)
            self.assertTrue(capture.released)
            self.assertTrue(report["closed"])

    def test_keyboard_interrupt_closes_without_automatic_reconnect(self):
        capture, processor, session = FakeCapture([object()]), Mock(), self.session()
        processor.process.side_effect = KeyboardInterrupt()
        processor.dropped_crops = processor.dropped_tracks = 0
        report = execute(capture, processor, session, monotonic_reader=lambda: 0)
        self.assertEqual(report["stop_reason"], "USER_INTERRUPTED")
        self.assertEqual(capture.reads, 1)
        self.assertTrue(capture.released)

    def test_demo_cli_never_opens_camera_or_network_and_preserves_existing_output(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            assert root.resolve().is_relative_to(base.resolve())
            output = root / "demo"
            with patch("cv2.VideoCapture", side_effect=AssertionError("camera forbidden")):
                with patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")):
                    with contextlib.redirect_stdout(io.StringIO()):
                        main(["--demo", "--output-dir", str(output)])
                    before = (output / "summary.json").read_bytes()
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        main(["--demo", "--output-dir", str(output)])
            report = json.loads(before)
            self.assertTrue(report["uses_synthetic_source"])
            self.assertEqual(report["decision_counts"], {"DISABLED": 1})
            self.assertEqual((output / "summary.json").read_bytes(), before)

    def test_real_mode_requires_configuration_and_reports_fake_camera_failure(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            assert root.resolve().is_relative_to(base.resolve())
            output = root / "run"
            with patch("cv2.VideoCapture") as camera:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(["--output-dir", str(output)])
                camera.assert_not_called()
            config = root / "config.json"
            config.write_text(json.dumps(CONFIG), encoding="utf-8")
            capture = FakeCapture([], opened=False)
            with patch("cv2.VideoCapture", return_value=capture), patch.object(LiveGateProcessor, "prepare"):
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                    main(["--config", str(config), "--camera-id", "TEST_GATE", "--down-direction", "ENTRY", "--output-dir", str(output)])
            self.assertTrue(capture.released)
            self.assertEqual(json.loads((output / "summary.json").read_text(encoding="utf-8"))["status"], "FAILED")

    def test_final_save_failure_keeps_running_marker_and_recovers_full_report(self):
        output = self.output_folder() / "run"
        calls = 0
        def write(path, value):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("private output path")
            write_json_atomic(path, value)
        with patch("ai_vision.recognition.run_live_gate.write_json_atomic", side_effect=write):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                main(["--demo", "--output-dir", str(output)])
        self.assertEqual(stopped.exception.code, 1)
        self.assertEqual(json.loads((output / "summary.json").read_text(encoding="utf-8"))["status"], "RUNNING")
        self.assertEqual(load_report(output / "recovered_summary.json")["processed_passages"], 1)
        failure = (output / "failure.json").read_text(encoding="utf-8")
        self.assertNotIn("private", failure)
        self.assertIn("FINAL_SAVE", failure)

    def test_complete_summary_not_overwritten_when_writer_raises_after_save(self):
        output = self.output_folder() / "run"
        def write(path, value):
            write_json_atomic(path, value)
            if value["status"] == "STOPPED":
                raise OSError("after replace")
        with patch("ai_vision.recognition.run_live_gate.write_json_atomic", side_effect=write):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--demo", "--output-dir", str(output)])
        self.assertEqual(load_report(output / "summary.json")["processed_passages"], 1)

    def test_initial_write_and_failure_write_errors_return_controlled_exit(self):
        output = self.output_folder() / "run"
        with patch("ai_vision.recognition.run_live_gate.write_json_atomic", side_effect=OSError("disk full")), \
                patch("ai_vision.recognition.live_gate_storage.write_json_atomic", side_effect=OSError("disk full")):
            with contextlib.redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit) as stopped:
                main(["--demo", "--output-dir", str(output)])
        self.assertEqual(stopped.exception.code, 1)
        self.assertIn("별도 실패 기록 저장 불가", stderr.getvalue())

    def test_cleanup_failure_does_not_prevent_session_close(self):
        capture, processor, session = FakeCapture([]), Mock(), self.session()
        processor.dropped_crops = processor.dropped_tracks = 0
        processor.close.side_effect = OSError("private error")
        report = execute(capture, processor, session)
        self.assertEqual((report["status"], report["cleanup_errors"], report["closed"]), ("FAILED", 1, True))

    def test_timing_includes_failed_processing_and_keeps_collection_clock_separate(self):
        capture, processor, session = FakeCapture([object()]), Mock(), self.session()
        processor.dropped_crops = processor.dropped_tracks = 0
        processor.process.side_effect = RuntimeError("test")
        report = execute(capture, processor, session, monotonic_reader=lambda: .3,
                         performance_reader=iter((0, .2, .2, .7)).__next__)
        metrics = report["performance"]
        self.assertEqual(metrics["captured_frames"], 1)
        self.assertEqual(metrics["stages"]["read"]["total_seconds"], .2)
        self.assertAlmostEqual(metrics["stages"]["process"]["total_seconds"], .5)
        self.assertEqual(metrics["stages"]["process"]["errors"], 1)
        self.assertTrue(session.summary()["closed"])

    def test_real_cli_records_used_config_even_if_source_file_changes(self):
        root = self.output_folder()
        config, output = root / "config.json", root / "run"
        config.write_text(json.dumps(CONFIG), encoding="utf-8")
        capture = FakeCapture([])
        def read():
            config.write_text('{}', encoding="utf-8")
            return False, None
        capture.read = read
        with patch("cv2.VideoCapture", return_value=capture), patch.object(LiveGateProcessor, "prepare"):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                main(["--config", str(config), "--camera-id", "TEST_GATE", "--down-direction", "EXIT",
                      "--camera-index", "2", "--seconds", "15", "--output-dir", str(output)])
        self.assertEqual(stopped.exception.code, 1)
        report = load_report(output / "summary.json")
        context = report["run_context"]
        self.assertEqual((context["camera_index"], context["seconds"]), (2, 15))
        self.assertEqual(context["tracking_config"], CONFIG)
        self.assertNotIn(str(config), (output / "summary.json").read_text(encoding="utf-8"))

    def test_demo_records_actual_synthetic_limits_and_no_camera_config(self):
        output = self.output_folder() / "run"
        with contextlib.redirect_stdout(io.StringIO()):
            main(["--demo", "--seconds", "10", "--camera-index", "2", "--output-dir", str(output)])
        context = load_report(output / "summary.json")["run_context"]
        self.assertEqual(context["source_type"], "SYNTHETIC")
        self.assertEqual(context["seconds"], 20)
        self.assertIsNone(context["camera_index"])
        self.assertIsNone(context["tracking_config"])

    def test_small_clock_history_keeps_session_running_and_does_not_invent_votes(self):
        # 이전 시각을 찾을 수 없던 실패 경로를 1개·2개 보관 한도로 검증합니다.
        for limit, expected_status, expected_samples in ((1, "BLOCKED", 1), (2, "DISABLED", 2)):
            with self.subTest(history_limit=limit):
                frames = [np.full((100, 100, 3), index, dtype=np.uint8) for index in range(7)]
                def tracker(frame):
                    index = int(frame[0, 0, 0])
                    y = 20 if index < 3 else (50 if index == 3 else 80)
                    return [{"track_id": 7, "box": [40, y - 10, 60, y + 10]}]
                ocr_frames = []
                def reader(crop):
                    ocr_frames.append(int(crop[0, 0, 0]))
                    return {"plate_number": "91소6408", "plate_type": "KOREAN_VALID", "plate_detection_confidence": .8}
                processor = LiveGateProcessor(CONFIG, tracker, reader)
                clock = LiveGateClock(datetime(2020, 1, 1, tzinfo=timezone.utc), 0, history_limit=limit)
                session = LiveGateSession("TEST_GATE", "ENTRY", clock)
                report = execute(FakeCapture(frames), processor, session,
                                 monotonic_reader=iter(index * .3 for index in range(7)).__next__, allow_source_end=True)
                self.assertEqual((report["status"], report["processed_passages"], report["request_attempts"]), ("STOPPED", 1, 0))
                self.assertEqual(report["results"][0]["decision"], expected_status)
                self.assertEqual(report["results"][0]["sample_count"], expected_samples)
                self.assertEqual(ocr_frames, list(range(7 - limit, 7)))
                self.assertGreater(report["processor_statistics"]["expired_history_crops"], 0)

    def test_camera_open_and_first_read_failure_are_not_normal_completion(self):
        for opened, expected in ((False, "CAMERA_OPEN_FAILED"), (True, "CAMERA_READ_FAILED")):
            capture, processor, session = FakeCapture([], opened=opened), Mock(), self.session()
            processor.dropped_crops = processor.dropped_tracks = 0
            report = execute(capture, processor, session)
            self.assertEqual((report["status"], report["stop_reason"], report["captured_frames"]), ("FAILED", expected, 0))
            self.assertTrue(capture.released)
            self.assertTrue(report["closed"])
            processor.process.assert_not_called()

    def test_read_failure_after_passage_preserves_results_and_does_not_reconnect(self):
        frames = [np.full((100, 100, 3), index, dtype=np.uint8) for index in range(7)]
        def tracker(frame):
            index = int(frame[0, 0, 0])
            y = 20 if index < 3 else (50 if index == 3 else 80)
            return [{"track_id": 7, "box": [40, y - 10, 60, y + 10]}]
        processor = LiveGateProcessor(CONFIG, tracker, lambda crop: {"plate_number": "", "plate_type": "NOT_DETECTED"})
        capture = FakeCapture(frames)
        report = execute(capture, processor, self.session(), monotonic_reader=iter(index * .3 for index in range(7)).__next__)
        self.assertEqual((report["status"], report["stop_reason"], report["processed_passages"]), ("FAILED", "CAMERA_READ_FAILED", 1))
        self.assertEqual(len(report["results"]), 1)
        self.assertEqual(capture.reads, 8)
        self.assertEqual(processor._bytes, 0)

    def test_finite_source_end_requires_explicit_boolean_policy(self):
        for policy, expected in ((True, "STOPPED"), (False, "FAILED"), (1, "FAILED")):
            processor = Mock()
            processor.dropped_crops = processor.dropped_tracks = 0
            report = execute(FakeCapture([]), processor, self.session(), allow_source_end=policy)
            self.assertEqual(report["status"], expected)

    def test_read_exception_has_capture_reason_without_private_error_text(self):
        capture, processor = FakeCapture([]), Mock()
        capture.read = Mock(side_effect=OSError("private device details"))
        processor.dropped_crops = processor.dropped_tracks = 0
        report = execute(capture, processor, self.session())
        self.assertEqual((report["status"], report["stop_reason"], report["error_type"]), ("FAILED", "CAMERA_READ_FAILED", "OSError"))
        self.assertEqual(report["performance"]["stages"]["read"]["errors"], 1)
        self.assertNotIn("private", str(report))

    def test_expired_budget_after_processing_prevents_next_camera_read(self):
        capture, processor = FakeCapture([object(), object()]), Mock()
        processor.process.return_value = []
        processor.dropped_crops = processor.dropped_tracks = 0
        report = execute(capture, processor, self.session(), seconds=1, monotonic_reader=lambda: 0,
                         deadline_reader=iter((0, 0, 2)).__next__)
        self.assertEqual((report["status"], report["stop_reason"], capture.reads), ("STOPPED", "TIME_LIMIT", 1))
        processor.process.assert_called_once()
        self.assertTrue(report["deadline"]["expired_before_read"])
        self.assertEqual(report["deadline"]["checks"], 2)
        self.assertTrue(capture.released)

    def test_initial_deadline_expiry_prevents_first_read(self):
        capture, processor = FakeCapture([object()]), Mock()
        processor.dropped_crops = processor.dropped_tracks = 0
        report = execute(capture, processor, self.session(), seconds=1, deadline_reader=iter((0, 1)).__next__)
        self.assertEqual((report["stop_reason"], report["captured_frames"], capture.reads), ("TIME_LIMIT", 0, 0))
        processor.process.assert_not_called()

    def test_read_that_finishes_after_frame_time_limit_is_not_processed(self):
        capture, processor = FakeCapture([object()]), Mock()
        processor.dropped_crops = processor.dropped_tracks = 0
        report = execute(capture, processor, self.session(), seconds=1, monotonic_reader=lambda: 2,
                         deadline_reader=iter((0, 0)).__next__)
        self.assertEqual((report["stop_reason"], report["captured_frames"], capture.reads), ("TIME_LIMIT", 1, 1))
        self.assertFalse(report["deadline"]["expired_before_read"])
        processor.process.assert_not_called()

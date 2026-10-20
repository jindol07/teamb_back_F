# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_run_live_gate.py

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.live_gate_clock import LiveGateClock
from ai_vision.recognition.live_gate_processor import LiveGateProcessor
from ai_vision.recognition.live_gate_session import LiveGateSession
from ai_vision.recognition.run_live_gate import execute, main
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.live_gate_report import load_report
from ai_vision.tests.recognition.test_live_gate_processor import CONFIG


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
            with patch("cv2.VideoCapture", return_value=capture):
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
        with patch("cv2.VideoCapture", return_value=capture):
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

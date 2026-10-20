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
        report = execute(capture, processor, session, monotonic_reader=iter(i * .3 for i in range(7)).__next__)
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
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--config", str(config), "--camera-id", "TEST_GATE", "--down-direction", "EXIT",
                      "--camera-index", "2", "--seconds", "15", "--output-dir", str(output)])
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

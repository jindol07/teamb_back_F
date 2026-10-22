"""실제 화재 모델과 USB 장치 없이 워밍업과 영상 연결 장애를 재현합니다."""

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from ai_vision.safety.live_fire_smoke import (
    LiveConfig, main, run_live, warmup_fire_smoke_model,
)
from ai_vision.tests.safety.test_live_fire_smoke import FakeCapture, FakeModel


class BrokenOpen(FakeCapture):
    def isOpened(self):
        return False


class BrokenRead(FakeCapture):
    def __init__(self, frames=0):
        super().__init__(frames=frames)


class StartupTests(unittest.TestCase):
    def test_warmup_uses_configured_parameters_without_real_camera(self):
        model = FakeModel(boxes=[])
        cfg = LiveConfig(fire_conf=.32, smoke_conf=.35, image_size=96, device="cpu")
        duration = warmup_fire_smoke_model(model, cfg)
        self.assertGreaterEqual(duration, 0)
        self.assertEqual(len(model.calls), 1)
        call = model.calls[0]
        self.assertEqual(call["source"].shape, (96, 96, 3))
        self.assertEqual(call["conf"], .32)
        self.assertEqual(call["iou"], .45)
        self.assertEqual(call["imgsz"], 96)
        self.assertEqual(call["device"], "cpu")

    def test_warmup_rejects_empty_model_result(self):
        class Empty(FakeModel):
            def predict(self, **kwargs):
                return []
        with self.assertRaisesRegex(RuntimeError, "워밍업"):
            warmup_fire_smoke_model(Empty(), LiveConfig(image_size=64))

    def test_invalid_configuration(self):
        for opts in ({"warmup": "true"}, {"camera_retries": True},
                     {"camera_retries": -1}, {"camera_retries": 21},
                     {"camera_retry_delay": -1}, {"camera_retry_delay": float("nan")},
                     {"camera_retry_delay": 31}):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                LiveConfig(**opts)

    def test_auto_warmup_before_camera_open_for_actual_model(self):
        model = FakeModel(boxes=[])
        opened = []
        def create_capture(index):
            opened.append(index)
            self.assertEqual(len(model.calls), 1, "모델 준비 전에 웹캠이 열렸습니다.")
            return FakeCapture(frames=4)
        fake_ultralytics = types.ModuleType("ultralytics")
        fake_ultralytics.YOLO = lambda _: model
        with tempfile.TemporaryDirectory() as root:
            config = LiveConfig(max_frames=2, max_seconds=0, output_dir=Path(root),
                                camera_retries=0, image_size=64)
            with patch.dict(sys.modules, {"ultralytics": fake_ultralytics}), \
                 patch("ai_vision.safety.live_fire_smoke.require_model_file"):
                summary = run_live(config, capture_factory=create_capture)
            self.assertEqual(summary["status"], "MAX_FRAMES")
            self.assertEqual(summary["camera_open_attempts"], 1)
            self.assertTrue(summary["warmup_completed"])
            self.assertIsNotNone(summary["model_warmup_ms"])
            self.assertEqual(opened, [0])
            self.assertEqual(summary["inference_samples"], 1)

    def test_injected_model_does_not_warmup_automatically(self):
        with tempfile.TemporaryDirectory() as root:
            model = FakeModel(boxes=[])
            result = run_live(LiveConfig(max_frames=1, output_dir=Path(root)), model=model,
                              capture=FakeCapture(frames=3))
            self.assertEqual(result["inference_samples"], 1)
            self.assertEqual(len(model.calls), 1)
            self.assertFalse(result["warmup_completed"])

    def test_model_failure_does_not_touch_camera(self):
        class BadModel(FakeModel):
            def predict(self, **kwargs):
                raise RuntimeError("broken warmup")
        fake_ultralytics = types.ModuleType("ultralytics")
        fake_ultralytics.YOLO = lambda _: BadModel()
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(sys.modules, {"ultralytics": fake_ultralytics}), \
                 patch("ai_vision.safety.live_fire_smoke.require_model_file"):
                with self.assertRaisesRegex(RuntimeError, "broken warmup"):
                    run_live(LiveConfig(output_dir=Path(root)),
                             capture_factory=lambda index: self.fail("camera opened"))
            saved = json.loads((Path(root) / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "ERROR")
            self.assertEqual(saved["camera_open_attempts"], 0)

    def test_cli_new_arguments_and_error_exit(self):
        with patch("ai_vision.safety.live_fire_smoke.run_live", return_value={
            "status": "CAMERA_OPEN_FAILED", "captured_frames": 0,
            "inference_samples": 0, "suspected_events": 0,
        }) as runner:
            exit_code = main(["--no-warmup", "--camera-retries", "0",
                              "--camera-retry-delay", "0"])
        self.assertEqual(exit_code, 1)
        c = runner.call_args.args[0]
        self.assertFalse(c.warmup)
        self.assertEqual(c.camera_retries, 0)
        self.assertEqual(c.camera_retry_delay, 0)


class SourceFailureTests(unittest.TestCase):
    def test_open_failure_retries_and_reports(self):
        first = BrokenOpen()
        next_caps = [BrokenOpen(), BrokenOpen()]
        with tempfile.TemporaryDirectory() as root:
            result = run_live(LiveConfig(output_dir=Path(root), camera_retries=2,
                                         camera_retry_delay=0), model=FakeModel(boxes=[]),
                              capture=first, capture_factory=lambda _: next_caps.pop(0))
            self.assertEqual(result["status"], "CAMERA_OPEN_FAILED")
            self.assertEqual(result["camera_reconnect_attempts"], 2)
            self.assertTrue(first.released)
            self.assertEqual(next_caps, [])
            self.assertTrue((Path(root) / "camera_health.json").exists())

    def test_camera_read_failure_recovers_without_clear(self):
        first = FakeCapture(frames=3)
        second = FakeCapture(frames=4)
        with tempfile.TemporaryDirectory() as root:
            current = [0]
            def clock():
                current[0] += .2
                return current[0]
            config = LiveConfig(output_dir=Path(root), max_frames=7, max_seconds=0,
                                window=2, min_hits=2, interval=.1,
                                camera_retries=1, camera_retry_delay=0)
            result = run_live(config, model=FakeModel(), capture=first,
                              capture_factory=lambda _: second, monotonic=clock)
            self.assertEqual(result["status"], "MAX_FRAMES")
            self.assertEqual(result["camera_read_failures"], 1)
            self.assertEqual(result["camera_reconnects"], 1)
            self.assertEqual(result["suspected_events"], 2)
            self.assertEqual(result["incident_transition_counts"]["CLEARED"], 0)
            self.assertEqual(result["incident_transition_counts"]["SESSION_ENDED"], 2)
            self.assertTrue(first.released)
            self.assertTrue(second.released)
            history = json.loads((Path(root) / "incident_history.json").read_text(encoding="utf-8"))
            ended = [x for x in history["transitions"] if x["status"] == "SESSION_ENDED"]
            self.assertEqual(ended[0]["reason"], "CAMERA_DISCONNECTED")
            self.assertEqual(ended[1]["reason"], "MAX_FRAMES")
            health = json.loads((Path(root) / "camera_health.json").read_text(encoding="utf-8"))
            self.assertEqual([c["status"] for c in health["changes"]],
                             ["CAMERA_READ_FAILED", "CAMERA_RECONNECTED"])

    def test_camera_read_failure_exhausts_retry_budget(self):
        initial = BrokenRead()
        replacements = [BrokenRead(), BrokenRead()]
        with tempfile.TemporaryDirectory() as root:
            result = run_live(LiveConfig(output_dir=Path(root), camera_retries=2,
                                         camera_retry_delay=0), model=FakeModel(boxes=[]),
                              capture=initial, capture_factory=lambda _: replacements.pop(0))
            self.assertEqual(result["status"], "CAMERA_READ_FAILED")
            self.assertEqual(result["camera_reconnect_attempts"], 2)
            self.assertEqual(result["camera_reconnects"], 0)
            self.assertEqual(result["inference_samples"], 0)
            self.assertTrue(initial.released)
            self.assertFalse(replacements)

    def test_video_eof_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "mock.mp4"
            file.write_bytes(b"mock")
            summary = run_live(LiveConfig(video_path=str(file), output_dir=Path(root) / "out",
                                          max_seconds=0), model=FakeModel(boxes=[]),
                               capture=FakeCapture(frames=5))
            self.assertEqual(summary["status"], "VIDEO_END")
            self.assertEqual(summary["camera_reconnects"], 0)

    def test_empty_video_is_read_failure(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "mock.mp4"
            file.write_bytes(b"mock")
            result = run_live(LiveConfig(video_path=str(file), output_dir=Path(root) / "out"),
                              model=FakeModel(boxes=[]), capture=FakeCapture(frames=0))
            self.assertEqual(result["status"], "VIDEO_READ_FAILED")

    def test_video_open_failure_does_not_retry_as_camera(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "mock.mp4"
            file.write_bytes(b"mock")
            result = run_live(LiveConfig(video_path=str(file), output_dir=Path(root) / "out"),
                              model=FakeModel(boxes=[]), capture=BrokenOpen())
            self.assertEqual(result["status"], "VIDEO_OPEN_FAILED")
            self.assertEqual(result["camera_reconnect_attempts"], 0)

    def test_healthy_camera_no_recovery_log(self):
        with tempfile.TemporaryDirectory() as root:
            config = LiveConfig(max_frames=4, output_dir=Path(root), max_seconds=0)
            current = [0]
            def clock():
                current[0] += .1
                return current[0]
            summary = run_live(config, model=FakeModel(boxes=[]), capture=FakeCapture(frames=6),
                               monotonic=clock)
            self.assertEqual(summary["status"], "MAX_FRAMES")
            self.assertIsNone(summary["camera_health_log"])
            self.assertFalse((Path(root) / "camera_health.json").exists())


if __name__ == "__main__":
    unittest.main()

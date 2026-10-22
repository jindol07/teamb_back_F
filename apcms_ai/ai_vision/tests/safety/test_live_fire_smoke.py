# D:/finalProjectB/back/apcms_ai/ai_vision/tests/safety/test_live_fire_smoke.py
"""실제 웹캠·모델·네트워크 없이 화재 의심 이벤트와 영상 자원 처리를 검증합니다."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from ai_vision.safety.live_fire_smoke import (
    FireSmokeWindow, LiveConfig, detect_frame, draw_detections, main, run_live,
)


# 1. 테스트용 YOLO 결과·카메라 (실제 모델·하드웨어가 필요 없습니다)
class Number:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class XY:
    def __init__(self, value):
        self.value = value

    def tolist(self):
        return self.value


class FakeBox:
    def __init__(self, kind=1, confidence=.80):
        self.cls = [Number(kind)]
        self.conf = [Number(confidence)]
        self.xyxy = [XY([2, 3, 22, 25])]


class FakeModel:
    names = {0: "smoke", 1: "fire"}

    def __init__(self, boxes=None):
        self.boxes = boxes if boxes is not None else [FakeBox()]
        self.calls = []

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        return [SimpleNamespace(boxes=self.boxes)]


class FakeCapture:
    def __init__(self, frames=7, fps=10):
        self.frames = [np.zeros((32, 40, 3), dtype=np.uint8) for _ in range(frames)]
        self.fps = fps
        self.released = False
        self.reads = 0

    def isOpened(self):
        return True

    def get(self, name):
        return self.fps

    def read(self):
        self.reads += 1
        return (True, self.frames.pop(0)) if self.frames else (False, None)

    def release(self):
        self.released = True


def fire(conf=.80):
    return {"class_name": "FIRE", "confidence": conf, "bbox": [1, 2, 10, 20]}


def smoke(conf=.75):
    return {"class_name": "SMOKE", "confidence": conf, "bbox": [1, 2, 10, 20]}


# 2. 탐지 설정과 연속 프레임 판단 검증
class DetectionWindowTests(unittest.TestCase):
    def test_defaults_and_reject_invalid_settings(self):
        config = LiveConfig()
        self.assertEqual((config.interval, config.conf, config.iou), (.5, .20, .45))
        for kwargs in ({"interval": 0}, {"conf": 1.0}, {"iou": float("nan")},
                       {"window": 2, "min_hits": 3}, {"camera_index": -1},
                       {"max_frames": -1}, {"cooldown": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                LiveConfig(**kwargs)

    def test_single_frame_does_not_trigger(self):
        window = FireSmokeWindow()
        self.assertEqual(window.update(0, [fire()]), [])
        self.assertEqual(window.update(.5, [fire()]), [])

    def test_three_hits_trigger_one_suspected_event(self):
        window = FireSmokeWindow()
        self.assertFalse(window.update(0, [fire(), fire(.3)]))
        self.assertFalse(window.update(.5, [fire()]))
        events = window.update(1, [fire(.7)])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "FIRE")
        self.assertEqual(events[0]["hits_in_window"], 3)
        self.assertEqual(events[0]["confidence"], .7)
        self.assertEqual(window.update(1.5, [fire()]), [])

    def test_clear_and_rearm_after_three_misses(self):
        window = FireSmokeWindow(cooldown=0)
        for i in range(3):
            events = window.update(i, [fire()])
        self.assertEqual(len(events), 1)
        for i in range(3, 6):
            self.assertEqual(window.update(i, []), [])
        emitted = []
        for i in range(6, 9):
            emitted.extend(window.update(i, [fire()]))
        self.assertEqual(len(emitted), 1)

    def test_cooldown_suppresses_repeated_events(self):
        window = FireSmokeWindow(cooldown=30)
        emitted = []
        for i in range(3):
            emitted += window.update(i, [fire()])
        for i in range(3, 6):
            emitted += window.update(i, [])
        for i in range(6, 9):
            emitted += window.update(i, [fire()])
        self.assertEqual(len(emitted), 1)

    def test_fire_and_smoke_are_independent(self):
        window = FireSmokeWindow()
        events = []
        for i in range(3):
            events.extend(window.update(i, [fire(), smoke()]))
        self.assertEqual({e["type"] for e in events}, {"FIRE", "SMOKE"})

    def test_invalid_or_reversed_timestamps_rejected(self):
        window = FireSmokeWindow()
        with self.assertRaises(ValueError):
            window.update(float("nan"), [])
        window.update(1, [])
        with self.assertRaises(ValueError):
            window.update(.5, [])


# 3. YOLO 결과 추출과 BGR 화면 표시 검증
class FrameTests(unittest.TestCase):
    def test_yolo_nms_parameters_and_result(self):
        model = FakeModel([FakeBox(1, .71), FakeBox(0, .85)])
        frame = np.zeros((32, 40, 3), dtype=np.uint8)
        detections, ms = detect_frame(model, frame)
        self.assertEqual([d["class_name"] for d in detections], ["FIRE", "SMOKE"])
        self.assertGreaterEqual(ms, 0)
        self.assertEqual(model.calls[0]["iou"], .45)
        self.assertEqual(model.calls[0]["conf"], .20)
        output = draw_detections(frame, detections)
        self.assertEqual(output.shape, frame.shape)
        self.assertEqual(int(frame.sum()), 0)
        self.assertGreater(int(output.sum()), 0)

    def test_empty_frame_rejected(self):
        with self.assertRaises(ValueError):
            detect_frame(FakeModel(), None)

    def test_unknown_class_not_counted(self):
        model = FakeModel([FakeBox(99, .9)])
        frame = np.zeros((32, 40, 3), dtype=np.uint8)
        detections, _ = detect_frame(model, frame)
        self.assertEqual(detections, [])


# 4. 영상 종료·이벤트 기록·카메라 해제 검증
class RunnerTests(unittest.TestCase):
    def test_video_interval_and_event_without_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "input.mp4"
            video.write_bytes(b"fake test data")
            output = Path(tmp) / "result"
            source = FakeCapture(frames=7, fps=10)
            model = FakeModel()
            config = LiveConfig(video_path=str(video), output_dir=output, interval=.2,
                                max_seconds=0)
            result = run_live(config, model=model, capture=source)
            self.assertEqual(result["status"], "VIDEO_END")
            self.assertEqual(result["captured_frames"], 7)
            self.assertEqual(result["inference_samples"], 4)
            self.assertEqual(result["suspected_events"], 1)
            self.assertTrue(source.released)
            self.assertEqual(len(model.calls), 4)
            self.assertEqual(list(output.glob("*.jpg")), [])
            saved = json.loads((output / "events.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["events"][0]["status"], "SUSPECTED")
            self.assertEqual(saved["events"][0]["source_seconds"], .4)
            self.assertIsNone(saved["events"][0]["evidence_image"])
            self.assertEqual(json.loads((output / "summary.json").read_text(encoding="utf-8"))["status"], "VIDEO_END")

    def test_evidence_saves_only_with_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "input.mp4"
            video.write_bytes(b"fake test data")
            output = Path(tmp) / "result"
            config = LiveConfig(video_path=str(video), output_dir=output,
                                save_evidence=True, interval=.1, max_seconds=0)
            with patch("ai_vision.safety.live_fire_smoke.cv2.imwrite", return_value=True) as write:
                report = run_live(config, model=FakeModel(), capture=FakeCapture(frames=3))
            self.assertEqual(report["suspected_events"], 1)
            write.assert_called_once()
            saved = json.loads((output / "events.json").read_text(encoding="utf-8"))
            self.assertTrue(saved["events"][0]["evidence_image"].endswith("fire.jpg"))

    def test_camera_respects_frame_limit_and_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = FakeCapture(frames=10)
            config = LiveConfig(max_frames=4, max_seconds=0, interval=.5, output_dir=Path(tmp))
            current = [0.0]
            def clock():
                current[0] += .2
                return current[0]
            result = run_live(config, model=FakeModel(), capture=cap, monotonic=clock)
            self.assertEqual(result["status"], "MAX_FRAMES")
            self.assertEqual(result["captured_frames"], 4)
            self.assertTrue(cap.released)

    def test_exception_releases_camera_and_marks_error(self):
        class FailingModel(FakeModel):
            def predict(self, **kwargs):
                raise RuntimeError("test error")
        with tempfile.TemporaryDirectory() as tmp:
            cap = FakeCapture()
            with self.assertRaisesRegex(RuntimeError, "test error"):
                run_live(LiveConfig(output_dir=Path(tmp)), model=FailingModel(), capture=cap)
            self.assertTrue(cap.released)
            saved = json.loads((Path(tmp) / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual((saved["status"], saved["error_type"]), ("ERROR", "RuntimeError"))

    def test_missing_video_path_does_not_open_camera(self):
        with self.assertRaises(FileNotFoundError):
            run_live(LiveConfig(video_path="/unlikely_nonexistent__xxxx.mp4"), model=FakeModel())

    def test_help_does_not_load_models_or_camera(self):
        with self.assertRaises(SystemExit) as result:
            main(["--help"])
        self.assertEqual(result.exception.code, 0)


if __name__ == "__main__":
    unittest.main()

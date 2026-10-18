# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_tracked_passages.py

import builtins
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic, read_json
from ai_vision.recognition.recognize_tracked_passages import run, load_tracking_inputs, select_samples


class TrackedPassageTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.source = self.root / "video.mp4"
        self.source.touch()
        self.tracking = self.root / "tracking"
        self.tracking.mkdir()
        write_json_atomic(self.tracking / "summary.json", {
            "source": str(self.source), "http_enabled": False, "counts": {"UP": 0, "DOWN": 0}})
        for name in ("crossings.jsonl", "observations.jsonl"):
            (self.tracking / name).write_text("", encoding="utf-8")

    def test_no_passage_does_not_import_models_or_cv2(self):
        # 빈 구간을 처리할 때 불필요한 모델 초기화를 수행하지 않아야 함
        original = builtins.__import__
        def guard(name, *args, **kwargs):
            if name == "cv2" or name.endswith("recognizer"):
                raise AssertionError("불필요한 모델 또는 영상 초기화")
            return original(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=guard):
            run(self.tracking, self.root / "ocr")
        self.assertEqual(read_json(self.root / "ocr/summary.json")["processed_tracks"], 0)

    def test_count_mismatch_rejected_before_models(self):
        write_json_atomic(self.tracking / "summary.json", {
            "source": str(self.source), "http_enabled": False, "counts": {"DOWN": 1}})
        with self.assertRaisesRegex(ValueError, "기록 수"):
            load_tracking_inputs(self.tracking)

    def test_old_output_is_not_overwritten(self):
        output = self.root / "old"
        output.mkdir()
        with self.assertRaises(FileExistsError):
            run(self.tracking, output)

    def test_invalid_sample_options_or_boxes_rejected(self):
        with self.assertRaises(ValueError):
            select_samples([], 1, limit=0)
        with self.assertRaises(ValueError):
            select_samples([{"frame_index": 1, "video_seconds": 0, "box": [4, 4, 1, 1]}], 1)


if __name__ == "__main__":
    unittest.main()

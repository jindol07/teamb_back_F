# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_tracked_passages.py

import builtins
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock
import json
import numpy as np

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic, read_json
from ai_vision.recognition.recognize_tracked_passages import run, load_tracking_inputs, select_samples


class TrackedPassageTests(unittest.TestCase):
    def test_failed_samples_keep_exact_vehicle_crop_without_changing_consensus(self):
        import cv2
        # 미탐지와 OCR 실패를 구분할 수 있도록 실제 입력 픽셀과 결과 연결을 검사합니다.
        frame = np.arange(40 * 50 * 3, dtype=np.uint8).reshape(40, 50, 3)
        rows = [{'frame_index': i, 'video_seconds': i * .3, 'box': [5, 6, 35, 36]}
                for i in range(3)]
        event = {'track_id': 1, 'direction': 'DOWN', 'video_seconds': .3}
        for kind in ('NOT_DETECTED', 'REVIEW', 'KOREAN_VALID'):
            with self.subTest(kind=kind):
                capture = Mock()
                capture.read.return_value = (True, frame)
                plate = None if kind == 'NOT_DETECTED' else {'box': [1, 1, 20, 15], 'confidence': .9}
                output = self.root / kind
                with patch('ai_vision.recognition.recognize_tracked_passages.load_tracking_inputs',
                           return_value=({'source': str(self.source)}, [event], [event], {1: rows})), \
                     patch('cv2.VideoCapture', return_value=capture), \
                     patch('ai_vision.recognition.recognizer.detect_best_plate', return_value=plate), \
                     patch('ai_vision.recognition.recognizer.recognize_plate',
                           return_value={'plate_number': '30고5957', 'plate_type': kind}):
                    run(self.tracking, output)
                result = json.loads((output / 'passages.jsonl').read_text(encoding='utf-8'))
                self.assertEqual(len(result['samples']), 3)
                for sample in result['samples']:
                    if kind == 'KOREAN_VALID':
                        self.assertNotIn('vehicle_review_image', sample)
                    else:
                        image = cv2.imread(str(output / sample['vehicle_review_image']))
                        np.testing.assert_array_equal(image, frame[6:36, 5:35])
                expected = 'CONFIRMED' if kind == 'KOREAN_VALID' else 'NO_VALID_KOREAN_PLATE'
                self.assertEqual(result['plate_consensus']['status'], expected)

    def test_failed_review_image_write_is_not_reported_as_completed(self):
        row = {'frame_index': 0, 'video_seconds': 0, 'box': [0, 0, 20, 20]}
        event = {'track_id': 1, 'direction': 'DOWN', 'video_seconds': 0}
        capture = Mock()
        capture.read.return_value = (True, np.zeros((20, 20, 3), dtype=np.uint8))
        output = self.root / 'write_failure'
        with patch('ai_vision.recognition.recognize_tracked_passages.load_tracking_inputs',
                   return_value=({'source': str(self.source)}, [event], [event], {1: [row]})), \
             patch('cv2.VideoCapture', return_value=capture), patch('cv2.imwrite', return_value=False), \
             patch('ai_vision.recognition.recognizer.detect_best_plate', return_value=None):
            with self.assertRaises(OSError):
                run(self.tracking, output)
        capture.release.assert_called_once()
        self.assertFalse((output / 'summary.json').exists())

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

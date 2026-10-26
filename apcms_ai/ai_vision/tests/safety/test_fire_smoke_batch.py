# D:/finalProjectB/back/apcms_ai/ai_vision/tests/safety/test_fire_smoke_batch.py
"""모델 실행 없이 일괄 화재 감지 결과의 계산 로직만 검증합니다."""

import json
import tempfile
import unittest
from pathlib import Path

from ai_vision.safety.fire_smoke_batch import (
    analyze_detections, calculate_iou, is_case_passed, load_manifest,
    parse_levels, summarize,
)


# 1. 경계 조건 테스트
class FireSmokeBatchTests(unittest.TestCase):
    # 1-1. 신뢰도와 IoU 입력이 잘못된 경우 분석을 시작하지 않습니다.
    def test_parse_levels(self):
        self.assertEqual(parse_levels("0.15,0.2,0.25", "conf"), [0.15, 0.2, 0.25])
        for text in ("0", "1", "0.3,0.3", "oops", "NaN", "0.1,"):
            with self.subTest(value=text), self.assertRaises(ValueError):
                parse_levels(text, "conf")

    # 1-2. IoU는 같은 박스 1, 겹치지 않는 박스 0이어야 합니다.
    def test_iou(self):
        self.assertEqual(calculate_iou([0, 0, 10, 10], [0, 0, 10, 10]), 1.0)
        self.assertEqual(calculate_iou([0, 0, 10, 10], [20, 20, 30, 30]), 0.0)
        self.assertAlmostEqual(calculate_iou([0, 0, 10, 10], [5, 5, 15, 15]), 25 / 175)

    # 1-3. 같은 클래스의 겹친 박스만 중복 후보로 계산합니다.
    def test_analyze_detections(self):
        boxes = [
            {"class_name": "FIRE", "confidence": 0.35,
             "bbox": [0, 0, 100, 100], "box_area_ratio": 0.75},
            {"class_name": "FIRE", "confidence": 0.30,
             "bbox": [10, 10, 90, 90], "box_area_ratio": 0.5},
            {"class_name": "SMOKE", "confidence": 0.28,
             "bbox": [0, 0, 100, 100], "box_area_ratio": 0.75},
        ]
        value = analyze_detections(boxes)
        self.assertEqual(value["fire_count"], 2)
        self.assertEqual(value["smoke_count"], 1)
        self.assertEqual(value["overlap_pairs_iou_05"], 1)
        self.assertEqual(value["max_box_area_ratio"], .75)

    # 1-4. 연기만 있는 이미지가 FIRE로 감지되면 검토가 필요합니다.
    def test_case_labels(self):
        self.assertTrue(is_case_passed("FIRE", 1, 0))
        self.assertTrue(is_case_passed("SMOKE", 0, 1))
        self.assertTrue(is_case_passed("NORMAL", 0, 0))
        self.assertFalse(is_case_passed("SMOKE", 1, 1))
        self.assertFalse(is_case_passed("NORMAL", 0, 1))

    # 1-5. 테스트 라벨은 반드시 실존 이미지와 지정된 정답을 사용합니다.
    def test_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "test.jpg").write_bytes(b"placeholder")
            (root / "labels.json").write_text(
                json.dumps([{"file": "test.jpg", "expected": "SMOKE"}]), encoding="utf-8")
            self.assertEqual(load_manifest(root / "labels.json")[0]["expected"], "SMOKE")
            (root / "labels.json").write_text(
                json.dumps([{"file": "../test.jpg", "expected": "SMOKE"}]), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_manifest(root / "labels.json")

    # 1-6. 설정별 요약에서 정상 사진 오탐을 구분합니다.
    def test_summary(self):
        base = {"conf": .15, "iou": .45, "inference_ms": 40,
                "overlap_pairs_iou_05": 0, "max_box_area_ratio": .1}
        rows = [
            {**base, "expected": "FIRE", "fire_count": 1, "smoke_count": 0, "case_passed": True},
            {**base, "expected": "SMOKE", "fire_count": 0, "smoke_count": 0, "case_passed": False},
            {**base, "expected": "NORMAL", "fire_count": 1, "smoke_count": 0, "case_passed": False},
        ]
        summary = summarize(rows)[0]
        self.assertEqual(summary["passed"], 1)
        self.assertEqual(summary["smoke_misses"], 1)
        self.assertEqual(summary["normal_false_alarms"], 1)


if __name__ == "__main__":
    unittest.main()

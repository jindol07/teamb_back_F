# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_aws_recognition_cases.py

"""공유받은 AWS 결과의 분류·보류 규칙을 재현합니다. AWS 영상 추론 재검증은 아닙니다."""

import copy
import unittest
from unittest.mock import Mock, patch

import numpy as np
from ai_vision.recognition import recognizer
from ai_vision.recognition.plate_review import plate_review_reasons
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.vehicle_live_candidate import create_live_candidate
from ai_vision.recognition.vehicle_delivery_flow import VehicleDeliveryFlow
from ai_vision.tests.recognition.test_vehicle_live_candidate import live_passage


class AWSRecognitionCasesTests(unittest.TestCase):
    def test_shared_plate_formats_and_review_reason(self):
        for text, kind, reasons in (("91소6408", "KOREAN_VALID", []),
                                    ("10-1557", "REVIEW", ["KOREAN_CHARACTER_NOT_FOUND"]),
                                    ("AB1234", "FOREIGN_OR_OTHER", ["NON_KOREAN_PLATE_FORMAT"]),
                                    ("", "OCR_FAILED", ["NO_OCR_TEXT"])):
            with self.subTest(text=text):
                self.assertEqual(recognizer.classify_plate_format(text), kind)
                self.assertEqual(plate_review_reasons(text, kind), reasons)

    def test_missing_character_is_not_invented_after_retry(self):
        with patch.object(recognizer, "run_paddleocr", return_value="10-1557"), \
                patch.object(recognizer, "retry_ocr", return_value=("10-1557", "REVIEW")):
            result = recognizer.recognize_plate(np.zeros((20, 80, 3), dtype=np.uint8))
        self.assertEqual((result["plate_number"], result["plate_type"]), ("10-1557", "REVIEW"))
        self.assertEqual(result["review_reasons"], ["KOREAN_CHARACTER_NOT_FOUND"])

    def test_non_ascii_digits_do_not_pass_korean_format(self):
        for text in ("９１소６４０８", "٩١소٦٤٠٨"):
            self.assertEqual(recognizer.classify_plate_format(text), "REVIEW")
            self.assertEqual(recognizer.cleanup_plate_text(text), text)

    def test_repeated_incomplete_or_foreign_text_never_creates_http_candidate(self):
        # 두 프레임에서 반복돼도 한국 번호판 형식이 아니면 확정·송신하지 않습니다.
        for text, kind in (("10-1557", "REVIEW"), ("AB1234", "FOREIGN_OR_OTHER")):
            row = copy.deepcopy(live_passage())
            for sample in row["samples"]:
                sample.update(plate_number=text, plate_type=kind)
            row["plate_consensus"] = summarize_plate_samples(row["samples"])
            candidate = create_live_candidate(row, "TEST_GATE", "ENTRY", "2020-01-01T00:00:01Z")
            client = Mock()
            client.enabled = True
            flow = VehicleDeliveryFlow(client)
            self.assertEqual(flow.process("aws_regression", candidate)["decision"], "BLOCKED")
            self.assertIsNone(candidate["payload"])
            client.send.assert_not_called()

    def test_no_vehicle_response_and_undetected_plate_reason(self):
        with patch.object(recognizer, "detect_vehicles", return_value=([], False)), \
                patch.object(recognizer, "detect_best_plate") as detect:
            self.assertEqual(recognizer.recognize_image(np.zeros((30, 30, 3), dtype=np.uint8))["vehicle_count"], 0)
        detect.assert_not_called()
        self.assertEqual(plate_review_reasons("", "NOT_DETECTED"), ["PLATE_NOT_DETECTED"])
        self.assertEqual(plate_review_reasons("", "CROP_FAILED"), ["PLATE_CROP_FAILED"])

    def test_vehicle_response_includes_review_reason_without_changing_ocr_text(self):
        vehicles = [{"box": (0, 0, 100, 100), "class_name": "car", "confidence": .9}]
        with patch.object(recognizer, "detect_vehicles", return_value=(vehicles, False)), \
                patch.object(recognizer, "detect_best_plate", return_value={"box": (10, 10, 90, 30), "confidence": .8}), \
                patch.object(recognizer, "run_paddleocr", return_value="10-1557"), \
                patch.object(recognizer, "retry_ocr", return_value=("10-1557", "REVIEW")):
            result = recognizer.recognize_image(np.zeros((100, 100, 3), dtype=np.uint8))
        self.assertEqual(result["vehicle_count"], 1)
        row = result["vehicles"][0]
        self.assertEqual(row["plate_number"], "10-1557")
        self.assertEqual(row["review_reasons"], ["KOREAN_CHARACTER_NOT_FOUND"])

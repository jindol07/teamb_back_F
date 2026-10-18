# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_result_validation.py

import unittest
from ai_vision.recognition.result_validation import public_passage, validate_summary


class ResultValidationTests(unittest.TestCase):
    def test_summary_counts_and_coverage_must_agree(self):
        result = {"kind": "pipeline", "total_crossings": 2, "ocr_processed": 1,
                  "crossing_counts": {"DOWN": 2}, "plate_status_counts": {"CONFLICT": 1}, "ocr_coverage": "PARTIAL"}
        validate_summary(result)
        for changes in ({"crossing_counts": {"DOWN": 3}}, {"plate_status_counts": {}},
                        {"ocr_coverage": "ALL_RECORDED_TRACKS"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_summary({**result, **changes})

    def test_ocr_count_order(self):
        with self.assertRaises(ValueError):
            validate_summary({"kind": "ocr", "confirmed_plates": 2, "processed_tracks": 1, "crossings_in_run": 1})

    def test_malformed_nested_samples_raise_validation_error(self):
        row = {"http_enabled": False, "record_type": "LOCAL_TRACKED_PASSAGE", "track_id": 1,
               "screen_direction": "DOWN", "crossing_video_seconds": 1}
        for changes in ({"samples": [None], "plate_consensus": {}},
                        {"samples": [], "plate_consensus": []}, {"samples": None, "plate_consensus": {}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                public_passage({**row, **changes})

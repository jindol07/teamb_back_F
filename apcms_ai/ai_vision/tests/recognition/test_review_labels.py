# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_review_labels.py

import unittest
from ai_vision.recognition.review_labels import template_rows, validate_labels


class ReviewLabelsTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {"run_id": "demo", "snapshot_sha256": "a" * 64, "items": [
            {"track_id": 1, "screen_direction": "DOWN", "video_seconds": 1.2,
             "plate_status": "CONFIRMED", "plate_number": "91소6408"}]}
        self.rows = template_rows(self.snapshot)

    def test_ai_prediction_is_never_prefilled_as_truth(self):
        self.assertEqual(self.rows[0]["expected_plate"], "")
        self.assertEqual(self.rows[0]["review_status"], "PENDING")
        self.assertEqual(validate_labels(self.snapshot, self.rows), self.rows)

    def test_readable_korean_plate_is_normalized(self):
        row = {**self.rows[0], "review_status": "VERIFIED_PLATE", "expected_plate": "91 소 6408"}
        self.assertEqual(validate_labels(self.snapshot, [row])[0]["expected_plate"], "91소6408")

    def test_invalid_truth_and_fixed_column_edits_are_rejected(self):
        for change in ({"expected_plate": "91소6408"}, {"review_status": "OK"},
                       {"review_status": "VERIFIED_PLATE", "expected_plate": "ABC123"},
                       {"snapshot_sha256": "b" * 64}, {"video_seconds": "2"},
                       {"predicted_plate": "12가3456"}, {"note": "x" * 2001}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_labels(self.snapshot, [{**self.rows[0], **change}])

    def test_missing_duplicate_and_unknown_tracks_are_rejected(self):
        for rows in ([], self.rows * 2, [{**self.rows[0], "track_id": "99"}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_labels(self.snapshot, rows)

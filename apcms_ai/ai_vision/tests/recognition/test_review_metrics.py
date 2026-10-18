# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_review_metrics.py

import unittest
from ai_vision.recognition.review_labels import template_rows
from ai_vision.recognition.review_metrics import build_report


class ReviewMetricsTests(unittest.TestCase):
    def snapshot(self, statuses):
        return {"run_id": "demo", "snapshot_sha256": "a" * 64,
                "overview": {"total_crossings": 20, "ocr_processed": len(statuses)},
                "items": [{"track_id": i, "screen_direction": "DOWN", "video_seconds": i,
                           "plate_status": status, "plate_number": "91소6408" if status == "CONFIRMED" else ""}
                          for i, status in enumerate(statuses)]}

    def test_pending_and_empty_data_have_no_accuracy(self):
        for snapshot in (self.snapshot([]), self.snapshot(["CONFIRMED"])):
            report = build_report(snapshot, template_rows(snapshot))
            self.assertIsNone(report["exact_match_rate_on_verified_plates"])
        self.assertIsNone(build_report(self.snapshot([]), [])["reviewed_fraction"])

    def test_matches_wrong_and_unconfirmed_have_explicit_denominator(self):
        snapshot = self.snapshot(["CONFIRMED", "CONFIRMED", "CONFLICT", "CONFIRMED", "CONFIRMED", "CONFIRMED"])
        rows = template_rows(snapshot)
        for i, plate in enumerate(("91소6408", "12가3456", "91소6408")):
            rows[i].update(review_status="VERIFIED_PLATE", expected_plate=plate)
        rows[3]["review_status"] = "UNREADABLE"
        rows[4]["review_status"] = "NO_PLATE"
        report = build_report(snapshot, rows)
        self.assertEqual(report["verified_plate_rows"], 3)
        self.assertEqual(report["exact_match_rate_on_verified_plates"], 1 / 3)
        self.assertEqual(report["wrong_confirmed_plates"], 1)
        self.assertEqual(report["unconfirmed_on_verified_plate"], 1)
        self.assertEqual(report["confirmed_on_no_plate"], 1)
        self.assertFalse(report["review_complete"])
        self.assertEqual(report["source_total_crossings"], 20)

    def test_unreadable_is_reviewed_but_not_readable_ground_truth(self):
        snapshot = self.snapshot(["CONFIRMED"])
        rows = template_rows(snapshot)
        rows[0]["review_status"] = "UNREADABLE"
        report = build_report(snapshot, rows)
        self.assertTrue(report["review_complete"])
        self.assertEqual(report["reviewed_fraction"], 1)
        self.assertIsNone(report["exact_match_rate_on_verified_plates"])

    def test_foreign_plate_is_outside_korean_evaluation_scope(self):
        snapshot = self.snapshot(["NO_VALID_KOREAN_PLATE"])
        rows = template_rows(snapshot)
        rows[0]["review_status"] = "OUT_OF_SCOPE"
        report = build_report(snapshot, rows)
        self.assertTrue(report["review_complete"])
        self.assertEqual(report["review_status_counts"]["OUT_OF_SCOPE"], 1)
        self.assertIsNone(report["exact_match_rate_on_verified_plates"])

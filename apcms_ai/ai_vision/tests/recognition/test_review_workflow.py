# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_review_workflow.py

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.review_workflow import create_template, create_report


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.catalog = ResultCatalog(self.root / "runs")
        self.folder = self.catalog.root / "ocr"
        write_json_atomic(self.folder / "summary.json", {
            "http_enabled": False, "crossings_in_run": 3, "processed_tracks": 1, "confirmed_plates": 0})
        self.row = {"http_enabled": False, "record_type": "LOCAL_TRACKED_PASSAGE", "track_id": 1,
                    "screen_direction": "DOWN", "crossing_video_seconds": 1,
                    "samples": [], "plate_consensus": summarize_plate_samples([])}
        (self.folder / "passages.jsonl").write_text(json.dumps(self.row), encoding="utf-8")
        self.labels = self.root / "review.csv"
        self.output = self.root / "report.json"

    def test_pending_roundtrip_preserves_originals_and_produces_no_accuracy(self):
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        self.assertEqual(create_template(self.catalog, "ocr", self.labels), 1)
        self.assertTrue(self.labels.read_bytes().startswith(b"\xef\xbb\xbf"))
        report = create_report(self.catalog, "ocr", self.labels, self.output)
        self.assertEqual(report["review_status_counts"]["PENDING"], 1)
        self.assertIsNone(report["exact_match_rate_on_verified_plates"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir()})
        self.assertNotIn(str(self.root), self.output.read_text(encoding="utf-8"))

    def test_manual_truth_is_compared_with_prediction(self):
        create_template(self.catalog, "ocr", self.labels)
        with self.labels.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields, rows = reader.fieldnames, list(reader)
        rows[0].update(review_status="VERIFIED_PLATE", expected_plate="91소6408")
        with self.labels.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        report = create_report(self.catalog, "ocr", self.labels, self.output)
        self.assertEqual(report["unconfirmed_on_verified_plate"], 1)
        self.assertEqual(report["exact_match_rate_on_verified_plates"], 0)

    def test_changed_predictions_reject_stale_labels_without_output(self):
        create_template(self.catalog, "ocr", self.labels)
        self.row["crossing_video_seconds"] = 2
        (self.folder / "passages.jsonl").write_text(json.dumps(self.row), encoding="utf-8")
        with self.assertRaises(ValueError):
            create_report(self.catalog, "ocr", self.labels, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_and_original_outputs_cannot_be_overwritten(self):
        create_template(self.catalog, "ocr", self.labels)
        before = self.labels.read_bytes()
        with self.assertRaises(FileExistsError):
            create_template(self.catalog, "ocr", self.labels)
        self.assertEqual(self.labels.read_bytes(), before)
        with self.assertRaises(ValueError):
            create_template(self.catalog, "ocr", self.folder / "review.csv")

    def test_publication_failure_leaves_no_partial_or_temporary_file(self):
        with patch("ai_vision.recognition.review_workflow.os.link", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                create_template(self.catalog, "ocr", self.labels)
        self.assertFalse(self.labels.exists())
        self.assertEqual(list(self.root.glob(".review-*.tmp")), [])

    def test_bad_headers_encoding_and_size_are_rejected(self):
        for data in (b"wrong,columns\n1,2\n", b"\xff\xfe", b"x" * (8 * 1024 * 1024 + 1)):
            self.labels.write_bytes(data)
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                create_report(self.catalog, "ocr", self.labels, self.output)
            self.assertFalse(self.output.exists())

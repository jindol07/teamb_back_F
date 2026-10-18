# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_results_catalog.py

import tempfile
import json
import unittest
from pathlib import Path

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.plate_consensus import summarize_plate_samples


class ResultsCatalogTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.catalog = ResultCatalog(self.root)
        write_json_atomic(self.root / "run_a/summary.json", {
            "source": "private/local/video.mp4", "http_enabled": False, "counts": {"DOWN": 2, "UP": 0}})

    def test_listing_excludes_private_paths(self):
        result = self.catalog.list_runs()
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["total_crossings"], 2)
        self.assertNotIn("private", str(result))

    def test_path_traversal_and_external_files_rejected(self):
        for name in ["../other", "..", "a/b", "C:\\secret", "a.json"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.catalog.folder(name)
        with self.assertRaises(ValueError):
            self.catalog.safe_file(self.root.parent / "external.json")

    def test_failed_run_has_no_raw_error_message(self):
        write_json_atomic(self.root / "failed/pipeline.json", {
            "status": "FAILED", "stage": "ocr", "http_enabled": False, "error": "secret path"})
        result = self.catalog.overview("failed")
        self.assertEqual(result["status"], "FAILED")
        self.assertNotIn("secret", str(result))

    def test_corrupt_run_does_not_hide_healthy_runs(self):
        bad = self.root / "bad"
        bad.mkdir()
        (bad / "summary.json").write_text("{", encoding="utf-8")
        result = self.catalog.list_runs(limit=1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["items"][0]["status"], "UNAVAILABLE")
        self.assertEqual(self.catalog.list_runs(offset=1)["items"][0]["run_id"], "run_a")

    def test_no_ocr_is_not_an_empty_success(self):
        with self.assertRaises(FileNotFoundError):
            self.catalog.passages("run_a")
        with self.assertRaises(ValueError):
            self.catalog.list_runs(limit=101)

    def test_inconsistent_pipeline_summary_is_unavailable(self):
        write_json_atomic(self.root / "bad_sum/summary.json", {
            "http_enabled": False, "total_crossings": 2, "ocr_processed": 1, "ocr_not_processed": 1,
            "crossing_counts": {"DOWN": 1}, "plate_status_counts": {"CONFLICT": 1}, "ocr_coverage": "PARTIAL"})
        with self.assertRaises(ValueError):
            self.catalog.overview("bad_sum")

    def test_missing_result_rows_are_not_empty_success(self):
        write_json_atomic(self.root / "ocr/summary.json", {
            "http_enabled": False, "crossings_in_run": 1, "processed_tracks": 1, "confirmed_plates": 0})
        (self.root / "ocr/passages.jsonl").write_text("", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.catalog.passages("ocr")

    def test_review_snapshot_is_order_independent_but_tracks_prediction_changes(self):
        write_json_atomic(self.root / "ocr/summary.json", {
            "http_enabled": False, "crossings_in_run": 2, "processed_tracks": 2, "confirmed_plates": 0})
        rows = [{"http_enabled": False, "record_type": "LOCAL_TRACKED_PASSAGE", "track_id": i,
                 "screen_direction": "DOWN", "crossing_video_seconds": i,
                 "samples": [], "plate_consensus": summarize_plate_samples([])} for i in (1, 2)]
        path = self.root / "ocr/passages.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        first = self.catalog.review_snapshot("ocr")
        path.write_text("\n".join(json.dumps(row) for row in reversed(rows)), encoding="utf-8")
        self.assertEqual(self.catalog.review_snapshot("ocr"), first)
        rows[0]["screen_direction"] = "UP"
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        self.assertNotEqual(self.catalog.review_snapshot("ocr")["snapshot_sha256"], first["snapshot_sha256"])

    def test_tracking_only_run_cannot_supply_ocr_review_subjects(self):
        with self.assertRaises(FileNotFoundError):
            self.catalog.review_snapshot("run_a")

    def test_review_source_rejects_unfinished_and_external_pipeline(self):
        write_json_atomic(self.root / "pending/pipeline.json", {
            "http_enabled": False, "status": "RUNNING", "stage": "ocr"})
        with self.assertRaises(ValueError):
            self.catalog.review_source("pending")
        write_json_atomic(self.root / "outside/summary.json", {
            "http_enabled": False, "total_crossings": 0, "ocr_processed": 0, "ocr_not_processed": 0,
            "crossing_counts": {}, "plate_status_counts": {}, "ocr_coverage": "ALL_RECORDED_TRACKS",
            "ocr_dir": str(self.root.parent / "external")})
        with self.assertRaises(ValueError):
            self.catalog.review_source("outside")


if __name__ == "__main__":
    unittest.main()

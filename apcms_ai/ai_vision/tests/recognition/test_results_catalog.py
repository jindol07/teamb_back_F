# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_results_catalog.py

import tempfile
import unittest
from pathlib import Path

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.results_catalog import ResultCatalog


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


if __name__ == "__main__":
    unittest.main()

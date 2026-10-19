# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_review_bundle.py

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.review_bundle import create_bundle


class ReviewBundleTests(unittest.TestCase):
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
            "http_enabled": False, "crossings_in_run": 1, "processed_tracks": 1, "confirmed_plates": 0})
        samples = [{"frame_index": 5, "video_seconds": 1, "plate_number": "ABC", "plate_type": "FOREIGN_OR_OTHER"}]
        row = {"http_enabled": False, "record_type": "LOCAL_TRACKED_PASSAGE", "track_id": 7,
               "screen_direction": "DOWN", "crossing_video_seconds": 1,
               "samples": samples, "plate_consensus": summarize_plate_samples(samples)}
        (self.folder / "passages.jsonl").write_text(json.dumps(row), encoding="utf-8")
        Image.new("RGB", (20, 10)).save(self.folder / "id_7_frame_5_plate.jpg")
        self.output = self.root / "review.html"

    def test_real_bundle_has_image_and_no_paths_models_or_source_writes(self):
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        loaded = "ai_vision.recognition.recognizer" in sys.modules
        report = create_bundle(self.catalog, "ocr", self.output)
        self.assertEqual(report["image_count"], 1)
        self.assertEqual(report["shown"], 1)
        html = self.output.read_text(encoding="utf-8")
        self.assertIn("data:image/jpeg;base64,", html)
        self.assertNotIn(str(self.root), html)
        self.assertEqual("ai_vision.recognition.recognizer" in sys.modules, loaded)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir()})

    def test_empty_page_preserves_total_and_invalid_pagination_fails(self):
        report = create_bundle(self.catalog, "ocr", self.output, offset=5)
        self.assertEqual((report["total"], report["shown"], report["image_count"]), (1, 0, 0))
        for offset, limit in ((-1, 20), (0, 101)):
            with self.assertRaises(ValueError):
                create_bundle(self.catalog, "ocr", self.root / "bad.html", offset, limit)

    def test_existing_output_and_source_folder_are_preserved(self):
        self.output.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            create_bundle(self.catalog, "ocr", self.output)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "keep")
        with self.assertRaises(ValueError):
            create_bundle(self.catalog, "ocr", self.folder / "review.html")

    def test_changing_snapshot_stops_before_output(self):
        original = self.catalog.review_snapshot("ocr")
        with patch.object(self.catalog, "review_snapshot", side_effect=[original, {**original, "snapshot_sha256": "changed"}]):
            with self.assertRaises(ValueError):
                create_bundle(self.catalog, "ocr", self.output)
        self.assertFalse(self.output.exists())

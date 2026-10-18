# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_review_assets.py

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.review_assets import load_evidence, read_plate_image


class ReviewAssetsTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.catalog = ResultCatalog(self.root)
        self.folder = self.root / "ocr"
        write_json_atomic(self.folder / "summary.json", {
            "http_enabled": False, "crossings_in_run": 1, "processed_tracks": 1, "confirmed_plates": 0})
        samples = [{"frame_index": 5, "video_seconds": 1, "plate_number": "foreign", "plate_type": "FOREIGN_OR_OTHER"}]
        self.row = {"http_enabled": False, "record_type": "LOCAL_TRACKED_PASSAGE", "track_id": 7,
                    "screen_direction": "DOWN", "crossing_video_seconds": 1,
                    "samples": samples, "plate_consensus": summarize_plate_samples(samples)}
        self.log = self.folder / "passages.jsonl"
        self.log.write_text(json.dumps(self.row), encoding="utf-8")
        self.picture = self.folder / "id_7_frame_5_plate.jpg"

    def test_missing_image_is_explicit_and_jpeg_is_embedded(self):
        snapshot = self.catalog.review_snapshot("ocr")
        self.assertIsNone(load_evidence(self.catalog, "ocr", snapshot)[7][0]["image"])
        Image.new("RGB", (20, 10), "white").save(self.picture)
        image = load_evidence(self.catalog, "ocr", snapshot)[7][0]["image"]
        self.assertEqual(image["byte_size"], self.picture.stat().st_size)
        self.assertEqual(len(image["sha256"]), 64)
        self.assertNotIn(str(self.root), str(image))

    def test_corrupt_or_wrong_format_image_is_rejected(self):
        for raw in (b"not a jpeg", b"\xff\xd8broken"):
            self.picture.write_bytes(raw)
            with self.assertRaises(ValueError):
                read_plate_image(self.catalog, self.folder, 7, 5)
        Image.new("RGB", (20, 10)).save(self.picture, format="PNG")
        with self.assertRaises(ValueError):
            read_plate_image(self.catalog, self.folder, 7, 5)

    def test_external_image_and_size_limits_are_rejected(self):
        Image.new("RGB", (20, 10)).save(self.picture)
        with patch.object(self.catalog, "safe_file", return_value=self.root / "other.jpg"):
            with self.assertRaises(ValueError):
                read_plate_image(self.catalog, self.folder, 7, 5)
        with patch("ai_vision.recognition.review_assets.MAX_IMAGE_BYTES", 1):
            with self.assertRaises(ValueError):
                read_plate_image(self.catalog, self.folder, 7, 5)
        with patch("ai_vision.recognition.review_assets.MAX_TOTAL_IMAGE_BYTES", 1):
            with self.assertRaises(ValueError):
                load_evidence(self.catalog, "ocr", self.catalog.review_snapshot("ocr"))

    def test_selected_page_does_not_load_other_images_but_still_checks_rows(self):
        snapshot = self.catalog.review_snapshot("ocr")
        self.picture.write_bytes(b"broken")
        self.assertEqual(load_evidence(self.catalog, "ocr", snapshot, []), {})
        with self.assertRaises(ValueError):
            load_evidence(self.catalog, "ocr", snapshot, [99])
        self.log.write_text(json.dumps({**self.row, "screen_direction": "UP"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_evidence(self.catalog, "ocr", snapshot, [])

    def test_duplicate_or_missing_tracks_are_rejected(self):
        snapshot = self.catalog.review_snapshot("ocr")
        for data in ("", json.dumps(self.row) + "\n" + json.dumps(self.row)):
            self.log.write_text(data, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_evidence(self.catalog, "ocr", snapshot)

    def test_truncated_jpeg_and_invalid_image_identifiers_are_rejected(self):
        Image.new("RGB", (20, 10)).save(self.picture)
        self.picture.write_bytes(self.picture.read_bytes()[:-30])
        with self.assertRaises(ValueError):
            read_plate_image(self.catalog, self.folder, 7, 5)
        for track, frame in ((True, 5), (7, -1), ("../other", 5)):
            with self.assertRaises(ValueError):
                read_plate_image(self.catalog, self.folder, track, frame)

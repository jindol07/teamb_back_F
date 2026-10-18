# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_passage_audit.py

import json
import tempfile
import unittest
from pathlib import Path
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.passage_audit import audit_passages
from ai_vision.tests.recognition.test_tracking_audit import save_tracking


def save_ocr(root, tracking):
    folder = root / "ocr"
    write_json_atomic(folder / "summary.json", {
        "http_enabled": False, "source_run": str(tracking.resolve()), "source_video": "D:/test/video.mp4",
        "crossings_in_run": 1, "processed_tracks": 1, "confirmed_plates": 0})
    samples = [{"frame_index": 12, "video_seconds": 1.2, "plate_number": "", "plate_type": "NOT_DETECTED"}]
    row = {"http_enabled": False, "record_type": "LOCAL_TRACKED_PASSAGE", "track_id": 7,
           "screen_direction": "DOWN", "crossing_video_seconds": 1,
           "samples": samples, "plate_consensus": summarize_plate_samples(samples)}
    (folder / "passages.jsonl").write_text(json.dumps(row), encoding="utf-8")
    return folder, row


class PassageAuditTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.catalog = ResultCatalog(self.root)
        self.tracking, _, _ = save_tracking(self.root)
        self.folder, self.row = save_ocr(self.root, self.tracking)

    def test_valid_ocr_is_linked_without_source_video_access(self):
        result = audit_passages(self.catalog, "ocr")
        self.assertEqual((result["processed_tracks"], result["samples_checked"]), (1, 1))

    def test_wrong_vehicle_direction_and_time_are_rejected(self):
        for change in ({"track_id": 99}, {"screen_direction": "UP"}, {"crossing_video_seconds": 2}):
            (self.folder / "passages.jsonl").write_text(json.dumps({**self.row, **change}), encoding="utf-8")
            with self.subTest(change=change), self.assertRaises(ValueError):
                audit_passages(self.catalog, "ocr")

    def test_unknown_or_duplicate_sample_frames_are_rejected(self):
        for samples in ([{**self.row["samples"][0], "frame_index": 13}], self.row["samples"] * 2):
            row = {**self.row, "samples": samples, "plate_consensus": summarize_plate_samples(samples)}
            (self.folder / "passages.jsonl").write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaises(ValueError):
                audit_passages(self.catalog, "ocr")

    def test_external_or_wrong_tracking_source_is_rejected(self):
        with self.assertRaises(ValueError):
            audit_passages(self.catalog, "ocr", self.root / "other")
        summary = json.loads((self.folder / "summary.json").read_text(encoding="utf-8"))
        summary["source_run"] = str(self.root.parent / "external")
        write_json_atomic(self.folder / "summary.json", summary)
        with self.assertRaises(ValueError):
            audit_passages(self.catalog, "ocr")

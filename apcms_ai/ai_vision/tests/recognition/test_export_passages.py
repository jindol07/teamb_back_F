# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_export_passages.py

import csv
import json
import tempfile
import unittest
from pathlib import Path

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.export_passages import export_csv
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.passage_query import PassageQuery
from ai_vision.recognition.plate_consensus import summarize_plate_samples


class ExportPassagesTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.catalog = ResultCatalog(self.root / "runs")
        write_json_atomic(self.catalog.root / "empty/summary.json", {
            "http_enabled": False, "crossings_in_run": 0, "processed_tracks": 0, "confirmed_plates": 0})
        (self.catalog.root / "empty/passages.jsonl").write_text("", encoding="utf-8")

    def test_empty_export_has_bom_and_column_header(self):
        output = self.root / "empty.csv"
        self.assertEqual(export_csv(self.catalog, "empty", output), 0)
        self.assertTrue(output.read_bytes().startswith(b"\xef\xbb\xbf"))
        with output.open(encoding="utf-8-sig", newline="") as handle:
            self.assertEqual(list(csv.reader(handle))[0][0], "run_id")

    def test_existing_export_and_original_results_are_preserved(self):
        output = self.root / "existing.csv"
        output.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            export_csv(self.catalog, "empty", output)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep")
        with self.assertRaises(ValueError):
            export_csv(self.catalog, "empty", self.catalog.root / "empty/export.csv")

    def test_corrupt_result_does_not_create_output(self):
        (self.catalog.root / "empty/passages.jsonl").write_text("{", encoding="utf-8")
        output = self.root / "bad.csv"
        with self.assertRaises(ValueError):
            export_csv(self.catalog, "empty", output)
        self.assertFalse(output.exists())

    def test_all_rows_and_korean_plate_survive_csv_roundtrip(self):
        folder = self.catalog.root / "many"
        write_json_atomic(folder / "summary.json", {
            "http_enabled": False, "crossings_in_run": 101, "processed_tracks": 101, "confirmed_plates": 101})
        samples = [{"frame_index": 1, "video_seconds": 1, "plate_number": "91소6408", "plate_type": "KOREAN_VALID"},
                   {"frame_index": 20, "video_seconds": 1.3, "plate_number": "91소6408", "plate_type": "KOREAN_VALID"}]
        rows = [{"http_enabled": False, "record_type": "LOCAL_TRACKED_PASSAGE", "track_id": i,
                 "screen_direction": "DOWN", "crossing_video_seconds": i,
                 "samples": samples, "plate_consensus": summarize_plate_samples(samples)} for i in range(101)]
        path = folder / "passages.jsonl"
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
        output = self.root / "many.csv"
        self.assertEqual(export_csv(self.catalog, "many", output), 101)
        with output.open(encoding="utf-8-sig", newline="") as handle:
            saved = list(csv.DictReader(handle))
        self.assertEqual(saved[-1]["track_id"], "100")
        self.assertEqual(saved[0]["plate_number"], "91소6408")
        self.assertEqual(export_csv(self.catalog, "many", self.root / "filtered.csv",
                                    PassageQuery("DOWN", "CONFIRMED", 99, 100)), 2)
        # 중복 차량은 검색 조건으로 제외되더라도 전체 결과 오류로 처리합니다.
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n" + json.dumps(rows[0]))
        with self.assertRaises(ValueError):
            export_csv(self.catalog, "many", self.root / "duplicate.csv", PassageQuery("UP"))

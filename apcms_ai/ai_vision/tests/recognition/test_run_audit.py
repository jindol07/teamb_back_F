# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_run_audit.py

import json
import sys
import tempfile
import unittest
from pathlib import Path
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.run_audit import audit_run
from ai_vision.tests.recognition.test_tracking_audit import save_tracking
from ai_vision.tests.recognition.test_passage_audit import save_ocr


class RunAuditTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.catalog = ResultCatalog(self.root)
        self.tracking, _, _ = save_tracking(self.root)
        self.ocr, _ = save_ocr(self.root, self.tracking)
        self.pipeline = {"http_enabled": False, "source_video": "D:/test/video.mp4",
                         "tracking_dir": str(self.tracking), "ocr_dir": str(self.ocr), "total_crossings": 1,
                         "ocr_processed": 1, "ocr_not_processed": 0, "crossing_counts": {"DOWN": 1},
                         "plate_status_counts": {"NO_VALID_KOREAN_PLATE": 1}, "ocr_coverage": "ALL_RECORDED_TRACKS"}
        write_json_atomic(self.root / "pipeline/summary.json", self.pipeline)

    def test_tracking_ocr_and_pipeline_pass_without_models_or_writes(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        loaded = "ai_vision.recognition.recognizer" in sys.modules
        for name in ("tracking", "ocr", "pipeline"):
            report = audit_run(self.catalog, name)
            self.assertEqual(report["status"], "PASS", report)
            self.assertEqual(report["scope"], "SAVED_LOG_CONSISTENCY_ONLY")
            self.assertNotIn(str(self.root), json.dumps(report))
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertEqual("ai_vision.recognition.recognizer" in sys.modules, loaded)

    def test_unfinished_run_and_missing_run_are_distinct(self):
        write_json_atomic(self.root / "failed/pipeline.json", {
            "http_enabled": False, "status": "FAILED", "stage": "ocr", "error": "secret local path"})
        result = audit_run(self.catalog, "failed")
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertNotIn("secret", str(result))
        with self.assertRaises(FileNotFoundError):
            audit_run(self.catalog, "missing")

    def test_corrupt_records_return_fixed_reason_code(self):
        (self.tracking / "crossings.jsonl").write_text("{", encoding="utf-8")
        result = audit_run(self.catalog, "pipeline")
        self.assertEqual((result["status"], result["reason_code"]), ("FAILED", "OCR_TRACK_LINKS"))
        self.assertNotIn(str(self.root), str(result))

    def test_wrong_pipeline_video_and_direction_counts_are_rejected(self):
        for change, code in (({"source_video": "D:/other.mp4"}, "PIPELINE_SOURCES"),
                             ({"crossing_counts": {"UP": 1}}, "OCR_TRACK_LINKS")):
            write_json_atomic(self.root / "pipeline/summary.json", {**self.pipeline, **change})
            result = audit_run(self.catalog, "pipeline")
            self.assertEqual((result["status"], result["reason_code"]), ("FAILED", code))

    def test_missing_observation_scope_is_warning(self):
        summary = json.loads((self.tracking / "summary.json").read_text(encoding="utf-8"))
        summary["observations_saved"] = False
        write_json_atomic(self.tracking / "summary.json", summary)
        (self.tracking / "observations.jsonl").unlink()
        result = audit_run(self.catalog, "tracking")
        self.assertEqual((result["status"], result["reason_code"]), ("WARNING", "OBSERVATIONS_NOT_SAVED"))

    def test_partial_ocr_is_warning_even_when_links_are_valid(self):
        event = {"track_id": 8, "frame_index": 15, "video_seconds": 1.5, "direction": "DOWN"}
        with (self.tracking / "crossings.jsonl").open("a", encoding="utf-8") as handle:
            handle.write("\n" + json.dumps(event))
        with (self.tracking / "observations.jsonl").open("a", encoding="utf-8") as handle:
            handle.write("\n" + json.dumps({"track_id": 8, "frame_index": 15, "video_seconds": 1.5, "box": [1, 2, 30, 40]}))
        summary = json.loads((self.tracking / "summary.json").read_text(encoding="utf-8"))
        summary["counts"] = {"DOWN": 2}
        write_json_atomic(self.tracking / "summary.json", summary)
        summary = json.loads((self.ocr / "summary.json").read_text(encoding="utf-8"))
        summary["crossings_in_run"] = 2
        write_json_atomic(self.ocr / "summary.json", summary)
        result = audit_run(self.catalog, "ocr")
        self.assertEqual((result["status"], result["reason_code"]), ("WARNING", "OCR_PARTIAL"))

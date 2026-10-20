# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_preview_vehicle_events.py

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.preview_vehicle_events import build_preview, main
from ai_vision.tests.recognition.test_tracking_audit import save_tracking
from ai_vision.tests.recognition.test_passage_audit import save_ocr


class PreviewVehicleEventsTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.catalog = ResultCatalog(self.root / "runs")
        self.tracking, _, _ = save_tracking(self.catalog.root)
        self.folder, self.row = save_ocr(self.catalog.root, self.tracking)
        self.now = datetime(2020, 1, 1, 0, 0, 10, tzinfo=timezone.utc)

    def confirmed(self):
        # 합성 정답은 요청 변환 규칙 테스트 전용이며 실제 영상 성능 증거가 아닙니다.
        self.row["samples"] = [{"frame_index": frame, "video_seconds": frame / 10,
                                "plate_number": "91소6408", "plate_type": "KOREAN_VALID", "plate_detection_confidence": score}
                               for frame, score in ((12, .9), (15, .8))]
        self.save_row()
        summary = json.loads((self.folder / "summary.json").read_text(encoding="utf-8"))
        summary["confirmed_plates"] = 1
        write_json_atomic(self.folder / "summary.json", summary)

    def save_row(self):
        self.row["plate_consensus"] = summarize_plate_samples(self.row["samples"])
        (self.folder / "passages.jsonl").write_text(json.dumps(self.row), encoding="utf-8")

    def preview(self, **kwargs):
        options = {"camera_id": "TEST_GATE", "down_direction": "ENTRY", "recording_started_at": "2020-01-01T00:00:00Z", "now": self.now}
        return build_preview(self.catalog, "ocr", **{**options, **kwargs})

    def test_unconfirmed_plate_never_becomes_payload(self):
        result = self.preview()
        self.assertEqual(result["candidate_count"], 0)
        self.assertIsNone(result["items"][0]["payload"])
        self.assertIn("NO_CONFIRMED_KOREAN_PLATE", result["items"][0]["reasons"])

    def test_missing_context_blocks_without_inventing_timestamp(self):
        self.confirmed()
        item = build_preview(self.catalog, "ocr")["items"][0]
        self.assertIsNone(item["payload"])
        self.assertEqual(set(item["reasons"]), {"MISSING_CAMERA_ID", "MISSING_DIRECTION_MAPPING", "MISSING_RECORDING_START"})

    def test_explicit_context_builds_stable_local_candidate_without_sender(self):
        self.confirmed()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        loaded = "ai_vision.parking.parking_event_sender" in sys.modules
        result = self.preview()
        payload = result["items"][0]["payload"]
        self.assertEqual(payload["detected_at"], "2020-01-01T00:00:01+00:00")
        self.assertEqual(payload["confidence"], .8)
        self.assertEqual(payload["direction"], "ENTRY")
        self.assertEqual(result, self.preview())
        self.assertFalse(result["http_enabled"])
        self.assertFalse(result["sendable"])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertEqual("ai_vision.parking.parking_event_sender" in sys.modules, loaded)

    def test_mapping_can_be_reversed_and_up_is_opposite(self):
        self.confirmed()
        self.assertEqual(self.preview(down_direction="EXIT")["items"][0]["payload"]["direction"], "EXIT")
        event = json.loads((self.tracking / "crossings.jsonl").read_text(encoding="utf-8"))
        event["direction"] = "UP"
        (self.tracking / "crossings.jsonl").write_text(json.dumps(event), encoding="utf-8")
        summary = json.loads((self.tracking / "summary.json").read_text(encoding="utf-8"))
        summary["counts"] = {"UP": 1}
        write_json_atomic(self.tracking / "summary.json", summary)
        self.row["screen_direction"] = "UP"
        self.save_row()
        self.assertEqual(self.preview()["items"][0]["payload"]["direction"], "EXIT")

    def test_missing_confidence_and_invalid_source_are_rejected(self):
        self.confirmed()
        del self.row["samples"][0]["plate_detection_confidence"]
        self.save_row()
        self.assertIn("MISSING_DETECTION_CONFIDENCE", self.preview()["items"][0]["reasons"])
        (self.tracking / "observations.jsonl").write_text("", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.preview()

    def test_cli_can_only_write_local_preview_and_preserves_existing_output(self):
        output = self.root / "preview.json"
        with patch("ai_vision.recognition.preview_vehicle_events.ResultCatalog", return_value=self.catalog):
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--run-id", "ocr", "--output", str(output)])
            before = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(["--run-id", "ocr", "--output", str(output)])
            self.assertEqual(error.exception.code, 1)
        self.assertEqual(output.read_bytes(), before)
        self.assertFalse(json.loads(before)["sendable"])

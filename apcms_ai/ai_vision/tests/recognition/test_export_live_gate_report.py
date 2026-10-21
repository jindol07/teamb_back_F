# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_export_live_gate_report.py

import contextlib
import io
import json
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.export_live_gate_report import export_report, main
from ai_vision.recognition.run_live_gate import _demo


class ExportLiveGateReportTests(unittest.TestCase):
    def test_cli_exports_optional_review_columns_and_summary_sidecar(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            source, output = root / "summary.json", root / "report"
            source.write_text(json.dumps(_demo(), ensure_ascii=False), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--summary", str(source), "--output-dir", str(output), "--include-review-reasons"])
            with (output / "passages.csv").open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["review_reason_state"], "NO_REASONS")
            summary = json.loads((output / "review_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["total_passages"], 1)
            self.assertEqual(summary["passages_without_reasons"], 1)
            self.assertEqual(summary["reason_counts"], {})
            self.assertIn("형식 검토 사유 집계", (output / "report.html").read_text(encoding="utf-8"))

    def test_export_preserves_source_and_existing_output_without_network(self):
        # 1. 별도 새 폴더에만 저장하며 원본 JSON 바이트는 보존합니다.
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            assert root.resolve().is_relative_to(base.resolve())
            source, output = root / "summary.json", root / "보고서"
            source.write_text(json.dumps(_demo(), ensure_ascii=False), encoding="utf-8")
            before = source.read_bytes()
            with patch("cv2.VideoCapture", side_effect=AssertionError("camera forbidden")), \
                    patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")):
                with contextlib.redirect_stdout(io.StringIO()):
                    main(["--summary", str(source), "--output-dir", str(output)])
            self.assertTrue((output / "passages.csv").read_bytes().startswith(b"\xef\xbb\xbf"))
            html = (output / "report.html").read_bytes()
            with self.assertRaises(FileExistsError):
                export_report(source, output)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual((output / "report.html").read_bytes(), html)

    def test_invalid_json_does_not_create_output(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            assert root.resolve().is_relative_to(base.resolve())
            source, output = root / "summary.json", root / "report"
            for text in ('{"status":"STOPPED","status":"FAILED"}', '{"value":NaN}', '{}'):
                source.write_text(text, encoding="utf-8")
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(["--summary", str(source), "--output-dir", str(output)])
                self.assertFalse(output.exists())

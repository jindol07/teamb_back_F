# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_run_guarded_vehicle_flow.py

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.run_guarded_vehicle_flow import main


class RunGuardedFlowTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)

    def test_demo_timeout_is_explicitly_synthetic_and_offline(self):
        output = self.root / "flow.json"
        with patch("ai_vision.recognition.run_guarded_vehicle_flow.ResultCatalog", return_value=ResultCatalog(self.root / "runs")):
            with patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")):
                with contextlib.redirect_stdout(io.StringIO()):
                    main(["--demo", "--scenario", "timeout", "--passes", "3", "--output", str(output)])
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(report["uses_synthetic_event"])
        self.assertFalse(report["http_enabled"])
        self.assertEqual(report["mock_call_count"], 1)
        self.assertEqual(report["steps"][-1]["receipt_state"], "DELIVERY_UNKNOWN")

    def test_real_blocked_preview_and_existing_file_are_preserved(self):
        source = self.root / "preview.json"
        output = self.root / "flow.json"
        original = {"run_id": "real", "record_type": "LOCAL_VEHICLE_EVENT_PREVIEW", "http_enabled": False,
                    "sendable": False, "total": 1, "candidate_count": 0,
                    "items": [{"track_id": 1, "status": "BLOCKED", "payload": None}]}
        source.write_text(json.dumps(original), encoding="utf-8")
        with patch("ai_vision.recognition.run_guarded_vehicle_flow.ResultCatalog", return_value=ResultCatalog(self.root / "runs")):
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--preview", str(source), "--output", str(output)])
            before = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--demo", "--output", str(output)])
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(json.loads(source.read_text(encoding="utf-8")), original)
        self.assertEqual(json.loads(before)["mock_call_count"], 0)

    def test_invalid_pass_count_creates_no_file(self):
        output = self.root / "bad.json"
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--demo", "--passes", "0", "--output", str(output)])
        self.assertFalse(output.exists())

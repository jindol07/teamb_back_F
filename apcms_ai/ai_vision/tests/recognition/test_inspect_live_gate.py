# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_inspect_live_gate.py

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.inspect_live_gate import inspect_session, main
from ai_vision.recognition.run_live_gate import _demo
from ai_vision.recognition.live_gate_storage import save_failure


class InspectLiveGateTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding="utf-8")

    def test_completed_and_running_or_interrupted(self):
        self.write("summary.json", _demo())
        self.assertEqual(inspect_session(self.root)["status"], "STOPPED")
        self.write("summary.json", {"record_type": "LIVE_GATE_SESSION", "status": "RUNNING"})
        result = inspect_session(self.root)
        self.assertEqual((result["status"], result["summary_status"]), ("INCOMPLETE", "RUNNING_OR_INTERRUPTED"))

    def test_recovery_is_available_but_failure_remains(self):
        save_failure(self.root, "FINAL_SAVE", OSError(), report=_demo())
        result = inspect_session(self.root)
        self.assertEqual(result["status"], "FAILED")
        self.assertTrue(result["recovery_available"])
        self.assertEqual(result["recovered_passages"], 1)

    def test_invalid_summary_not_silently_replaced_by_valid_recovery(self):
        self.write("summary.json", {})
        self.write("recovered_summary.json", _demo())
        result = inspect_session(self.root)
        self.assertEqual(result["status"], "CORRUPT")
        self.assertTrue(result["recovery_available"])

    def test_missing_or_bad_records_and_cli_status(self):
        self.assertEqual(inspect_session(self.root)["status"], "INCOMPLETE")
        self.write("failure.json", {})
        self.assertEqual(inspect_session(self.root)["status"], "CORRUPT")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stopped:
            main(["--session-dir", str(self.root)])
        self.assertEqual(stopped.exception.code, 1)

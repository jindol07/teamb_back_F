# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_check_live_gate.py

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.check_live_gate import main
from ai_vision.tests.recognition.test_live_gate_preflight import CONFIG


class CheckLiveGateTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps(CONFIG), encoding="utf-8")
        self.args = ["--config", str(self.config), "--camera-id", "TEST", "--down-direction", "ENTRY"]

    def test_default_cli_no_camera_network_or_model_initialization(self):
        output = self.root / "점검.json"
        with patch("cv2.VideoCapture", side_effect=AssertionError("camera forbidden")), \
                patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")), \
                patch("ai_vision.recognition.live_gate_preflight.check_environment", return_value=[]):
            with contextlib.redirect_stdout(io.StringIO()):
                main(self.args + ["--output", str(output)])
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["camera"]["status"], "NOT_CHECKED")
        self.assertEqual(report["status"], "CHECKED")

    def test_existing_output_stops_before_preflight(self):
        output = self.root / "existing.json"
        output.write_text("preserve", encoding="utf-8")
        with patch("ai_vision.recognition.check_live_gate.run_preflight") as run:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(self.args + ["--probe-camera", "--output", str(output)])
            run.assert_not_called()
        self.assertEqual(output.read_text(encoding="utf-8"), "preserve")

    def test_blocked_cli_saves_diagnostic_and_returns_failure(self):
        output = self.root / "blocked.json"
        with patch("ai_vision.recognition.live_gate_preflight.check_environment",
                   return_value=[{"name": "lap", "status": "MISSING"}]):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                main(self.args + ["--output", str(output)])
        self.assertEqual(stopped.exception.code, 1)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["missing_items"], ["lap"])

    def test_missing_output_parent_stops_before_camera_check(self):
        with patch("ai_vision.recognition.check_live_gate.run_preflight") as run:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(self.args + ["--probe-camera", "--output", str(self.root / "missing" / "check.json")])
            run.assert_not_called()

    def test_cli_import_failure_is_saved_and_returns_failure(self):
        output = self.root / "imports.json"
        with patch("ai_vision.recognition.live_gate_preflight.check_environment", return_value=[]), \
                patch("ai_vision.recognition.live_gate_preflight.probe_imports",
                      return_value={"status": "FAILED"}) as imports:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                main(self.args + ["--probe-imports", "--import-timeout", "15", "--output", str(output)])
        self.assertEqual(stopped.exception.code, 1)
        self.assertEqual(imports.call_args_list[0].args, ("vision", 15))
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["imports"]["status"], "FAILED")

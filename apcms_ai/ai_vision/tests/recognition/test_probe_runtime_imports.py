# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_probe_runtime_imports.py

import contextlib
import io
import subprocess
import unittest
from unittest.mock import patch

from ai_vision.recognition.probe_runtime_imports import MARKER, PROFILES, main, probe_imports


class ProbeRuntimeImportsTests(unittest.TestCase):
    def test_success_uses_isolation_and_bounded_timeout(self):
        calls = []
        def runner(command, **options):
            calls.append((command, options))
            return subprocess.CompletedProcess(command, 0, MARKER + "\n", "")
        report = probe_imports("ocr", 12, runner)
        self.assertEqual(report["status"], "PASSED")
        self.assertEqual(len(calls), len(PROFILES["ocr"]))
        self.assertEqual(calls[0][0][1:3], ["-I", "-c"])
        self.assertEqual(calls[0][1]["timeout"], 12)

    def test_failures_continue_and_hide_package_output(self):
        outcomes = [subprocess.TimeoutExpired("probe", 1), OSError("private-path"),
                    subprocess.CompletedProcess([], 1, "private-path", "secret"),
                    subprocess.CompletedProcess([], 0, "no-marker", "")]
        def runner(*args, **kwargs):
            outcome = outcomes.pop(0) if outcomes else subprocess.CompletedProcess([], 0, MARKER, "")
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        report = probe_imports(runner=runner)
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual([row["status"] for row in report["checks"][:4]],
                         ["TIMEOUT", "PROCESS_ERROR", "FAILED", "FAILED"])
        self.assertEqual(len(report["checks"]), len(PROFILES["api"]))
        self.assertNotIn("private-path", str(report))
        self.assertNotIn("secret", str(report))

    def test_invalid_options_rejected_before_process_start(self):
        for timeout in (0, 301, True, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                probe_imports(timeout=timeout)
        with self.assertRaises(ValueError):
            probe_imports("unknown")

    def test_cli_exit_status(self):
        for status, expected in (("PASSED", 0), ("FAILED", 1)):
            with patch("ai_vision.recognition.probe_runtime_imports.probe_imports",
                       return_value={"status": status}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([]), expected)

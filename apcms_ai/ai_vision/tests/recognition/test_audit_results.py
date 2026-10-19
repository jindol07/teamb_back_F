# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_audit_results.py

import contextlib
import io
import unittest
from unittest.mock import patch
from ai_vision.recognition.audit_results import main


class AuditResultsCLITests(unittest.TestCase):
    def test_status_exit_codes_and_default_no_output_file(self):
        for status, expected in (("PASS", 0), ("WARNING", 0), ("FAILED", 1), ("INCOMPLETE", 1)):
            with patch("ai_vision.recognition.audit_results.audit_run", return_value={"status": status}):
                with patch("ai_vision.recognition.audit_results.write_new_file") as write:
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(main(["--run-id", "demo"]), expected)
                    write.assert_not_called()

    def test_optional_report_uses_preserving_writer(self):
        with patch("ai_vision.recognition.audit_results.audit_run", return_value={"status": "PASS"}):
            with patch("ai_vision.recognition.audit_results.write_new_file") as write:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["--run-id", "demo", "--output", "report.json"]), 0)
                self.assertEqual(write.call_args.args[-1], ".json")

    def test_invalid_target_is_nonzero_without_raw_error(self):
        with patch("ai_vision.recognition.audit_results.audit_run", side_effect=ValueError("secret path")):
            with contextlib.redirect_stderr(io.StringIO()) as stream, self.assertRaises(SystemExit) as error:
                main(["--run-id", "demo"])
        self.assertEqual(error.exception.code, 2)
        self.assertNotIn("secret", stream.getvalue())

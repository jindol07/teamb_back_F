# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_check_deployed_api_cli.py

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.check_deployed_api import main


class CheckDeployedAPICLITests(unittest.TestCase):
    def test_review_options_are_forwarded(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder, \
                patch("ai_vision.recognition.check_deployed_api.run_check", return_value={"status": "PASS"}) as check, \
                contextlib.redirect_stdout(io.StringIO()):
            main(["--image", "sample.jpg", "--expected-ocr-text", "10-1557", "--expected-plate-type", "REVIEW",
                  "--expected-review-reason", "KOREAN_CHARACTER_NOT_FOUND", "--output-dir", str(Path(folder) / "check")])
            self.assertEqual(check.call_args.kwargs, {"expected_ocr_text": "10-1557", "expected_plate_type": "REVIEW",
                                                      "expected_review_reason": "KOREAN_CHARACTER_NOT_FOUND"})

    def test_report_is_saved_and_existing_folder_stops_network_check(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            output = Path(folder) / "check"
            report = {"status": "PASS", "checks": []}
            with patch("ai_vision.recognition.check_deployed_api.run_check", return_value=report) as check:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["--output-dir", str(output)]), 0)
                self.assertEqual(json.loads((output / "api_check.json").read_text(encoding="utf-8")), report)
                check.reset_mock()
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    main(["--output-dir", str(output)])
                self.assertEqual(caught.exception.code, 2)
                check.assert_not_called()

    def test_failed_api_result_returns_nonzero_and_is_saved(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder, \
                patch("ai_vision.recognition.check_deployed_api.run_check", return_value={"status": "FAIL"}), \
                contextlib.redirect_stdout(io.StringIO()):
            output = Path(folder) / "check"
            self.assertEqual(main(["--output-dir", str(output)]), 1)
            self.assertTrue((output / "api_check.json").is_file())

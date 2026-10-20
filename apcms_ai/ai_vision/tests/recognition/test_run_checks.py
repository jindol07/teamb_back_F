# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_run_checks.py

import contextlib
import io
import unittest
from unittest.mock import Mock, patch

from ai_vision.tests.run_checks import MODULES, build_suite, main


class RunChecksTests(unittest.TestCase):
    def test_manifest_unique_and_excludes_heavy_experiments(self):
        self.assertEqual(len(MODULES), len(set(MODULES)))
        for name in ("test_yolo", "test_pipeline", "test_paddleocr", "test_trocr"):
            self.assertNotIn("ai_vision.tests.recognition." + name, MODULES)
        self.assertIn("ai_vision.tests.recognition.test_recognize_upload_api", MODULES)

    def test_list_does_not_load_or_run_tests(self):
        with patch("ai_vision.tests.run_checks.build_suite") as build, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--list"]), 0)
        build.assert_not_called()
        self.assertEqual(tuple(output.getvalue().splitlines()), MODULES)

    def test_loader_uses_explicit_module_manifest(self):
        loader = Mock()
        self.assertIs(build_suite(loader), loader.loadTestsFromNames.return_value)
        loader.loadTestsFromNames.assert_called_once_with(MODULES)

    def test_failure_is_nonzero_and_options_forwarded(self):
        for successful, expected in ((True, 0), (False, 1)):
            with patch("ai_vision.tests.run_checks.build_suite", return_value="suite"), \
                    patch("ai_vision.tests.run_checks.unittest.TextTestRunner") as runner:
                runner.return_value.run.return_value.wasSuccessful.return_value = successful
                self.assertEqual(main(["--failfast", "-v"]), expected)
                runner.assert_called_once_with(verbosity=2, failfast=True)
                runner.return_value.run.assert_called_once_with("suite")

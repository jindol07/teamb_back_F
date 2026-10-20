# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_asyncio_runtime_check.py

import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from ai_vision.tests.recognition.asyncio_runtime_check import ensure_asyncio_runtime


class AsyncioRuntimeCheckTests(unittest.TestCase):
    def test_same_interpreter_and_bounded_child_process(self):
        result = Mock(returncode=0, stdout="ASYNCIO_RUNTIME_OK\n")
        with patch("ai_vision.tests.recognition.asyncio_runtime_check.subprocess.run", return_value=result) as run:
            ensure_asyncio_runtime()
        self.assertEqual(run.call_args.args[0][0], sys.executable)
        self.assertEqual(run.call_args.kwargs["timeout"], 5)
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_failed_probe_is_error_not_skip_or_success(self):
        for result in (Mock(returncode=1, stdout=""), Mock(returncode=0, stdout="unexpected")):
            with patch("ai_vision.tests.recognition.asyncio_runtime_check.subprocess.run", return_value=result):
                with self.assertRaisesRegex(RuntimeError, "ASYNCIO_RUNTIME_UNAVAILABLE"):
                    ensure_asyncio_runtime()

    def test_timeout_and_process_launch_failure_are_bounded_errors(self):
        for error in (subprocess.TimeoutExpired("probe", 5), OSError("launch failed")):
            with patch("ai_vision.tests.recognition.asyncio_runtime_check.subprocess.run", side_effect=error):
                with self.assertRaisesRegex(RuntimeError, "ASYNCIO_RUNTIME_UNAVAILABLE"):
                    ensure_asyncio_runtime()

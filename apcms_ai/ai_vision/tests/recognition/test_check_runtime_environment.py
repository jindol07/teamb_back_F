# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_check_runtime_environment.py

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.runtime_environment import collect_snapshot
from ai_vision.recognition.check_runtime_environment import main


class CheckRuntimeEnvironmentTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.snapshot = collect_snapshot(lambda name: "test-version")

    def test_export_compare_and_existing_output_preserved(self):
        output = self.root / "environment.json"
        with patch("ai_vision.recognition.check_runtime_environment.collect_snapshot", return_value=self.snapshot):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--output", str(output)]), 0)
                self.assertEqual(main(["--compare", str(output)]), 0)
            before = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(["--output", str(output)])
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(output.read_bytes(), before)

    def test_difference_is_nonzero_and_corrupt_json_is_error(self):
        output = self.root / "environment.json"
        output.write_text(json.dumps(self.snapshot), encoding="utf-8")
        changed = {**self.snapshot, "system": "DifferentOS"}
        with patch("ai_vision.recognition.check_runtime_environment.collect_snapshot", return_value=changed):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--compare", str(output)]), 1)
            output.write_text('{}', encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(["--compare", str(output)])
        self.assertEqual(error.exception.code, 2)

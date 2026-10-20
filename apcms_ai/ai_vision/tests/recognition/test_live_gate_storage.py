# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_storage.py

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.live_gate_storage import save_failure


class LiveGateStorageTests(unittest.TestCase):
    def test_summary_preserved_recovery_and_fixed_error_metadata_saved(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            assert root.resolve().is_relative_to(base.resolve())
            summary = root / "summary.json"
            summary.write_text("preserved", encoding="utf-8")
            files = save_failure(root, "FINAL_SAVE", OSError("private path or key"), report={"example": 1})
            self.assertEqual(files, ["recovered_summary.json", "failure.json"])
            self.assertEqual(summary.read_text(encoding="utf-8"), "preserved")
            diagnostic = json.loads((root / "failure.json").read_text(encoding="utf-8"))
            self.assertNotIn("private", str(diagnostic))
            self.assertTrue(diagnostic["recovered_summary_saved"])

    def test_all_writes_failing_do_not_raise_new_exception(self):
        with patch("ai_vision.recognition.live_gate_storage.write_json_atomic", side_effect=OSError("disk full")) as writer:
            self.assertEqual(save_failure(Path("unused"), "FINAL_SAVE", OSError(), report={}), [])
        self.assertEqual(writer.call_count, 2)

    def test_failed_recovery_still_attempts_diagnostic(self):
        with patch("ai_vision.recognition.live_gate_storage.write_json_atomic", side_effect=[OSError(), None]) as writer:
            files = save_failure(Path("unused"), "FINAL_SAVE", OSError(), report={})
        self.assertEqual(files, ["failure.json"])
        self.assertFalse(writer.call_args.args[1]["recovered_summary_saved"])

# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_deployment_readiness.py

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.deployment_readiness import check_readiness, main


class DeploymentReadinessTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name in ("yolo11n.pt", "license_plate_yolov8n.pt"):
            (self.root / name).write_bytes(b"mock weights")
        patcher = patch.dict(os.environ, {}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_checks_files_and_storage_without_leaving_probe_files(self):
        before = set(self.root.iterdir())
        report = check_readiness(self.root, self.root)
        self.assertEqual(report["status"], "CHECKED")
        self.assertEqual(set(self.root.iterdir()), before)
        self.assertNotIn(str(self.root), str(report))
        self.assertIn("MODEL_INFERENCE", report["unverified"])

    def test_empty_and_missing_models_are_blocked(self):
        (self.root / "yolo11n.pt").write_bytes(b"")
        (self.root / "license_plate_yolov8n.pt").unlink()
        report = check_readiness(self.root, self.root)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(all(c["status"] == "UNAVAILABLE" for c in report["checks"][:2]))

    def test_unwritable_or_missing_storage_is_blocked(self):
        report = check_readiness(self.root, self.root / "missing")
        self.assertEqual(report["status"], "BLOCKED")
        with patch("ai_vision.recognition.deployment_readiness.write_json_atomic", side_effect=PermissionError):
            self.assertEqual(check_readiness(self.root, self.root)["status"], "BLOCKED")
        self.assertFalse(list(self.root.glob(".vision-probe-*")))

    def test_incomplete_local_ocr_configuration_is_blocked(self):
        with patch.dict(os.environ, {"VISION_OCR_DETECTION_MODEL_DIR": "det"}):
            report = check_readiness(self.root, self.root)
        self.assertEqual(report["checks"][-1]["status"], "UNAVAILABLE")

    def test_cli_exit_code(self):
        for status, expected in (("CHECKED", 0), ("BLOCKED", 1)):
            with patch("ai_vision.recognition.deployment_readiness.check_readiness", return_value={"status": status}), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([]), expected)

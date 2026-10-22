# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_preflight.py

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.live_gate_preflight import run_preflight


CONFIG = {"tracker": "bytetrack", "line_y": .5, "line_x": [.1, .9],
          "roi": [0, 0, 1, 0, 1, 1, 0, 1]}


class LiveGatePreflightTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        assert root.resolve().is_relative_to(base.resolve())
        self.config = root / "config.json"
        self.config.write_text(json.dumps(CONFIG), encoding="utf-8")

    def test_default_does_not_probe_or_claim_runtime_ready(self):
        camera = Mock()
        report = run_preflight(self.config, "TEST", "ENTRY", environment_checker=lambda: [], camera_checker=camera)
        self.assertEqual(report["status"], "CHECKED")
        self.assertEqual(report["camera"]["status"], "NOT_CHECKED")
        self.assertIn("MODEL_LOADING_AND_INTEGRITY", report["unverified"])
        self.assertFalse(report["http_enabled"])
        camera.assert_not_called()

    def test_missing_environment_blocks_requested_camera(self):
        camera = Mock()
        report = run_preflight(self.config, "TEST", "ENTRY", probe=True,
            environment_checker=lambda: [{"name": "lap", "status": "MISSING"}], camera_checker=camera)
        self.assertEqual((report["status"], report["missing_items"]), ("BLOCKED", ["lap"]))
        camera.assert_not_called()

    def test_explicit_probe_failure_blocks_and_valid_frame_is_checked(self):
        for state, expected in (("FAILED", "BLOCKED"), ("FRAME_READ", "CHECKED")):
            camera = Mock(return_value={"status": state})
            report = run_preflight(self.config, "TEST", "EXIT", camera_index=2, probe=True,
                                   environment_checker=lambda: [], camera_checker=camera)
            self.assertEqual(report["status"], expected)
            camera.assert_called_once_with(2)

    def test_invalid_config_rejected_before_camera(self):
        camera = Mock()
        self.config.write_text('{}', encoding="utf-8")
        with self.assertRaises(ValueError):
            run_preflight(self.config, "TEST", "ENTRY", probe=True, camera_checker=camera)
        camera.assert_not_called()

    # 1. import 실패가 있을 때 실제 카메라를 열지 않는지 확인합니다.
    def test_import_failure_blocks_camera_but_preserves_both_reports(self):
        camera = Mock()
        checker = Mock(side_effect=[{"status": "FAILED"}, {"status": "PASSED"}])
        report = run_preflight(self.config, "TEST", "ENTRY", probe=True,
            environment_checker=lambda: [], camera_checker=camera,
            check_imports=True, import_timeout=12, import_checker=checker)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["imports"]["status"], "FAILED")
        self.assertEqual(checker.call_args_list[0].args, ("vision", 12))
        self.assertEqual(checker.call_args_list[1].args, ("ocr", 12))
        camera.assert_not_called()

    def test_successful_imports_allow_requested_camera(self):
        camera = Mock(return_value={"status": "FRAME_READ"})
        report = run_preflight(self.config, "TEST", "ENTRY", probe=True,
            environment_checker=lambda: [], camera_checker=camera, check_imports=True,
            import_checker=lambda *args: {"status": "PASSED"})
        self.assertEqual(report["status"], "CHECKED")
        self.assertEqual(report["imports"]["status"], "PASSED")
        self.assertIn("PACKAGE_IMPORT_AND_COMPATIBILITY", report["unverified"])
        camera.assert_called_once()

    def test_default_and_missing_packages_do_not_import(self):
        checker = Mock(side_effect=AssertionError("import forbidden"))
        report = run_preflight(self.config, "TEST", "ENTRY", environment_checker=lambda: [],
                               import_checker=checker)
        self.assertEqual(report["imports"]["status"], "NOT_CHECKED")
        report = run_preflight(self.config, "TEST", "ENTRY", check_imports=True,
            environment_checker=lambda: [{"name": "lap", "status": "MISSING"}], import_checker=checker)
        self.assertEqual(report["imports"]["status"], "SKIPPED_MISSING_ENVIRONMENT")
        self.assertEqual(report["status"], "BLOCKED")
        checker.assert_not_called()

    def test_invalid_import_options_rejected_before_environment_check(self):
        checker = Mock()
        for options in ({"check_imports": 1}, {"import_timeout": 0},
                        {"import_timeout": float("nan")}, {"import_timeout": 301}):
            with self.assertRaises(ValueError):
                run_preflight(self.config, "TEST", "ENTRY", environment_checker=checker, **options)
        checker.assert_not_called()

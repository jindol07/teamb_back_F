# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_environment.py

import tempfile
import unittest
from importlib.metadata import PackageNotFoundError
from pathlib import Path

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.live_gate_environment import check_environment


class LiveGateEnvironmentTests(unittest.TestCase):
    def test_metadata_alternatives_and_nonempty_models(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            assert root.resolve().is_relative_to(base.resolve())
            for name in ("yolo11n.pt", "license_plate_yolov8n.pt"):
                (root / name).write_bytes(b"not loaded")
            def version(name):
                if name in {"opencv-contrib-python", "opencv-contrib-python-headless", "opencv-python-headless", "paddlepaddle-gpu"}:
                    raise PackageNotFoundError(name)
                return "test-version"
            checks = check_environment(root, version)
            self.assertTrue(all(item["status"] == "FOUND" for item in checks))
            opencv = next(item for item in checks if item["name"] == "opencv")
            self.assertEqual(opencv["installed"], {"opencv-python": "test-version"})

    def test_missing_packages_and_empty_models_are_reported(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            assert root.resolve().is_relative_to(base.resolve())
            (root / "yolo11n.pt").write_bytes(b"")
            def missing(name):
                raise PackageNotFoundError(name)
            self.assertTrue(all(item["status"] == "MISSING" for item in check_environment(root, missing)))

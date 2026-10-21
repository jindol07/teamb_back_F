# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_deployment_runtime.py

"""실제 카메라·모델 없이 배포 경로와 화면 없는 실행을 확인합니다."""

import ast
import contextlib
import io
import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from ai_vision import paths
from ai_vision.camera_runtime import open_camera, require_display, release_resources
from ai_vision.recognition.record_gate_video import record


class DeploymentRuntimeTests(unittest.TestCase):
    def test_development_tools_import_without_writing_or_opening_gui(self):
        names = ("parking.space_marker", "parking.space_editor", "parking.object_detector_test",
                 "safety.test_fire_smoke_speed", "recognition.make_motion_video",
                 "safety.fire_smoke_detector", "parking.object_detector")
        # 실제 파일 쓰기·창 생성 없이 환경변수 경로를 쓰는지 함께 검사합니다.
        with patch("pathlib.Path.mkdir", side_effect=AssertionError("import must not write")), \
                patch("ai_vision.camera_runtime.require_display", side_effect=AssertionError("GUI forbidden")):
            modules = [importlib.reload(importlib.import_module("ai_vision." + name)) for name in names]
        self.assertEqual(modules[0].IMAGE_PATH, paths.RESULT_DIR / "parking" / "first_frame.jpg")
        self.assertEqual(modules[1].SAVE_PATH, paths.DATA_DIR / "parking_spaces" / "parking_spots.json")
        self.assertEqual(modules[2].MODEL_PATH, paths.MODEL_DIR / "yolo11n.pt")
        self.assertEqual(modules[3].MODEL_PATH, paths.MODEL_DIR / "fire_smoke.pt")
        self.assertEqual(modules[4].IMAGE_PATH, paths.TEST_IMAGE_DIR / "car12.png")

    def test_cleanup_failure_still_releases_remaining_resources(self):
        capture, writer = Mock(), Mock()
        capture.release.side_effect = RuntimeError("device error")
        with self.assertRaises(OSError):
            release_resources(capture, writer)
        writer.release.assert_called_once()

    def test_cleanup_keeps_original_processing_error(self):
        capture, writer = Mock(), Mock()
        capture.release.side_effect = RuntimeError("cleanup")
        with self.assertRaisesRegex(ValueError, "original"):
            try:
                raise ValueError("original")
            finally:
                release_resources(capture, writer)
        writer.release.assert_called_once()

    def test_record_write_failure_cleans_resources_without_success_report(self):
        capture, writer = Mock(), Mock()
        capture.read.return_value = (True, np.zeros((10, 10, 3), dtype=np.uint8))
        capture.get.return_value = 30
        capture.release.side_effect = RuntimeError("cleanup")
        writer.write.side_effect = ValueError("encode failed")
        base = paths.RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder, \
                patch("ai_vision.recognition.record_gate_video.open_camera", return_value=capture), \
                patch("cv2.VideoWriter", return_value=writer), \
                patch("ai_vision.recognition.record_gate_video.monotonic", side_effect=[0, 0]), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "encode failed"):
                record(0, 1, Path(folder), preview=False)
            self.assertEqual(list(Path(folder).glob("*.json")), [])
        capture.release.assert_called_once()
        writer.release.assert_called_once()

    def test_volume_paths_are_independent_of_working_directory(self):
        with patch.dict(os.environ, {"VISION_RESULT_DIR": "external-results"}):
            self.assertEqual(paths._directory("VISION_RESULT_DIR", None),
                             (paths.BASE_DIR / "external-results").resolve())
        with patch.dict(os.environ, {"VISION_RESULT_DIR": " "}):
            with self.assertRaises(ValueError):
                paths._directory("VISION_RESULT_DIR", None)

    def test_absolute_volume_path_is_preserved(self):
        target = paths.BASE_DIR.resolve()
        with patch.dict(os.environ, {"VISION_MODEL_DIR": str(target)}):
            self.assertEqual(paths._directory("VISION_MODEL_DIR", None), target)

    def test_windows_volume_path_is_rejected_on_linux(self):
        with patch("ai_vision.paths.sys.platform", "linux"), \
                patch.dict(os.environ, {"VISION_MODEL_DIR": "D:/models"}):
            with self.assertRaises(ValueError):
                paths._directory("VISION_MODEL_DIR", None)

    def test_camera_backend_is_platform_specific(self):
        for system, windows in (("win32", True), ("linux", False)):
            with patch("ai_vision.camera_runtime.sys.platform", system), patch("cv2.VideoCapture") as capture:
                open_camera(2)
                self.assertEqual(len(capture.call_args.args), 2 if windows else 1)

    def test_linux_without_display_is_rejected_before_gui_calls(self):
        with patch("ai_vision.camera_runtime.sys.platform", "linux"), patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                require_display()

    def test_headless_opencv_is_rejected_even_with_display_variable(self):
        with patch.dict(os.environ, {"DISPLAY": ":0"}), \
                patch("cv2.getBuildInformation", return_value="  GUI: NONE\n"):
            with self.assertRaises(RuntimeError):
                require_display()

    def test_record_without_preview_never_calls_gui_and_releases_resources(self):
        capture, writer = Mock(), Mock()
        capture.read.return_value = (True, np.zeros((10, 10, 3), dtype=np.uint8))
        capture.get.return_value = 30
        base = paths.RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder, \
                patch("ai_vision.recognition.record_gate_video.open_camera", return_value=capture), \
                patch("cv2.VideoWriter", return_value=writer), \
                patch("ai_vision.recognition.record_gate_video.monotonic", side_effect=[0, 0, 1, 1]), \
                patch("cv2.imshow", side_effect=AssertionError("GUI forbidden")), \
                patch("cv2.waitKey", side_effect=AssertionError("GUI forbidden")), \
                patch("cv2.destroyAllWindows", side_effect=AssertionError("GUI forbidden")), \
                contextlib.redirect_stdout(io.StringIO()):
            record(0, 1, Path(folder), preview=False)
            self.assertEqual(len(list(Path(folder).glob("*.json"))), 1)
        capture.release.assert_called_once()
        writer.release.assert_called_once()
        writer.write.assert_called_once()

    def test_all_python_sources_parse_without_running_experiment_scripts(self):
        # import하면 카메라·모델을 실행하는 구형 실험도 있어 전체 파일은 구문만 검사합니다.
        for source in paths.BASE_DIR.rglob("*.py"):
            with self.subTest(source=source.relative_to(paths.BASE_DIR)):
                ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))

    def test_standalone_app_health_does_not_import_inquiry_or_recommendation(self):
        # 새 프로세스에서 서버를 가져와 다른 테스트의 import 상태와 섞이지 않게 합니다.
        script = (
            "import sys; from fastapi.testclient import TestClient; "
            "from ai_vision.app import app; "
            "client=TestClient(app); response=client.get('/health'); "
            "assert response.status_code == 200; "
            "assert response.json()['scope'] == 'PROCESS_ONLY'; "
            "assert client.get('/parking/occupancy').status_code in (200, 503); "
            "assert not any(k.startswith(('ai_inquiry', 'ai_recmn', 'paddleocr', 'ultralytics')) "
            "for k in sys.modules)"
        )
        result = subprocess.run([sys.executable, "-c", script], cwd=paths.BASE_DIR.parent,
                                capture_output=True, text=True, errors="replace", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

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
    def test_explicit_backend_maps_to_platform_capture_code(self):
        import cv2
        for platform, backend, code in [('win32', 'msmf', cv2.CAP_MSMF),
                                         ('win32', 'dshow', cv2.CAP_DSHOW),
                                         ('linux', 'v4l2', cv2.CAP_V4L2)]:
            with self.subTest(platform=platform, backend=backend), \
                    patch('ai_vision.camera_runtime.sys.platform', platform), patch('cv2.VideoCapture') as capture:
                open_camera(1, backend=backend)
                capture.assert_called_once_with(1, code)

    def test_auto_backend_uses_platform_selection(self):
        with patch('cv2.VideoCapture') as capture:
            open_camera(1, backend='auto')
        capture.assert_called_once_with(1)

    def test_incompatible_backend_is_rejected_before_camera_open(self):
        for platform, backend in [('linux', 'msmf'), ('linux', 'dshow'), ('win32', 'v4l2'), ('win32', 'unknown')]:
            with self.subTest(platform=platform, backend=backend), \
                    patch('ai_vision.camera_runtime.sys.platform', platform), patch('cv2.VideoCapture') as capture:
                with self.assertRaises(ValueError):
                    open_camera(1, backend=backend)
            capture.assert_not_called()

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
                patch("cv2.VideoWriter", side_effect=lambda path, *args: (Path(path).touch(), writer)[1]), \
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

    def test_record_manual_start_cancel_does_not_save_video(self):
        capture = Mock()
        capture.read.return_value = (True, np.zeros((10, 10, 3), dtype=np.uint8))
        base = paths.RESULT_DIR / 'test_tmp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder, \
                patch('ai_vision.recognition.record_gate_video.open_camera', return_value=capture) as opened, \
                patch('ai_vision.recognition.record_gate_video.require_display'), \
                patch('ai_vision.parking.parking_preview.ParkingPreview') as preview, \
                patch('cv2.VideoWriter') as writer:
            preview.return_value.wait_until_ready.return_value = None
            result = record(1, 10, Path(folder), camera_backend='auto', wait_for_start=True)
            self.assertEqual(result['status'], 'CANCELLED')
            opened.assert_called_once_with(1, backend='auto')
            writer.assert_not_called()
            self.assertEqual(list(Path(folder).iterdir()), [])
            preview.return_value.close.assert_called_once()
        capture.release.assert_called_once()

    def test_record_rejects_hidden_manual_start_before_camera(self):
        with patch('ai_vision.recognition.record_gate_video.open_camera') as opened:
            with self.assertRaises(ValueError):
                record(1, 10, paths.RESULT_DIR, preview=False, wait_for_start=True)
        opened.assert_not_called()

    def test_preparation_allows_recording_without_vehicle_detection(self):
        from ai_vision.parking.parking_preview import ParkingPreview
        view = ParkingPreview.__new__(ParkingPreview)
        view.show = Mock(return_value=ord(' '))
        first, second = np.zeros((10, 10, 3), dtype=np.uint8), np.ones((10, 10, 3), dtype=np.uint8)
        capture = Mock()
        capture.read.side_effect = [(True, first), (True, second)]
        checker = Mock(side_effect=[False, True])
        self.assertIs(view.wait_until_ready(capture, checker), first)
        self.assertEqual(checker.call_count, 1)

    def test_vehicle_check_requires_config_and_manual_start(self):
        with patch('ai_vision.recognition.record_gate_video.open_camera') as opened:
            with self.assertRaises(ValueError):
                record(1, 10, paths.RESULT_DIR, check_vehicle=True)
            with self.assertRaises(ValueError):
                record(1, 10, paths.RESULT_DIR, wait_for_start=True, check_vehicle=True)
        opened.assert_not_called()

    def test_vehicle_preparation_checks_actual_model_boxes_inside_space(self):
        from ai_vision.tests.recognition.test_vehicle_space_tracker import CONFIG
        from ai_vision.recognition.local_io import write_json_atomic
        capture = Mock()
        capture.read.return_value = (True, np.zeros((140, 240, 3), dtype=np.uint8))
        base = paths.RESULT_DIR / 'test_tmp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            config = Path(folder) / 'config.json'
            write_json_atomic(config, CONFIG)
            # 실제 추론은 모의 모델을 쓰므로 Git 제외 가중치에 의존하지 않습니다.
            model_dir = Path(folder) / 'models'
            model_dir.mkdir()
            model_file = model_dir / 'yolo11n.pt'
            model_file.write_bytes(b'mocked model; YOLO loader is patched below')
            with patch.object(paths, 'MODEL_DIR', model_dir), \
                    patch.dict(os.environ, {'YOLO_AUTOINSTALL': 'false'}), \
                    patch('ultralytics.YOLO') as model, \
                    patch('ai_vision.recognition.record_gate_video.open_camera', return_value=capture), \
                    patch('ai_vision.recognition.record_gate_video.require_display'), \
                    patch('ai_vision.parking.parking_preview.ParkingPreview') as preview:
                model.return_value.names = {0: 'car', 1: 'cell phone'}
                box = Mock()
                box.xyxy = np.array([[25, 25, 75, 90]])
                prediction = Mock()
                prediction.boxes = [box]
                model.return_value.predict.return_value = [prediction]
                def prepare(camera, check_ready):
                    self.assertTrue(check_ready(capture.read.return_value[1]))
                    self.assertEqual(preview.return_value.source_label, 'VEHICLE IN SPACE')
                    box.xyxy = np.array([[25, 25, 75, 135]])
                    self.assertFalse(check_ready(capture.read.return_value[1]))
                    self.assertEqual(preview.return_value.source_label, 'VEHICLE OUTSIDE SPACE')
                    prediction.boxes = []
                    self.assertFalse(check_ready(capture.read.return_value[1]))
                    self.assertEqual(preview.return_value.source_label, 'VEHICLE NOT DETECTED')
                    return None
                preview.return_value.wait_until_ready.side_effect = prepare
                result = record(1, 10, Path(folder), wait_for_start=True, config_path=config, check_vehicle=True)
                self.assertEqual(result['status'], 'CANCELLED')
                model.assert_called_once_with(model_file)
                self.assertEqual(model.return_value.predict.call_args.kwargs['classes'], [0])
        capture.release.assert_called_once()

    def test_missing_preparation_model_does_not_download_or_open_camera(self):
        from ai_vision.tests.recognition.test_vehicle_space_tracker import CONFIG
        from ai_vision.recognition.local_io import write_json_atomic
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'spaces.json'
            write_json_atomic(config, CONFIG)
            with patch.object(paths, 'MODEL_DIR', Path(folder) / 'missing_models'), \
                    patch('ultralytics.YOLO') as model, \
                    patch('ai_vision.recognition.record_gate_video.require_display'), \
                    patch('ai_vision.recognition.record_gate_video.open_camera') as camera:
                with self.assertRaises(FileNotFoundError):
                    record(1, 10, Path(folder) / 'output', wait_for_start=True,
                           config_path=config, check_vehicle=True)
                model.assert_not_called()
                camera.assert_not_called()

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

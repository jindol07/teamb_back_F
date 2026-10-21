# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_preview_gate_config.py

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.preview_gate_config import main, render_preview, LiveGatePreview


class PreviewGateConfigTests(unittest.TestCase):
    def test_preparation_keeps_showing_frames_until_space(self):
        capture = Mock()
        capture.read.return_value = (True, np.zeros((200, 300, 3), dtype=np.uint8))
        with patch('ai_vision.recognition.preview_gate_config.require_display'), patch('cv2.imshow') as show, \
                patch('cv2.waitKey', side_effect=[-1, -1, ord(' ')]), patch('cv2.destroyWindow'), \
                contextlib.redirect_stdout(io.StringIO()):
            preview = LiveGatePreview(self.config, 'ENTRY')
            self.assertTrue(preview.wait_until_ready(capture))
            self.assertEqual(show.call_count, 3)
            preview.close()
        capture.release.assert_not_called()

    def test_preparation_q_cancels_without_starting_measurement(self):
        capture = Mock()
        capture.read.return_value = (True, np.zeros((200, 300, 3), dtype=np.uint8))
        with patch('ai_vision.recognition.preview_gate_config.require_display'), patch('cv2.imshow'), \
                patch('cv2.waitKey', return_value=ord('q')), patch('cv2.destroyWindow'), \
                contextlib.redirect_stdout(io.StringIO()):
            preview = LiveGatePreview(self.config, 'ENTRY')
            self.assertFalse(preview.wait_until_ready(capture))
            preview.close()
        capture.read.assert_called_once()

    def test_live_preview_preserves_original_and_q_closes_only_its_window(self):
        frame = np.zeros((200, 300, 3), dtype=np.uint8)
        before = frame.copy()
        with patch('ai_vision.recognition.preview_gate_config.require_display'), \
                patch('cv2.imshow') as show, patch('cv2.waitKey', return_value=ord('q')), \
                patch('cv2.destroyWindow') as close:
            preview = LiveGatePreview(self.config, 'ENTRY')
            self.assertFalse(preview(frame))
            np.testing.assert_array_equal(frame, before)
            self.assertFalse(np.array_equal(show.call_args.args[1], frame))
            preview.close()
            preview.close()
            close.assert_called_once_with('APCMS Live Gate - Q to stop')

    def test_live_preview_rejects_headless_before_window_creation(self):
        with patch('ai_vision.recognition.preview_gate_config.require_display', side_effect=RuntimeError('화면 없음')), \
                patch('cv2.imshow') as show:
            with self.assertRaises(RuntimeError):
                LiveGatePreview(self.config, 'ENTRY')
        show.assert_not_called()

    def test_live_preview_not_shown_does_not_destroy_windows(self):
        with patch('ai_vision.recognition.preview_gate_config.require_display'), patch('cv2.destroyWindow') as close:
            preview = LiveGatePreview(self.config, 'ENTRY')
            preview.close()
        close.assert_not_called()

    def setUp(self):
        self.config = {"tracker": "bytetrack", "line_y": .5, "line_x": [.1, .9],
                       "roi": [.1, .1, .9, .1, .9, .9, .1, .9]}

    def test_coordinates_colors_and_original_preserved(self):
        # 1. 실시간 처리기에 전달되는 비율이 정확한 픽셀에 표시되는지 확인합니다.
        frame = np.zeros((200, 300, 3), dtype=np.uint8)
        result = render_preview(frame, self.config, "ENTRY")
        self.assertEqual(result[100, 150].tolist(), [0, 0, 255])
        self.assertEqual(result[150, 30].tolist(), [0, 255, 0])
        self.assertFalse(frame.any())

    def test_invalid_image_config_or_direction_rejected(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        for image, config, direction in ((None, self.config, "ENTRY"),
                (frame, {}, "ENTRY"), (frame, self.config, "DOWN"),
                (frame.astype(float), self.config, "ENTRY")):
            with self.assertRaises(ValueError):
                render_preview(image, config, direction)

    def test_cli_korean_paths_no_camera_and_no_overwrite(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            assert root.resolve().is_relative_to(base.resolve())
            image, config, output = root / "입력.png", root / "설정.json", root / "결과.png"
            image.write_bytes(cv2.imencode(".png", np.zeros((200, 300, 3), dtype=np.uint8))[1].tobytes())
            config.write_text(json.dumps(self.config), encoding="utf-8")
            args = ["--image", str(image), "--config", str(config), "--down-direction", "EXIT", "--output", str(output)]
            with patch("cv2.VideoCapture", side_effect=AssertionError("camera forbidden")):
                with contextlib.redirect_stdout(io.StringIO()):
                    main(args)
                before = output.read_bytes()
                self.assertIsNotNone(cv2.imdecode(np.frombuffer(before, dtype=np.uint8), cv2.IMREAD_COLOR))
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(args)
                self.assertEqual(output.read_bytes(), before)
            image.write_bytes(b"broken image")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args[:-1] + [str(root / "invalid.png")])
            self.assertFalse((root / "invalid.png").exists())

    def camera_case(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        assert root.resolve().is_relative_to(base.resolve())
        config, output = root / "config.json", root / "camera.png"
        config.write_text(json.dumps(self.config), encoding="utf-8")
        args = ["--camera-index", "0", "--config", str(config), "--down-direction", "ENTRY", "--output", str(output)]
        return config, output, args

    def test_camera_mode_reads_once_releases_and_writes_overlay(self):
        config, output, args = self.camera_case()
        capture = Mock()
        original = np.zeros((200, 300, 3), dtype=np.uint8)
        capture.read.return_value = (True, original)
        with patch("cv2.VideoCapture", return_value=capture), \
                patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")):
            with contextlib.redirect_stdout(io.StringIO()):
                main(args)
        capture.read.assert_called_once()
        capture.release.assert_called_once()
        image = cv2.imdecode(np.frombuffer(output.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(image[100, 150].tolist(), [0, 0, 255])
        self.assertFalse(original.any())

    def test_existing_output_bad_config_or_invalid_index_prevents_camera_access(self):
        config, output, args = self.camera_case()
        with patch("cv2.VideoCapture") as camera:
            output.write_bytes(b"preserve")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args)
            self.assertEqual(output.read_bytes(), b"preserve")
            bad_args = args[:-1] + [str(output.parent / "new.png")]
            config.write_text('{}', encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(bad_args)
            config.write_text(json.dumps(self.config), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--camera-index", "33"] + bad_args[2:])
            camera.assert_not_called()

    def test_release_failure_does_not_publish_preview(self):
        config, output, args = self.camera_case()
        capture = Mock()
        capture.read.return_value = (True, np.zeros((200, 300, 3), dtype=np.uint8))
        capture.release.side_effect = OSError("private")
        with patch("cv2.VideoCapture", return_value=capture):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args)
        self.assertFalse(output.exists())

    def test_image_and_camera_options_are_mutually_exclusive(self):
        config, output, args = self.camera_case()
        with patch("cv2.VideoCapture") as camera:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args + ["--image", str(output.parent / "unused.png")])
            camera.assert_not_called()

    def test_user_interrupt_releases_camera_and_returns_130(self):
        config, output, args = self.camera_case()
        capture = Mock()
        capture.read.side_effect = KeyboardInterrupt()
        with patch("cv2.VideoCapture", return_value=capture):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                main(args)
        self.assertEqual(stopped.exception.code, 130)
        capture.release.assert_called_once()
        self.assertFalse(output.exists())

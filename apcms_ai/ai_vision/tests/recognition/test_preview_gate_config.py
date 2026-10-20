# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_preview_gate_config.py

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.preview_gate_config import main, render_preview


class PreviewGateConfigTests(unittest.TestCase):
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

# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_read_camera_frame.py

import unittest
from unittest.mock import Mock

import numpy as np

from ai_vision.recognition.read_camera_frame import read_camera_frame


class ReadCameraFrameTests(unittest.TestCase):
    def test_frame_copied_before_device_release_and_returned_after_release(self):
        original = np.full((80, 120, 3), 7, dtype=np.uint8)
        capture = Mock()
        capture.read.return_value = (True, original)
        capture.release.side_effect = lambda: original.fill(0)
        frame = read_camera_frame(0, lambda index: capture)
        self.assertTrue((frame == 7).all())
        self.assertFalse(original.any())
        capture.read.assert_called_once()
        capture.release.assert_called_once()

    def test_release_failure_or_read_failure_does_not_return_image(self):
        for failure in ("read", "release"):
            capture = Mock()
            capture.read.return_value = (failure != "read", np.zeros((80, 120, 3), dtype=np.uint8))
            if failure == "release":
                capture.release.side_effect = OSError("private device error")
            with self.assertRaises(ValueError) as caught:
                read_camera_frame(0, lambda index: capture)
            self.assertNotIn("private", str(caught.exception))
            capture.release.assert_called_once()

# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_camera_probe.py

import unittest
from unittest.mock import Mock

import numpy as np

from ai_vision.recognition.live_gate_camera_probe import probe_camera


class LiveGateCameraProbeTests(unittest.TestCase):
    def test_single_frame_resolution_and_release(self):
        capture = Mock()
        capture.read.return_value = (True, np.zeros((80, 120, 3), dtype=np.uint8))
        result = probe_camera(1, lambda index: capture)
        self.assertEqual((result["status"], result["width"], result["height"], result["released"]),
                         ("FRAME_READ", 120, 80, True))
        capture.read.assert_called_once()
        capture.release.assert_called_once()

    def test_failures_still_release_and_hide_exception_details(self):
        for failure in ("open", "read", "invalid", "exception", "release"):
            capture = Mock()
            capture.isOpened.return_value = failure != "open"
            capture.read.return_value = (failure != "read", None)
            if failure == "exception":
                capture.read.side_effect = RuntimeError("private camera details")
            if failure == "release":
                capture.read.return_value = (True, np.zeros((80, 120, 3), dtype=np.uint8))
                capture.release.side_effect = RuntimeError("private camera details")
            result = probe_camera(0, lambda index: capture)
            self.assertEqual(result["status"], "FAILED")
            self.assertNotIn("private", str(result))
            capture.release.assert_called_once()

    def test_invalid_index_never_opens_and_interrupt_releases(self):
        factory = Mock()
        for index in (True, -1, 33, "0"):
            with self.assertRaises(ValueError):
                probe_camera(index, factory)
        factory.assert_not_called()
        capture = Mock()
        capture.read.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            probe_camera(0, lambda index: capture)
        capture.release.assert_called_once()

    def test_optional_consumer_failure_still_releases_with_fixed_reason(self):
        capture = Mock()
        capture.read.return_value = (True, np.zeros((80, 120, 3), dtype=np.uint8))
        consumer = Mock(side_effect=RuntimeError("private error"))
        result = probe_camera(0, lambda index: capture, frame_consumer=consumer)
        self.assertEqual((result["status"], result["reason"], result["released"]), ("FAILED", "FRAME_CONSUMER_FAILED", True))
        capture.release.assert_called_once()

    def test_non_callable_consumer_rejected_before_opening(self):
        factory = Mock()
        with self.assertRaises(ValueError):
            probe_camera(0, factory, frame_consumer=False)
        factory.assert_not_called()

# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_lifecycle.py

import unittest
from unittest.mock import Mock

from ai_vision.recognition.live_gate_lifecycle import close_resources


class LiveGateLifecycleTests(unittest.TestCase):
    def test_all_resources_attempted_even_when_first_two_fail(self):
        capture, processor, session = Mock(), Mock(), Mock()
        capture.release.side_effect = OSError("capture")
        processor.close.side_effect = RuntimeError("processor")
        self.assertEqual(close_resources(capture, processor, session), 2)
        session.close.assert_called_once()
        capture.release.assert_called_once()
        processor.close.assert_called_once()

    def test_missing_resources_and_repeated_calls(self):
        self.assertEqual(close_resources(), 0)
        session = Mock()
        self.assertEqual(close_resources(session=session), 0)
        session.close.assert_called_once()

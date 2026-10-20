# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_deadline.py

import unittest

from ai_vision.recognition.live_gate_deadline import LiveGateDeadline, validate_deadline


class LiveGateDeadlineTests(unittest.TestCase):
    def test_exact_boundary_expires_and_summary_is_last_checked_time(self):
        deadline = LiveGateDeadline(2, iter((10, 10, 11, 12)).__next__)
        self.assertFalse(deadline.before_read())
        self.assertFalse(deadline.before_read())
        self.assertTrue(deadline.before_read())
        value = validate_deadline(deadline.summary())
        self.assertEqual((value["checks"], value["last_checked_elapsed_seconds"]), (3, 2))

    def test_invalid_and_reverse_clocks_rejected_without_advancing(self):
        for limit in (0, -1, True, float("nan"), 301):
            with self.assertRaises(ValueError):
                LiveGateDeadline(limit)
        deadline = LiveGateDeadline(2, iter((10, 11, 10)).__next__)
        deadline.before_read()
        with self.assertRaises(ValueError):
            deadline.before_read()
        self.assertEqual(deadline.summary()["checks"], 1)

    def test_inconsistent_saved_checks_rejected(self):
        value = LiveGateDeadline(2, lambda: 10).summary()
        self.assertEqual(validate_deadline(value), value)
        for changes in ({"checks": True}, {"checks": -1}, {"expired_before_read": True},
                        {"last_checked_elapsed_seconds": 1}, {"seconds": 0}):
            with self.assertRaises(ValueError):
                validate_deadline({**value, **changes})

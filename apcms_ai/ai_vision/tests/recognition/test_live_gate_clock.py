# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_clock.py

import unittest
from datetime import datetime, timedelta, timezone
from ai_vision.recognition.live_gate_clock import LiveGateClock


class LiveGateClockTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.clock = LiveGateClock(self.start, 10)

    def test_monotonic_elapsed_maps_to_timezone_aware_capture_time(self):
        first = self.clock.capture(0, 10)
        second = self.clock.capture(1, 10.5)
        self.assertEqual(first.captured_at, self.start)
        self.assertEqual(second.captured_at, self.start + timedelta(seconds=.5))
        self.assertIs(self.clock.lookup(1), second)

    def test_repeated_frame_and_reverse_time_do_not_advance_clock(self):
        self.clock.capture(0, 10)
        for index, value in ((0, 11), (1, 10), (1, 9), (True, 11), (1, float("nan"))):
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                self.clock.capture(index, value)
        self.assertEqual(self.clock.frame_count, 1)
        self.clock.capture(1, 11)

    def test_history_is_bounded_and_invalid_lookup_is_rejected(self):
        clock = LiveGateClock(self.start, 0, history_limit=2)
        for index in range(3):
            clock.capture(index, index)
        for index in (0, True, 99, -1):
            with self.assertRaises(ValueError):
                clock.lookup(index)

    def test_invalid_start_and_limits_are_rejected(self):
        for kwargs in ({"started_at": datetime(2020, 1, 1)}, {"monotonic_start": -1},
                       {"history_limit": 0}, {"history_limit": True}):
            with self.assertRaises(ValueError):
                LiveGateClock(**kwargs)

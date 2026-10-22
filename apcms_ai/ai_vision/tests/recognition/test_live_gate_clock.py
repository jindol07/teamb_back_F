# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_clock.py

import unittest
from datetime import datetime, timedelta, timezone
from ai_vision.recognition.live_gate_clock import LiveGateClock


class LiveGateClockTests(unittest.TestCase):
    def test_retained_original_stamp_survives_history_eviction_until_released(self):
        clock = LiveGateClock(monotonic_start=0, history_limit=1)
        original = clock.capture(0, 0)
        token = clock.retain([0])
        clock.capture(1, 1)
        self.assertIs(clock.lookup(0), original)
        clock.release_retained(token)
        with self.assertRaises(ValueError):
            clock.lookup(0)

    def test_retention_limit_and_missing_stamp_do_not_partially_mutate(self):
        clock = LiveGateClock(monotonic_start=0)
        clock.capture(0, 0)
        for indices in ([0, 99], [True], list(range(5))):
            with self.assertRaises(ValueError):
                clock.retain(indices)
            self.assertFalse(clock._retained)
        first, second = clock.retain([0]), clock.retain([0])
        with self.assertRaises(ValueError):
            clock.retain([0])
        self.assertEqual(len(clock._retained), 2)
        clock.release_retained(first)
        clock.release_retained(second)

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

    def test_oldest_frame_boundary_tracks_eviction_and_nonconsecutive_indices(self):
        clock = LiveGateClock(self.start, 0, history_limit=2)
        self.assertIsNone(clock.oldest_frame_index)
        clock.capture(10, 0)
        clock.capture(20, .1)
        self.assertEqual(clock.oldest_frame_index, 10)
        clock.capture(30, .2)
        self.assertEqual(clock.oldest_frame_index, 20)
        self.assertEqual(clock.lookup(clock.oldest_frame_index).frame_index, 20)

    def test_invalid_start_and_limits_are_rejected(self):
        for kwargs in ({"started_at": datetime(2020, 1, 1)}, {"monotonic_start": -1},
                       {"history_limit": 0}, {"history_limit": True}):
            with self.assertRaises(ValueError):
                LiveGateClock(**kwargs)

# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_latest_frame_capture.py

"""느린 처리 중 수집 지속·오래된 프레임 폐기·실패·장치 해제를 확인합니다."""

import contextlib
import io
import queue
import unittest
from unittest.mock import Mock

import numpy as np

from ai_vision.recognition.latest_frame_capture import LatestFrameCapture
from ai_vision.recognition.live_gate_clock import LiveGateClock
from ai_vision.recognition.live_gate_session import LiveGateSession
from ai_vision.recognition.run_live_gate import execute, main


class Source:
    def __init__(self):
        self.frames = queue.Queue()
        self.releases = 0

    def isOpened(self):
        return True

    def read(self):
        value = self.frames.get(timeout=2)
        if isinstance(value, Exception):
            raise value
        return (False, None) if value is None else (True, value)

    def release(self):
        self.releases += 1


class LatestFrameCaptureTests(unittest.TestCase):
    def test_equal_windows_clock_ticks_drop_only_duplicate_and_keep_collecting(self):
        self.capture._reader = iter((10, 10, 11)).__next__
        self.feed(1)
        self.capture.read()
        self.feed(2)
        self.feed(3)
        self.wait_for_frames(3)
        ok, frame = self.capture.read()
        self.assertTrue(ok)
        self.assertEqual(int(frame[0, 0, 0]), 3)
        self.assertEqual(self.capture.captured_monotonic, 11)
        self.assertEqual(self.capture.summary()['duplicate_timestamp_frames'], 1)
        self.assertIsNone(self.capture.summary()['worker_error'])

    def test_reversed_clock_is_still_an_error(self):
        self.capture._reader = iter((10, 9)).__next__
        self.feed(1)
        self.capture.read()
        self.feed(2)
        with self.assertRaises(RuntimeError):
            self.capture.read()

    def setUp(self):
        self.source = Source()
        self.capture = LatestFrameCapture(self.source, reader=iter(range(10, 100)).__next__, read_timeout=.2)
        self.addCleanup(self.finish)

    def finish(self):
        self.source.frames.put(None)
        try:
            self.capture.release()
        except RuntimeError:
            pass  # 오류 전달 여부는 개별 검사에서 확인하며 종료는 항상 진행합니다.

    def feed(self, value):
        self.source.frames.put(np.full((8, 8, 3), value, dtype=np.uint8))

    def wait_for_frames(self, count):
        # 임의의 sleep 대신 수집 스레드의 통지로 시험 순서를 맞춥니다.
        with self.capture._condition:
            self.assertTrue(self.capture._condition.wait_for(lambda: self.capture._captured >= count, timeout=1))

    def test_collection_continues_and_only_latest_waits_for_slow_consumer(self):
        self.feed(1)
        self.assertEqual(int(self.capture.read()[1][0, 0, 0]), 1)
        self.feed(2)
        self.feed(3)
        self.wait_for_frames(3)
        self.assertEqual(int(self.capture.read()[1][0, 0, 0]), 3)
        self.assertEqual(self.capture.captured_monotonic, 12)
        summary = self.capture.summary()
        self.assertEqual((summary['captured_frames'], summary['delivered_frames'], summary['dropped_frames']), (3, 2, 1))
        self.assertEqual(summary['peak_pending_bytes'], 8 * 8 * 3)

    def test_frame_copy_is_independent_of_driver_buffer(self):
        frame = np.full((8, 8, 3), 1, dtype=np.uint8)
        self.source.frames.put(frame)
        delivered = self.capture.read()[1]
        frame.fill(9)
        self.assertEqual(int(delivered[0, 0, 0]), 1)

    def test_source_end_drains_last_frame_and_releases_once(self):
        self.feed(1)
        self.capture.read()
        self.source.frames.put(None)
        self.assertEqual(self.capture.read(), (False, None))
        self.capture.release()
        self.capture.release()
        self.assertEqual(self.source.releases, 1)

    def test_source_error_is_not_hidden_as_normal_end(self):
        self.source.frames.put(OSError('private driver message'))
        with self.assertRaises(RuntimeError) as error:
            self.capture.read()
        self.assertNotIn('private', str(error.exception))
        with self.assertRaises(RuntimeError):
            self.capture.release()

    def test_oversized_frame_is_rejected_before_copying(self):
        self.capture._budget = 1
        self.feed(1)
        with self.assertRaises(RuntimeError):
            self.capture.read()
        self.assertEqual(self.capture.summary()['captured_frames'], 0)

    def test_blocked_driver_reports_timeout_and_releases_when_read_returns(self):
        self.capture._close_timeout = .01
        with self.assertRaises(TimeoutError):
            self.capture.read()
        with self.assertRaises(TimeoutError):
            self.capture.release()
        self.source.frames.put(None)
        self.capture._thread.join(1)
        self.assertFalse(self.capture.summary()['worker_alive'])
        self.assertEqual(self.source.releases, 1)

    def test_execute_preserves_camera_timestamp_and_capture_during_processing(self):
        self.capture._reader = iter((.1, .4, .7)).__next__
        self.feed(1)
        source, capture = self.source, self.capture
        seen = []
        def process(frame, stamp):
            seen.append((int(frame[0, 0, 0]), stamp.elapsed_seconds))
            if len(seen) == 1:
                self.feed(2)
                self.feed(3)
                self.wait_for_frames(3)
                source.frames.put(None)
            return []
        processor = Mock()
        processor.process.side_effect = process
        session = LiveGateSession('BUFFER_TEST', 'ENTRY', clock=LiveGateClock(monotonic_start=0))
        report = execute(capture, processor, session, seconds=2, allow_source_end=True,
                         monotonic_reader=Mock(side_effect=AssertionError('수집 시각을 덮어쓰면 안 됩니다.')),
                         deadline_reader=lambda: 0)
        self.assertEqual(report['status'], 'STOPPED')
        self.assertEqual(seen, [(1, .1), (3, .7)])
        self.assertEqual(report['capture_buffer']['dropped_frames'], 1)
        self.assertFalse(report['capture_buffer']['worker_alive'])
        self.assertEqual(report['request_attempts'], 0)

    def test_demo_rejects_buffered_physical_capture(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['--demo', '--buffered-capture', '--output-dir', 'unused'])

    def test_invalid_limits_rejected_without_releasing_unowned_camera(self):
        for kwargs in ({'read_timeout': True}, {'close_timeout': 0}, {'max_frame_bytes': 0}):
            with self.assertRaises(ValueError):
                LatestFrameCapture(self.source, **kwargs)
        self.assertEqual(self.source.releases, 0)

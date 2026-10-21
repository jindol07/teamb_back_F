# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_async_gate_processor.py

"""느린 OCR 중 추적 지속, 유한 대기열, 원본 시각, 오류·종료 처리를 확인합니다."""

import contextlib
import io
import threading
import unittest
from unittest.mock import Mock, patch

import numpy as np

from ai_vision.recognition.async_gate_processor import AsyncGateProcessor
from ai_vision.recognition.live_gate_clock import LiveGateClock
from ai_vision.recognition.live_gate_processor import LiveGateProcessor
from ai_vision.recognition.live_gate_session import LiveGateSession
from ai_vision.recognition.live_gate_report import validate_report
from ai_vision.recognition.run_live_gate import execute, main


CONFIG = {'tracker': 'bytetrack', 'line_y': .5, 'line_x': [.1, .9], 'roi': [0, 0, 1, 0, 1, 1, 0, 1]}
SAMPLE = {'plate_number': '91소6408', 'plate_type': 'KOREAN_VALID', 'plate_detection_confidence': .9}


def tracker(frame):
    index = int(frame[0, 0, 0])
    rows = []
    for track_id, start in ((7, 0), (8, 7), (9, 14)):
        if index < start:
            continue
        age = index - start
        y = 20 if age < 3 else (50 if age == 3 else 80)
        rows.append({'track_id': track_id, 'box': [40, y - 10, 60, y + 10]})
    return rows


class AsyncGateProcessorTests(unittest.TestCase):
    def setUp(self):
        self.entered, self.resume = threading.Event(), threading.Event()
        def read(crop):
            self.entered.set()
            if not self.resume.wait(3):
                raise TimeoutError('시험 OCR 대기 시간 초과')
            return dict(SAMPLE)
        self.reader = Mock(side_effect=read)
        self.base = LiveGateProcessor(CONFIG, tracker, self.reader)
        self.processor = AsyncGateProcessor(self.base)
        self.session = LiveGateSession('ASYNC_TEST', 'ENTRY', clock=LiveGateClock(monotonic_start=0, history_limit=4))
        self.addCleanup(self.finish)

    def finish(self):
        self.resume.set()
        try:
            self.processor.close()
        except RuntimeError:
            pass
        self.session.close()

    def frames(self, start, end):
        for index in range(start, end):
            stamp = self.session.capture(index, index * .3)
            self.processor.submit_frame(np.full((100, 100, 3), index, dtype=np.uint8), stamp, self.session)

    def test_slow_ocr_does_not_stop_tracking_and_queue_overflow_is_counted(self):
        self.frames(0, 7)
        self.assertTrue(self.entered.wait(1))
        self.frames(7, 21)
        self.assertEqual(self.base.statistics()['frames'], 21)
        self.assertEqual(self.reader.call_count, 1)
        self.assertEqual(self.processor.summary()['submitted_jobs'], 2)
        self.assertEqual(self.processor.summary()['dropped_jobs'], 1)
        self.assertEqual(len(self.session.clock._retained), 2)
        self.resume.set()
        self.processor._pending[-1][0].result(timeout=2)
        results = []
        for passage, stamp in self.processor.completed():
            results.append(self.session.consume(passage, stamp))
            self.assertEqual(passage['plate_consensus']['status'], 'CONFIRMED')
        self.assertEqual([row['decision'] for row in results], ['DISABLED', 'DISABLED'])
        self.assertEqual(self.session.summary()['request_attempts'], 0)
        self.assertFalse(self.session.clock._retained)
        with self.assertRaises(ValueError):
            self.session.clock.lookup(4)

    def test_pending_image_budget_rejects_without_ocr_or_retained_timestamps(self):
        self.processor._budget = 1
        self.frames(0, 7)
        self.reader.assert_not_called()
        self.assertEqual(self.processor.summary()['dropped_jobs'], 1)
        self.assertFalse(self.session.clock._retained)

    def test_close_cancels_queued_job_and_remaining_samples_without_late_delivery(self):
        self.frames(0, 14)
        self.assertTrue(self.entered.wait(1))
        closer = threading.Thread(target=self.processor.close)
        closer.start()
        self.assertTrue(self.processor._cancel.wait(1))
        self.resume.set()
        closer.join(2)
        self.assertFalse(closer.is_alive())
        self.assertEqual(self.reader.call_count, 1)
        self.assertEqual(self.processor.summary()['abandoned_jobs'], 2)
        self.assertFalse(self.session.clock._retained)
        self.assertEqual(self.session.summary()['processed_passages'], 0)
        self.assertEqual(self.session.summary()['request_attempts'], 0)

    def test_worker_failure_is_raised_and_timestamp_refs_released(self):
        self.reader.side_effect = ValueError('비공개 서버 정보')
        self.frames(0, 7)
        future = self.processor._pending[0][0]
        with self.assertRaises(ValueError):
            future.result(timeout=1)
        with self.assertRaises(ValueError):
            list(self.processor.completed())
        self.assertFalse(self.session.clock._retained)
        self.assertEqual(self.processor.summary()['worker_error_types'], ['ValueError'])
        self.assertEqual(self.session.summary()['request_attempts'], 0)

    def test_late_worker_error_is_not_hidden_by_close(self):
        self.reader.side_effect = ValueError('서버 정보')
        self.frames(0, 7)
        with self.assertRaises(ValueError):
            self.processor._pending[0][0].result(timeout=1)
        with self.assertRaises(RuntimeError):
            self.processor.close()
        self.assertFalse(self.session.clock._retained)
        self.assertEqual(self.processor.summary()['abandoned_jobs'], 1)

    def test_execute_delivers_old_crossing_with_original_time_after_history_eviction(self):
        test = self
        class Capture:
            index = 0
            def isOpened(self):
                return True
            def read(self):
                index = self.index
                self.index += 1
                if index == 7:
                    test.assertTrue(test.entered.wait(1))
                if index == 21:
                    test.resume.set()
                    test.processor._pending[-1][0].result(timeout=2)
                return (True, np.full((100, 100, 3), index, dtype=np.uint8)) if index < 23 else (False, None)
            def release(self):
                pass
        report = execute(Capture(), self.processor, self.session, seconds=30,
                         monotonic_reader=iter(i * .3 for i in range(23)).__next__,
                         deadline_reader=lambda: 0, allow_source_end=True)
        self.assertEqual(report['status'], 'STOPPED')
        self.assertEqual(report['captured_frames'], 23)
        self.assertEqual(report['processed_passages'], 2)
        self.assertAlmostEqual(report['results'][0]['crossing_elapsed_seconds'], 1.8)
        self.assertEqual(report['request_attempts'], 0)
        self.assertEqual(report['async_ocr']['pending_jobs'], 0)
        validate_report({**report, 'uses_synthetic_source': True})

    def test_invalid_pending_limits(self):
        for options in ({'max_pending': True}, {'max_pending': 3}, {'max_pending_bytes': 0}):
            with self.assertRaises(ValueError):
                AsyncGateProcessor(self.base, **options)

    def test_cli_requires_remote_mode(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['--async-ocr', '--output-dir', 'unused'])

    def test_cli_connects_remote_async_processor_and_buffered_camera(self):
        from ai_vision.recognition.latest_frame_capture import LatestFrameCapture
        def finish(capture, processor, session, **kwargs):
            self.assertIsInstance(processor, AsyncGateProcessor)
            self.assertIsInstance(capture, LatestFrameCapture)
            self.assertFalse(session.flow.client.enabled)
            capture.release()
            processor.close()
            session.close()
            return {**session.summary(), 'status': 'STOPPED', 'async_ocr': processor.summary()}
        with patch('ai_vision.recognition.run_live_gate.read_json', return_value=CONFIG), \
                patch('ai_vision.recognition.run_live_gate.write_json_atomic'), patch('pathlib.Path.mkdir'), \
                patch('ai_vision.recognition.run_live_gate.LiveGateProcessor') as base, \
                patch('ai_vision.recognition.remote_plate_reader.RemotePlateReader') as reader, \
                patch('cv2.VideoCapture') as capture, \
                patch('ai_vision.recognition.run_live_gate.execute', side_effect=finish), \
                contextlib.redirect_stdout(io.StringIO()):
            main(['--config', 'unused.json', '--camera-id', 'CLI_TEST', '--down-direction', 'ENTRY',
                  '--async-ocr', '--buffered-capture', '--vision-api-url', 'http://127.0.0.1:18000',
                  '--output-dir', 'unused-async-cli-output'])
        base.assert_called_once_with(CONFIG, plate_reader=reader.return_value.read)
        base.return_value.prepare.assert_called_once()
        base.return_value.close.assert_called_once()
        capture.return_value.release.assert_called_once()

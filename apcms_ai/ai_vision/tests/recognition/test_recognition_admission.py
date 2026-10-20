# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_recognition_admission.py

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

from ai_vision.recognition.recognition_admission import RecognitionAdmission


class RecognitionAdmissionTests(unittest.TestCase):
    def test_capacity_and_pending_release_are_bounded_and_idempotent(self):
        admission = RecognitionAdmission(2)
        first, second = admission.try_acquire(), admission.try_acquire()
        self.assertIsNone(admission.try_acquire())
        self.assertTrue(first.cancel_pending())
        self.assertFalse(first.cancel_pending())
        replacement = admission.try_acquire()
        self.assertIsNotNone(replacement)
        self.assertIsNone(admission.try_acquire())
        second.cancel_pending()
        replacement.cancel_pending()

    def test_operation_failure_returns_slot_and_cancelled_work_cannot_run(self):
        admission = RecognitionAdmission(1)
        lease = admission.try_acquire()
        with self.assertRaises(ValueError):
            lease.run(Mock(side_effect=ValueError("failed")))
        lease = admission.try_acquire()
        self.assertIsNotNone(lease)
        lease.cancel_pending()
        operation = Mock()
        with self.assertRaises(RuntimeError):
            lease.run(operation)
        operation.assert_not_called()

    def test_running_work_keeps_slot_until_completion(self):
        admission = RecognitionAdmission(1)
        lease = admission.try_acquire()
        started, release = threading.Event(), threading.Event()
        def operation():
            started.set()
            release.wait(2)
            return "done"
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lease.run, operation)
            try:
                self.assertTrue(started.wait(1))
                self.assertFalse(lease.cancel_pending())
                self.assertIsNone(admission.try_acquire())
            finally:
                release.set()
            self.assertEqual(future.result(timeout=1), "done")
        replacement = admission.try_acquire()
        self.assertIsNotNone(replacement)
        replacement.cancel_pending()

    def test_invalid_capacity_rejected(self):
        for value in (0, -1, True, 17, 1.5):
            with self.assertRaises(ValueError):
                RecognitionAdmission(value)

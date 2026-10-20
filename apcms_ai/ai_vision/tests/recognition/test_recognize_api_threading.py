# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_recognize_api_threading.py

import asyncio
import contextlib
import importlib.util
import io
import threading
import unittest
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import cv2
from fastapi import HTTPException

from ai_vision.paths import BASE_DIR
from ai_vision.tests.recognition.asyncio_runtime_check import ensure_asyncio_runtime
from ai_vision.recognition.recognition_admission import RecognitionAdmission


class RecognizeAPIThreadingTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        ensure_asyncio_runtime()

    def setUp(self):
        spec = importlib.util.spec_from_file_location("ai_vision._recognize_api_thread_test", BASE_DIR / "main.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.file = Mock(content_type="image/png")
        self.image = np.zeros((20, 20, 3), dtype=np.uint8)
        self.file.read = AsyncMock(return_value=cv2.imencode(".png", self.image)[1].tobytes())

    async def test_sync_inference_runs_in_worker_and_event_loop_stays_responsive(self):
        main_thread = threading.get_ident()
        started, release = threading.Event(), threading.Event()
        threads = []
        def inference(image):
            threads.append(threading.get_ident())
            started.set()
            if not release.wait(2):
                raise RuntimeError("test release timeout")
            return {"success": True, "vehicle_count": 1, "vehicles": []}
        with patch.object(self.module, "recognize_image", side_effect=inference):
            task = asyncio.create_task(self.module.recognize(self.file))
            try:
                self.assertTrue(await asyncio.wait_for(asyncio.to_thread(started.wait, 1), 1.5))
                self.assertEqual(await asyncio.wait_for(asyncio.sleep(0, result="responsive"), .5), "responsive")
                self.assertFalse(task.done())
            finally:
                release.set()
            result = await asyncio.wait_for(task, 1)
        self.assertEqual(result["vehicle_count"], 1)
        self.assertNotEqual(threads[0], main_thread)

    async def test_inference_exception_keeps_generic_500_response(self):
        with patch.object(self.module, "recognize_image", side_effect=RuntimeError("private model path")), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(HTTPException) as caught:
                await self.module.recognize(self.file)
        self.assertEqual(caught.exception.status_code, 500)
        self.assertNotIn("private", caught.exception.detail)

    async def test_invalid_input_does_not_start_inference(self):
        self.file.content_type = "text/plain"
        with patch.object(self.module, "recognize_image") as inference:
            with self.assertRaises(HTTPException) as caught:
                await self.module.recognize(self.file)
            self.assertEqual(caught.exception.status_code, 400)
            inference.assert_not_called()
            self.file.read.assert_not_awaited()

    async def test_upload_read_is_bounded_to_limit_plus_one_byte(self):
        with patch.object(self.module, "recognize_image", return_value={"success": True}):
            await self.module.recognize(self.file)
        self.file.read.assert_awaited_once_with(self.module.MAX_UPLOAD_BYTES + 1)

    async def test_busy_rejected_before_read_or_inference(self):
        admission = RecognitionAdmission(1)
        lease = admission.try_acquire()
        try:
            with patch.object(self.module, "_recognition_admission", admission), patch.object(self.module, "recognize_image") as inference:
                with self.assertRaises(HTTPException) as caught:
                    await self.module.recognize(self.file)
                self.assertEqual(caught.exception.status_code, 503)
                self.assertEqual(caught.exception.headers["Retry-After"], "1")
                self.file.read.assert_not_awaited()
                inference.assert_not_called()
        finally:
            lease.cancel_pending()

    async def test_cancel_before_read_finishes_returns_pending_slot(self):
        admission, started = RecognitionAdmission(1), asyncio.Event()
        async def read(size):
            started.set()
            await asyncio.Event().wait()
        self.file.read = AsyncMock(side_effect=read)
        with patch.object(self.module, "_recognition_admission", admission):
            task = asyncio.create_task(self.module.recognize(self.file))
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        replacement = admission.try_acquire()
        self.assertIsNotNone(replacement)
        replacement.cancel_pending()

    async def test_cancel_running_request_does_not_open_slot_before_worker_finishes(self):
        admission = RecognitionAdmission(1)
        started, release = threading.Event(), threading.Event()
        def inference(image):
            started.set()
            release.wait(2)
            return {"success": True}
        with patch.object(self.module, "_recognition_admission", admission), patch.object(self.module, "recognize_image", side_effect=inference):
            task = asyncio.create_task(self.module.recognize(self.file))
            try:
                self.assertTrue(await asyncio.wait_for(asyncio.to_thread(started.wait, 1), 1.5))
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertIsNone(admission.try_acquire())
            finally:
                release.set()
            replacement = None
            for _ in range(100):
                replacement = admission.try_acquire()
                if replacement is not None:
                    break
                await asyncio.sleep(.01)
            self.assertIsNotNone(replacement)
            replacement.cancel_pending()

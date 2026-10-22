# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_upload_limits.py

"""파싱 전 본문·동시 업로드 한도와 임시 파일 해제를 검사합니다."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch
import cv2
import numpy as np
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
import starlette.formparsers

from ai_vision.app import create_app
from ai_vision.upload_limits import UploadLimitsMiddleware
from ai_vision.tests.recognition.asyncio_runtime_check import ensure_asyncio_runtime


def scope_for(headers=()):
    return {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
            "scheme": "http", "path": "/recognize", "raw_path": b"/recognize", "root_path": "",
            "query_string": b"", "headers": list(headers), "client": ("test", 1), "server": ("test", 80)}


async def raw_request(app, chunks, headers=()):
    messages, incoming = [], iter(chunks)
    async def receive():
        return next(incoming, {"type": "http.disconnect"})
    async def send(message):
        messages.append(message)
    await app(scope_for(headers), receive, send)
    return messages


class UploadLimitsTests(unittest.TestCase):
    def test_reverse_proxy_root_path_is_limited(self):
        for path in ("/gateway/recognize", "/recognize"):
            app, receive, send = AsyncMock(), AsyncMock(), AsyncMock()
            scope = scope_for([(b"content-length", b"129")])
            scope.update(root_path="/gateway", path=path)
            asyncio.run(UploadLimitsMiddleware(app, max_bytes=128)(scope, receive, send))
            self.assertEqual(send.call_args_list[0].args[0]["status"], 413)
            app.assert_not_called()

    def test_invalid_limit_configuration_is_rejected(self):
        for options in ({"max_bytes": True}, {"capacity": 0}, {"read_timeout": 0},
                        {"upload_timeout": float("nan")}, {"read_timeout": True}):
            with self.assertRaises(ValueError):
                UploadLimitsMiddleware(AsyncMock(), **options)

    def test_slow_upload_returns_408_and_releases_slot(self):
        async def check():
            from fastapi import FastAPI, UploadFile, File
            from ai_vision.upload_limits import SingleImageUploadRoute
            app = FastAPI()
            app.router.route_class = SingleImageUploadRoute
            @app.post("/recognize")
            async def endpoint(file: UploadFile = File(...)):
                return {"ok": True}
            limited = UploadLimitsMiddleware(app, capacity=1, read_timeout=.01)
            # 요청 본문을 보내지 않는 클라이언트를 모의합니다.
            async def slow_receive():
                await asyncio.Event().wait()
            messages = []
            async def send(message):
                messages.append(message)
            headers = [(b"content-type", b"multipart/form-data; boundary=boundary")]
            await limited(scope_for(headers), slow_receive, send)
            self.assertEqual(messages[0]["status"], 408)
            # 같은 처리기의 다음 잘못된 요청도 503이 아닌 파싱 오류로 돌아와야 합니다.
            result = await raw_request(limited, [{"type": "http.request", "body": b"", "more_body": False}], headers)
            self.assertNotEqual(result[0]["status"], 503)
        asyncio.run(check())

    def test_total_upload_deadline_is_checked_before_read(self):
        async def app(scope, receive, send):
            try:
                await receive()
            except starlette.formparsers.MultiPartException:
                await JSONResponse({"detail": "parser failure"}, status_code=400)(scope, receive, send)
        limited = UploadLimitsMiddleware(app, upload_timeout=1)
        async def check():
            messages = []
            async def send(message):
                messages.append(message)
            with patch("ai_vision.upload_limits.monotonic", side_effect=[0, 2]):
                await limited(scope_for(), AsyncMock(), send)
            self.assertEqual(messages[0]["status"], 408)
        asyncio.run(check())
    @classmethod
    def setUpClass(cls):
        ensure_asyncio_runtime()

    def test_valid_single_image_and_extra_file_or_field(self):
        png = cv2.imencode(".png", np.zeros((20, 20, 3), dtype=np.uint8))[1].tobytes()
        with TestClient(create_app()) as client, patch("ai_vision.main.recognize_image", return_value={"success": True}) as inference:
            file = ("image.png", png, "image/png")
            self.assertEqual(client.post("/recognize", files={"file": file}).status_code, 200)
            inference.reset_mock()
            self.assertEqual(client.post("/recognize", files=[("file", file), ("extra", file)]).status_code, 400)
            self.assertEqual(client.post("/recognize", files={"file": file}, data={"extra": "value"}).status_code, 400)
            inference.assert_not_called()

    def test_content_length_limit_rejects_before_reading_or_app(self):
        app, receive, send = AsyncMock(), AsyncMock(), AsyncMock()
        limited = UploadLimitsMiddleware(app, max_bytes=128)
        asyncio.run(limited(scope_for([(b"content-length", b"129")]), receive, send))
        self.assertEqual(send.call_args_list[0].args[0]["status"], 413)
        receive.assert_not_called()
        app.assert_not_called()

    def test_bad_content_lengths_return_400(self):
        for headers in ([(b"content-length", b"-1")], [(b"content-length", b"bad")],
                        [(b"content-length", b"1"), (b"content-length", b"2")]):
            app, receive, send = AsyncMock(), AsyncMock(), AsyncMock()
            asyncio.run(UploadLimitsMiddleware(app)(scope_for(headers), receive, send))
            self.assertEqual(send.call_args_list[0].args[0]["status"], 400)
            app.assert_not_called()

    def test_chunked_or_underreported_body_is_bounded_and_temp_files_closed(self):
        prefix = b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="image.png"\r\nContent-Type: image/png\r\n\r\n'
        chunks = [{"type": "http.request", "body": prefix + b"x" * 20, "more_body": True},
                  {"type": "http.request", "body": b"x" * 300 + b"\r\n--boundary--\r\n", "more_body": False}]
        original = starlette.formparsers.SpooledTemporaryFile
        created = []
        def tracked(*args, **kwargs):
            file = original(*args, **kwargs)
            created.append(file)
            return file
        for length in ([], [(b"content-length", b"1")]):
            with patch("ai_vision.upload_limits.MAX_MULTIPART_BYTES", 256), \
                    patch("starlette.formparsers.SpooledTemporaryFile", side_effect=tracked), \
                    patch("ai_vision.main.recognize_image") as inference:
                messages = asyncio.run(raw_request(create_app(), chunks,
                    [(b"content-type", b"multipart/form-data; boundary=boundary")] + length))
            self.assertEqual(messages[0]["status"], 413)
            self.assertIn(b"x-request-id", dict(messages[0]["headers"]))
            inference.assert_not_called()
        self.assertEqual(len(created), 2)
        self.assertTrue(all(file.closed for file in created))

    def test_concurrent_upload_limit_releases_slot_after_completion(self):
        async def check():
            entered, release = asyncio.Event(), asyncio.Event()
            async def app(scope, receive, send):
                entered.set()
                await release.wait()
                await JSONResponse({"ok": True})(scope, receive, send)
            limited = UploadLimitsMiddleware(app, capacity=1)
            first = asyncio.create_task(raw_request(limited, []))
            await entered.wait()
            blocked = await raw_request(limited, [])
            self.assertEqual(blocked[0]["status"], 503)
            self.assertEqual(dict(blocked[0]["headers"])[b"retry-after"], b"1")
            release.set()
            self.assertEqual((await first)[0]["status"], 200)
            self.assertEqual((await raw_request(limited, []))[0]["status"], 200)
        asyncio.run(check())

    def test_cancelled_upload_releases_slot(self):
        async def check():
            entered, release = asyncio.Event(), asyncio.Event()
            async def app(scope, receive, send):
                entered.set()
                await release.wait()
                await JSONResponse({"ok": True})(scope, receive, send)
            limited = UploadLimitsMiddleware(app, capacity=1)
            task = asyncio.create_task(raw_request(limited, []))
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            release.set()
            self.assertEqual((await raw_request(limited, []))[0]["status"], 200)
        asyncio.run(check())

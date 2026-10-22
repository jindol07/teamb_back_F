# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_http_diagnostics.py

"""요청 상관관계·응답 호환성·민감 정보 제외를 모델 없이 확인합니다."""

import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient
from ai_vision.app import create_app
from ai_vision.http_diagnostics import REQUEST_ID
from ai_vision.tests.recognition.asyncio_runtime_check import ensure_asyncio_runtime


class HTTPDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_asyncio_runtime()

    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_headers_do_not_change_json_and_client_request_id_is_not_trusted(self):
        with self.assertLogs("uvicorn.error", level="INFO") as captured:
            response = self.client.get("/health?token=private-query", headers={"X-Request-ID": "private-id", "Authorization": "secret-key"})
        self.assertEqual(response.json(), {"status": "ok", "scope": "PROCESS_ONLY"})
        request_id = response.headers["x-request-id"]
        self.assertRegex(request_id, r"^[0-9a-f]{32}$")
        self.assertGreaterEqual(float(response.headers["server-timing"].split("=")[1]), 0)
        record = json.loads(captured.records[-1].getMessage())
        self.assertEqual((record["request_id"], record["status"], record["route"]), (request_id, 200, "/health"))
        for secret in ("private-query", "private-id", "secret-key"):
            self.assertNotIn(secret, str(captured.output))

    def test_unmatched_path_is_not_logged_verbatim(self):
        with self.assertLogs("uvicorn.error", level="INFO") as captured:
            response = self.client.get("/91소6408-private-path")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(captured.records[-1].getMessage())["route"], "UNMATCHED")
        self.assertNotIn("private-path", str(captured.output))

    def test_unhandled_error_is_sanitized_and_still_has_diagnostic_headers(self):
        @self.app.get("/broken")
        def broken():
            raise ValueError("secret-plate-and-path")
        with self.assertLogs("uvicorn.error", level="INFO") as captured:
            response = self.client.get("/broken")
        self.assertEqual(response.status_code, 500)
        self.assertIn("x-request-id", response.headers)
        self.assertNotIn("secret-plate-and-path", response.text + str(captured.output))
        self.assertEqual(json.loads(captured.records[-1].getMessage())["error_type"], "ValueError")

    def test_inference_error_is_correlated_without_ocr_or_filename_in_logs(self):
        png = cv2.imencode(".png", np.zeros((20, 20, 3), dtype=np.uint8))[1].tobytes()
        for error, status in ((RuntimeError("private-plate"), 500), (FileNotFoundError("private-plate"), 503)):
            with patch("ai_vision.main.recognize_image", side_effect=error), \
                    self.assertLogs("uvicorn.error", level="INFO") as captured:
                response = self.client.post("/recognize", files={"file": ("secret-filename.png", png, "image/png")})
            self.assertEqual(response.status_code, status)
            records = [json.loads(record.getMessage()) for record in captured.records]
            inference = next(record for record in records if record["event"] == "VISION_INFERENCE_ERROR")
            self.assertEqual(inference["request_id"], response.headers["x-request-id"])
            self.assertNotIn("private-plate", str(captured.output))
            self.assertNotIn("secret-filename", str(captured.output))

    def test_stream_failure_is_not_changed_into_second_response(self):
        from starlette.responses import StreamingResponse
        async def chunks():
            yield b"first-part"
            raise RuntimeError("private-stream-error")
        @self.app.get("/stream-failure")
        def streaming():
            return StreamingResponse(chunks())
        with self.assertLogs("uvicorn.error", level="INFO") as captured, self.assertRaises(RuntimeError):
            self.client.get("/stream-failure")
        record = json.loads(captured.records[-1].getMessage())
        self.assertEqual(record["status"], 200)
        self.assertTrue(record["response_started"])
        self.assertFalse(record["completed"])
        self.assertNotIn("private-stream-error", str(captured.output))

    def test_concurrent_requests_have_independent_ids(self):
        with self.assertLogs("uvicorn.error", level="INFO"):
            with ThreadPoolExecutor(max_workers=4) as pool:
                responses = list(pool.map(lambda _: self.client.get("/health"), range(8)))
        self.assertEqual(len({response.headers["x-request-id"] for response in responses}), 8)
        self.assertIsNone(REQUEST_ID.get())

    def test_cors_exposes_diagnostic_headers_to_allowed_browser(self):
        with patch.dict(os.environ, {"VISION_CORS_ORIGINS": '["https://frontend.example"]'}):
            application = create_app()
        with TestClient(application) as client:
            response = client.get("/health", headers={"Origin": "https://frontend.example"})
        self.assertEqual(response.headers["access-control-expose-headers"], "X-Request-ID, Server-Timing")

    def test_logging_failure_does_not_break_response(self):
        with patch("ai_vision.http_diagnostics.LOGGER.log", side_effect=OSError("logger unavailable")):
            self.assertEqual(self.client.get("/health").status_code, 200)

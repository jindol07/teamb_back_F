# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_recognize_upload_api.py

import importlib.util
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_vision.paths import BASE_DIR
from ai_vision.tests.recognition.asyncio_runtime_check import ensure_asyncio_runtime
from ai_vision.recognition.recognition_admission import RecognitionAdmission


class RecognizeUploadAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_asyncio_runtime()

    def setUp(self):
        spec = importlib.util.spec_from_file_location("ai_vision._recognize_upload_test", BASE_DIR / "main.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        app = FastAPI()
        app.include_router(self.module.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.png = cv2.imencode(".png", np.zeros((20, 20, 3), dtype=np.uint8))[1].tobytes()

    def test_valid_multipart_keeps_response_contract(self):
        expected = {"success": True, "vehicle_count": 0, "vehicles": []}
        with patch.object(self.module, "recognize_image", return_value=expected) as inference:
            response = self.client.post("/recognize", files={"file": ("sample.png", self.png, "image/png")})
        self.assertEqual((response.status_code, response.json()), (200, expected))
        self.assertEqual(inference.call_args.args[0].shape, (20, 20, 3))
        self.assertIn("413", self.client.app.openapi()["paths"]["/recognize"]["post"]["responses"])

    def test_byte_and_pixel_limit_return_413_without_inference(self):
        with patch.object(self.module, "MAX_UPLOAD_BYTES", 32), patch.object(self.module, "recognize_image") as inference:
            response = self.client.post("/recognize", files={"file": ("large.png", self.png, "image/png")})
            self.assertEqual(response.status_code, 413)
            inference.assert_not_called()
        with patch("ai_vision.recognition.image_upload.MAX_IMAGE_PIXELS", 1), patch.object(self.module, "recognize_image") as inference:
            response = self.client.post("/recognize", files={"file": ("large.png", self.png, "image/png")})
            self.assertEqual(response.status_code, 413)
            inference.assert_not_called()

    def test_empty_corrupt_or_non_image_returns_400_without_inference(self):
        for body, mime in ((b"", "image/png"), (b"broken", "image/png"), (self.png, "text/plain")):
            with patch.object(self.module, "recognize_image") as inference:
                response = self.client.post("/recognize", files={"file": ("sample.png", body, mime)})
                self.assertEqual(response.status_code, 400)
                inference.assert_not_called()

    def test_busy_returns_503_with_retry_header_and_next_request_can_succeed(self):
        admission = RecognitionAdmission(1)
        lease = admission.try_acquire()
        with patch.object(self.module, "_recognition_admission", admission), patch.object(self.module, "recognize_image", return_value={"success": True}) as inference:
            try:
                response = self.client.post("/recognize", files={"file": ("sample.png", self.png, "image/png")})
                self.assertEqual((response.status_code, response.headers["Retry-After"]), (503, "1"))
                inference.assert_not_called()
            finally:
                lease.cancel_pending()
            response = self.client.post("/recognize", files={"file": ("sample.png", self.png, "image/png")})
            self.assertEqual(response.status_code, 200)

    def test_missing_model_or_dependency_returns_503_and_releases_slot(self):
        for error in (FileNotFoundError("private-path"), PermissionError("private-path"), ImportError("private-path")):
            with patch.object(self.module, "recognize_image", side_effect=error):
                response = self.client.post("/recognize", files={"file": ("sample.png", self.png, "image/png")})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("private-path", response.text)
        with patch.object(self.module, "recognize_image", return_value={"success": True}):
            response = self.client.post("/recognize", files={"file": ("sample.png", self.png, "image/png")})
        self.assertEqual(response.status_code, 200)

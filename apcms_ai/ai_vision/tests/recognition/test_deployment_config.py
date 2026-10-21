# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_deployment_config.py

import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from ai_vision.deployment_config import cors_origins
from ai_vision.tests.recognition.asyncio_runtime_check import ensure_asyncio_runtime


class DeploymentConfigTests(unittest.TestCase):
    def test_default_empty_and_explicit_origins_are_deduplicated(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cors_origins(), [])
        with patch.dict(os.environ, {"VISION_CORS_ORIGINS": '["https://example.com","https://example.com"]'}):
            self.assertEqual(cors_origins(), ["https://example.com"])

    def test_invalid_or_overbroad_origins_are_rejected(self):
        for value in ('*', '"https://example.com"', '["*"]', '[null]', '["https://example.com/path"]',
                      '["https://user:pass@example.com"]', '["https://example.com:bad"]',
                      '["https://example.com/#fragment"]', '["https://exa mple.com"]'):
            with patch.dict(os.environ, {"VISION_CORS_ORIGINS": value}), self.subTest(value=value):
                with self.assertRaises(ValueError):
                    cors_origins()

    def test_browser_origin_normalization_handles_case_default_port_and_ipv6(self):
        with patch.dict(os.environ, {"VISION_CORS_ORIGINS": '["HTTPS://EXAMPLE.COM:443","http://[::1]:3000"]'}):
            self.assertEqual(cors_origins(), ["https://example.com", "http://[::1]:3000"])


class DeploymentAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_asyncio_runtime()

    def test_browser_preflight_allows_only_configured_origin(self):
        from ai_vision.app import create_app
        with patch.dict(os.environ, {"VISION_CORS_ORIGINS": '["https://frontend.example"]'}):
            app = create_app()
        with TestClient(app) as client:
            headers = {"Origin": "https://frontend.example", "Access-Control-Request-Method": "POST",
                       "Access-Control-Request-Headers": "content-type"}
            response = client.options("/recognize", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["access-control-allow-origin"], headers["Origin"])
            headers["Origin"] = "https://other.example"
            self.assertEqual(client.options("/recognize", headers=headers).status_code, 400)

    def test_readiness_failure_does_not_change_liveness(self):
        from ai_vision.app import create_app
        with TestClient(create_app()) as client, patch("ai_vision.app.check_readiness", return_value={"status": "BLOCKED"}):
            self.assertEqual(client.get("/ready").status_code, 503)
            self.assertEqual(client.get("/health").status_code, 200)

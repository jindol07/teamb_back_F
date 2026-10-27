"""팀 AWS HTTP 시험 예외 정책을 실제 네트워크/웹캠 없이 검증."""
import os
import unittest
from unittest.mock import patch

from ai_vision.safety import fire_alert_sender as sender
from ai_vision.safety import camera_monitor_router as monitor_router

AWS_URL = "http://52.79.133.132:3000/admin-api/api/parking/ai/fire-alerts"


class InsecureTestHttpPolicyTests(unittest.TestCase):
    def _env(self, **additional):
        return patch.dict(os.environ, additional, clear=True)

    def test_default_rejects_external_http(self):
        with self._env():
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                sender.validate_endpoint(AWS_URL)

    def test_explicit_test_approval_allows_exact_aws_url(self):
        with self._env(SAFETY_TEST_AWS_HTTP="1", SAFETY_CAMERA_SEND_MODE="test"):
            self.assertEqual(sender.validate_endpoint(AWS_URL), AWS_URL)

    def test_test_approval_does_not_allow_other_external_http(self):
        with self._env(SAFETY_TEST_AWS_HTTP="1", SAFETY_CAMERA_SEND_MODE="test"):
            for url in (
                "http://example.com/admin-api/api/parking/ai/fire-alerts",
                "http://52.79.133.133:3000/admin-api/api/parking/ai/fire-alerts",
                "http://52.79.133.132:3001/admin-api/api/parking/ai/fire-alerts",
                "http://52.79.133.132:3000/not-approved",
                "http://52.79.133.132:3000/admin-api/api/parking/ai/fire-alerts?other=1",
            ):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    sender.validate_endpoint(url)

    def test_production_mode_rejects_http_even_with_allow_flag(self):
        with self._env(SAFETY_TEST_AWS_HTTP="1", SAFETY_CAMERA_SEND_MODE="production"):
            with self.assertRaises(ValueError):
                sender.validate_endpoint(AWS_URL)

    def test_production_record_must_use_https(self):
        with self._env(SAFETY_TEST_AWS_HTTP="1", SAFETY_CAMERA_SEND_MODE="test"):
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                sender.validate_delivery_policy(
                    [{"is_test": False}], AWS_URL, allow_production_records=True
                )

    def test_other_normal_urls_unaffected(self):
        with self._env():
            self.assertEqual(sender.validate_endpoint("http://127.0.0.1:8765/api/mock/fire-alerts"),
                             "http://127.0.0.1:8765/api/mock/fire-alerts")
            self.assertEqual(sender.validate_endpoint("https://example.com/api/parking/ai/fire-alerts"),
                             "https://example.com/api/parking/ai/fire-alerts")

    def test_router_requires_token_for_aws_even_with_approval(self):
        with self._env(SAFETY_TEST_AWS_HTTP="1", SAFETY_CAMERA_SEND_MODE="test",
                       SAFETY_CAMERA_SEND_ENABLED="1", SAFETY_CAMERA_ALERT_URL=AWS_URL):
            with self.assertRaisesRegex(ValueError, "FIRE_ALERT_TOKEN"):
                monitor_router._delivery_options()

    def test_router_selects_test_only_with_approved_url_and_token(self):
        with self._env(SAFETY_TEST_AWS_HTTP="1", SAFETY_CAMERA_SEND_MODE="test",
                       SAFETY_CAMERA_SEND_ENABLED="1", SAFETY_CAMERA_ALERT_URL=AWS_URL,
                       FIRE_ALERT_TOKEN="dummy-do-not-use"):
            args, mode, production = monitor_router._delivery_options()
            self.assertFalse(production)
            self.assertEqual(mode, "TEST_HTTP")
            self.assertIn("--allow-test-records", args)
            self.assertNotIn("--allow-production-records", args)
            self.assertNotIn("dummy-do-not-use", args)

    def test_off_flag_keeps_dry_run(self):
        with self._env(SAFETY_CAMERA_SEND_ENABLED="0"):
            args, mode, production = monitor_router._delivery_options()
            self.assertEqual((args, mode, production), ([], "DRY_RUN_NO_HTTP", False))


if __name__ == "__main__":
    unittest.main(verbosity=2)

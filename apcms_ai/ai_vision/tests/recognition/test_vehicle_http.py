# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_vehicle_http.py

import json
import unittest
from unittest.mock import Mock
import requests

from ai_vision.recognition.vehicle_http import VehicleHTTPClient
from ai_vision.tests.recognition.test_vehicle_response import sample_event


def mock_http(outcome="PROCESSED", status=200):
    event = sample_event()
    body = {"eventId": event["event_id"], "eventType": "VEHICLE_PASSAGE", "plateNumber": event["plate_number"],
            "spaceCode": None, "parkingUsageId": 1, "outcome": outcome}
    response = Mock(status_code=status)
    response.iter_content.return_value = [json.dumps(body).encode("utf-8")]
    session = Mock()
    session.post.return_value = response
    return session, response


class VehicleHTTPTests(unittest.TestCase):
    def test_disabled_client_never_creates_session(self):
        factory = Mock(side_effect=AssertionError("session forbidden"))
        result = VehicleHTTPClient(session_factory=factory).send(sample_event())
        self.assertEqual(result["state"], "DISABLED")
        self.assertFalse(result["request_attempted"])
        factory.assert_not_called()

    def test_one_post_has_correct_contract_key_timeouts_no_redirect_or_retry(self):
        session, response = mock_http()
        client = VehicleHTTPClient("http://example.invalid/alpharking/admin/", "TEST_KEY", True, session_factory=lambda: session)
        result = client.send(sample_event())
        self.assertEqual(result["state"], "APPLIED")
        session.post.assert_called_once()
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], "http://example.invalid/alpharking/admin/api/parking/ai/vehicle-events")
        self.assertEqual(kwargs["headers"], {"X-AI-API-Key": "TEST_KEY"})
        self.assertEqual(kwargs["timeout"], (3, 5))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertTrue(kwargs["stream"])
        self.assertFalse(session.trust_env)
        self.assertTrue(all(call.args[1].max_retries.total == 0 for call in session.mount.call_args_list))
        response.close.assert_called_once()
        session.close.assert_called_once()
        self.assertNotIn("TEST_KEY", str(result))

    def test_timeouts_and_connection_errors_are_not_retried(self):
        for error, reason in ((requests.Timeout("secret"), "TRANSPORT_TIMEOUT"),
                              (requests.ConnectionError("secret"), "TRANSPORT_CONNECTION_ERROR")):
            session, _ = mock_http()
            session.post.side_effect = error
            client = VehicleHTTPClient("http://example.invalid", "KEY", True, session_factory=lambda: session)
            result = client.send(sample_event())
            self.assertEqual(result["reason_code"], reason)
            self.assertFalse(result["automatic_retry_allowed"])
            session.post.assert_called_once()
            session.close.assert_called_once()
            self.assertNotIn("secret", str(result))

    def test_large_or_interrupted_response_is_unknown_and_closed(self):
        for chunks in ([b"x" * 65537], requests.Timeout("secret")):
            session, response = mock_http()
            if isinstance(chunks, Exception):
                response.iter_content.side_effect = chunks
            else:
                response.iter_content.return_value = chunks
            result = VehicleHTTPClient("http://example.invalid", "KEY", True, session_factory=lambda: session).send(sample_event())
            self.assertEqual(result["state"], "DELIVERY_UNKNOWN")
            self.assertTrue(result["request_attempted"])
            response.close.assert_called_once()
            session.close.assert_called_once()

    def test_error_status_does_not_parse_body_or_follow_redirect(self):
        for status, state in ((307, "REJECTED"), (401, "AUTH_REQUIRED"), (409, "REJECTED"), (500, "DELIVERY_UNKNOWN")):
            session, response = mock_http(status=status)
            result = VehicleHTTPClient("http://example.invalid", "KEY", True, session_factory=lambda: session).send(sample_event())
            self.assertEqual(result["state"], state)
            response.iter_content.assert_not_called()
            session.post.assert_called_once()

    def test_configuration_and_invalid_payload_fail_before_post(self):
        for options in ({"enabled": "true"}, {"enabled": True}, {"context_url": "ftp://bad"},
                        {"context_url": "http://user:secret@example.invalid"}, {"context_url": "http://a/?key=secret"},
                        {"context_url": "http://a:99999"}, {"timeout": (0, 5)},
                        {"context_url": "http://a", "api_key": "bad\nkey", "enabled": True}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                VehicleHTTPClient(**options)
        session, _ = mock_http()
        client = VehicleHTTPClient("http://example.invalid", "KEY", True, session_factory=lambda: session)
        with self.assertRaises(ValueError):
            client.send({})
        session.post.assert_not_called()

    def test_session_setup_failure_is_reported_without_attempt_or_secret(self):
        factory = Mock(side_effect=RuntimeError("secret/key"))
        result = VehicleHTTPClient("http://example.invalid", "KEY", True, session_factory=factory).send(sample_event())
        self.assertEqual(result["reason_code"], "LOCAL_HTTP_PROCESSING_FAILED")
        self.assertFalse(result["request_attempted"])
        self.assertNotIn("secret", str(result))

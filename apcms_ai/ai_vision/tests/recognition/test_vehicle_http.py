# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_vehicle_http.py

import json
import unittest
from unittest.mock import Mock
import requests

from ai_vision.recognition.vehicle_http import VehicleHTTPClient
from ai_vision.tests.recognition.test_vehicle_response import sample_event
from ai_vision.tests.recognition.test_vehicle_response import sample_space_event
from ai_vision.recognition.vehicle_http import SpaceMatchHTTPClient


def mock_http(outcome="PROCESSED", status=200):
    event = sample_event()
    body = {"eventId": event["event_id"], "eventType": "VEHICLE_PASSAGE", "plateNumber": event["plate_number"],
            "spaceCode": None, "parkingUsageId": 1, "outcome": outcome}
    response = Mock(status_code=status)
    response.iter_content.return_value = [json.dumps(body).encode("utf-8")]
    session = Mock()
    session.post.return_value = response
    return session, response


class SpaceLifecycleLoopbackTests(unittest.TestCase):
    """합성 Boot 응답의 실제 HTTP 왕복 검사입니다. Oracle 검증이 아닙니다."""
    def exercise(self, bad_release=False, missing_match_version=False):
        import threading
        import uuid
        from concurrent.futures import wait
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from ai_vision.recognition.vehicle_http import SpaceReleaseHTTPClient
        from ai_vision.recognition.vehicle_delivery_flow import SpaceMatchDeliveryFlow
        requests_seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                event = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests_seen.append((self.path, self.headers.get('X-AI-API-Key'), event))
                release = event['event_type'] == 'VEHICLE_SPACE_RELEASE'
                version = (event['link_version'] + (0 if bad_release else 1)) if release else len(requests_seen)
                if missing_match_version and not release:
                    version = None
                body = json.dumps({'eventId': event['event_id'], 'eventType': event['event_type'],
                    'plateNumber': event['plate_number'], 'spaceCode': event['space_code'],
                    'parkingUsageId': 70, 'linkVersion': version, 'outcome': 'PROCESSED'}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/alpharking/admin'
        flow = SpaceMatchDeliveryFlow(SpaceMatchHTTPClient(url, 'TEST_KEY', True),
                                     SpaceReleaseHTTPClient(url, 'TEST_KEY', True))
        def complete():
            done, pending = wait([flow._future], timeout=3)
            self.assertFalse(pending)
            flow.poll(lambda: None)
        def candidate(space):
            return {'origin': 'LIVE', 'status': 'CANDIDATE_ONLY', 'reasons': [], 'track_id': 1,
                    'payload': sample_space_event() | {'event_id': str(uuid.uuid4()), 'space_code': space}}
        try:
            self.assertEqual(flow.submit(candidate('1F-A01'), 'first', lambda: None), 'IN_FLIGHT')
            complete()
            self.assertEqual(flow.records[-1]['status'], 'APPLIED')
            if missing_match_version:
                self.assertEqual(flow.records[-1]['blocking_reason'], 'SPACE_RELEASE_VERSION_UNAVAILABLE')
                self.assertEqual(flow.submit(candidate('1F-A02'), 'moved', lambda: None), 'BLOCKED')
                self.assertFalse(flow.release_empty({'1F-A01'}, 'SIMULATION_ONLY',
                                                   '2020-01-01T00:00:01Z', lambda: None))
                self.assertEqual(len(requests_seen), 1)
                return
            self.assertEqual(flow.submit(candidate('1F-A02'), 'moved', lambda: None), 'BUSY')
            self.assertTrue(flow.release_empty({'1F-A01'}, 'SIMULATION_ONLY',
                                              '2020-01-01T00:00:01Z', lambda: None))
            complete()
            if bad_release:
                self.assertEqual(flow.records[-1]['status'], 'DELIVERY_UNKNOWN')
                self.assertEqual(flow.submit(candidate('1F-A02'), 'retry', lambda: None), 'BLOCKED')
                self.assertEqual(len(requests_seen), 2)
            else:
                self.assertEqual(flow.records[-1]['status'], 'APPLIED')
                self.assertEqual(flow.submit(candidate('1F-A02'), 'second', lambda: None), 'IN_FLIGHT')
                complete()
                self.assertEqual(flow.records[-1]['status'], 'APPLIED')
                self.assertEqual([r[2]['space_code'] for r in requests_seen], ['1F-A01','1F-A01','1F-A02'])
            self.assertTrue(all(key == 'TEST_KEY' for _, key, _ in requests_seen))
            self.assertTrue(requests_seen[0][0].endswith('/space-match-events'))
            self.assertTrue(requests_seen[1][0].endswith('/space-release-events'))
            self.assertEqual(requests_seen[1][2]['parking_usage_id'], 70)
            self.assertEqual(requests_seen[1][2]['link_version'], 1)
        finally:
            flow.close(lambda: None)
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_match_release_then_other_space_over_real_local_http(self):
        self.exercise()

    def test_wrong_release_version_blocks_reconnection_without_retry(self):
        self.exercise(bad_release=True)

    def test_release_disabled_boot_response_stops_further_http(self):
        self.exercise(missing_match_version=True)


class VehicleHTTPTests(unittest.TestCase):
    def test_space_match_posts_once_to_separate_endpoint(self):
        event = sample_space_event()
        session, response = mock_http()
        response.iter_content.return_value = [json.dumps({
            'eventId': event['event_id'], 'eventType': event['event_type'], 'plateNumber': event['plate_number'],
            'spaceCode': '1F-A01', 'parkingUsageId': 70, 'outcome': 'PROCESSED'}).encode('utf-8')]
        result = SpaceMatchHTTPClient('http://example.invalid/alpharking/admin', 'TEST_KEY', True,
                                     session_factory=lambda: session).send(event)
        self.assertEqual(result['state'], 'APPLIED')
        self.assertEqual(result['event_type'], 'VEHICLE_SPACE_MATCH')
        session.post.assert_called_once()
        args, kwargs = session.post.call_args
        self.assertTrue(args[0].endswith('/api/parking/ai/space-match-events'))
        self.assertEqual(kwargs['json']['space_code'], '1F-A01')
        self.assertNotIn('direction', kwargs['json'])
        self.assertFalse(kwargs['allow_redirects'])
        response.close.assert_called_once()
        session.close.assert_called_once()

    def test_space_match_is_disabled_by_default_and_rejects_passage(self):
        factory = Mock()
        client = SpaceMatchHTTPClient(session_factory=factory)
        self.assertEqual(client.send(sample_space_event())['state'], 'DISABLED')
        factory.assert_not_called()
        with self.assertRaises(ValueError):
            client.send(sample_event())
        with self.assertRaises(ValueError):
            VehicleHTTPClient(session_factory=factory).send(sample_space_event())
        factory.assert_not_called()

    def test_space_match_timeout_is_not_retried(self):
        session, _ = mock_http()
        session.post.side_effect = requests.Timeout('private key')
        result = SpaceMatchHTTPClient('http://example.invalid', 'KEY', True,
                                     session_factory=lambda: session).send(sample_space_event())
        self.assertEqual(result['state'], 'DELIVERY_UNKNOWN')
        session.post.assert_called_once()
        self.assertNotIn('private', str(result))

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


class SpaceReleaseHTTPTests(unittest.TestCase):
    def test_release_posts_once_to_separate_endpoint_and_validates_response(self):
        from ai_vision.recognition.vehicle_http import SpaceReleaseHTTPClient
        from ai_vision.tests.recognition.test_vehicle_contract import SpaceReleaseContractTests
        event = SpaceReleaseContractTests().event()
        session, response = mock_http()
        response.iter_content.return_value = [json.dumps({'eventId': event['event_id'],
            'eventType': event['event_type'], 'plateNumber': '91소6408', 'spaceCode': '1F-A01',
            'parkingUsageId': 70, 'linkVersion': 5, 'outcome': 'PROCESSED'}).encode()]
        client = SpaceReleaseHTTPClient('http://example.invalid', 'KEY', True, session_factory=lambda: session)
        result = client.send(event)
        self.assertEqual(result['state'], 'APPLIED')
        self.assertEqual(result['link_version'], 5)
        session.post.assert_called_once()
        self.assertTrue(session.post.call_args.args[0].endswith('/api/parking/ai/space-release-events'))
        self.assertFalse(SpaceReleaseHTTPClient().send(event)['request_attempted'])

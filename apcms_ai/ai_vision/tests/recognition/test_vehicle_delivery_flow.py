# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_vehicle_delivery_flow.py

import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import requests
from ai_vision.recognition.vehicle_delivery_flow import VehicleDeliveryFlow
from ai_vision.recognition.vehicle_event_guard import VehicleEventGuard
from ai_vision.recognition.vehicle_http import VehicleHTTPClient
from ai_vision.recognition.vehicle_response import assess_response
from ai_vision.tests.recognition.test_vehicle_http import mock_http
from ai_vision.tests.recognition.test_vehicle_response import sample_event


def live_candidate():
    return {"origin": "LIVE", "track_id": 7, "status": "CANDIDATE_ONLY", "reasons": [], "payload": sample_event()}


class VehicleDeliveryFlowTests(unittest.TestCase):
    def test_default_is_disabled_and_does_not_reserve_candidate(self):
        guard = VehicleEventGuard()
        result = VehicleDeliveryFlow(guard=guard).process("run", live_candidate())
        self.assertEqual(result["decision"], "DISABLED")
        session, _ = mock_http()
        client = VehicleHTTPClient("http://example.invalid", "KEY", True, session_factory=lambda: session)
        flow = VehicleDeliveryFlow(client, guard)
        self.assertEqual(flow.process("run", live_candidate())["receipt_state"], "APPLIED")
        flow.process("run", live_candidate())
        session.post.assert_called_once()

    def test_pending_and_timeout_remain_held_without_second_post(self):
        for outcome, state in (("PENDING", "HELD"), ("PROCESSED", "DELIVERY_UNKNOWN")):
            session, _ = mock_http(outcome)
            if state == "DELIVERY_UNKNOWN":
                session.post.side_effect = requests.Timeout("secret")
            flow = VehicleDeliveryFlow(VehicleHTTPClient("http://example.invalid", "KEY", True, session_factory=lambda: session))
            for _ in range(3):
                self.assertEqual(flow.process("run", live_candidate())["receipt_state"], state)
            session.post.assert_called_once()

    def test_offline_source_and_blocked_candidate_never_send(self):
        session, _ = mock_http()
        flow = VehicleDeliveryFlow(VehicleHTTPClient("http://example.invalid", "KEY", True, session_factory=lambda: session))
        with self.assertRaises(ValueError):
            flow.process("run", {**live_candidate(), "origin": "LOCAL"})
        result = flow.process("run", {"origin": "LIVE", "track_id": 7, "status": "BLOCKED", "payload": None})
        self.assertEqual(result["decision"], "BLOCKED")
        session.post.assert_not_called()

    def test_concurrent_inputs_make_one_post(self):
        session, _ = mock_http()
        flow = VehicleDeliveryFlow(VehicleHTTPClient("http://example.invalid", "KEY", True, session_factory=lambda: session))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: flow.process("run", live_candidate()), range(32)))
        session.post.assert_called_once()
        self.assertEqual(sum(row["request_attempted"] is True for row in results), 1)

    def test_unexpected_client_failure_is_held_without_auto_retry(self):
        client = Mock(enabled=True)
        client.send.side_effect = RuntimeError("secret")
        flow = VehicleDeliveryFlow(client)
        first = flow.process("run", live_candidate())
        self.assertEqual(first["receipt_state"], "DELIVERY_UNKNOWN")
        self.assertIsNone(first["request_attempted"])
        self.assertNotIn("secret", str(first))
        self.assertEqual(flow.process("run", live_candidate())["receipt_state"], "DELIVERY_UNKNOWN")
        client.send.assert_called_once()

    def test_incomplete_transport_receipt_cannot_be_recorded_as_success(self):
        client = Mock(enabled=True)
        client.send.return_value = assess_response(sample_event(), transport_error="TIMEOUT")
        flow = VehicleDeliveryFlow(client)
        first = flow.process("run", live_candidate())
        self.assertEqual(first["receipt"]["reason_code"], "LOCAL_DELIVERY_PROCESSING_FAILED")
        self.assertIsNone(first["request_attempted"])
        flow.process("run", live_candidate())
        client.send.assert_called_once()

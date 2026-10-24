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


class SpaceMatchDeliveryTests(unittest.TestCase):
    def candidate(self):
        from ai_vision.recognition.vehicle_live_candidate import create_space_match_candidate
        row = {'track_id': 3, 'space_id': 'A-01', 'plate_number': '91소6408'}
        return create_space_match_candidate({**row, 'kind': 'LIVE_SPACE_MATCH',
            'plate_detection_confidence': .9}, [row], 'PARKING_1', '2020-01-01T00:00:00Z')

    def flow(self, client=None):
        from ai_vision.recognition.vehicle_delivery_flow import SpaceMatchDeliveryFlow
        flow = SpaceMatchDeliveryFlow(client)
        self.addCleanup(flow.close, lambda: None)
        return flow

    def test_disabled_records_once_without_network(self):
        flow = self.flow()
        self.assertEqual(flow.submit(self.candidate(), 'stop1', lambda: None), 'DISABLED')
        self.assertEqual(flow.submit(self.candidate(), 'stop1', lambda: None), 'DUPLICATE')
        self.assertEqual(len(flow.records), 1)

    def test_slow_http_has_no_queue_and_result_is_recorded(self):
        import threading
        release, started = threading.Event(), threading.Event()
        client = Mock(enabled=True)
        def send(event):
            started.set()
            release.wait(3)
            return {'event_id': event['event_id'], 'event_type': 'VEHICLE_SPACE_MATCH',
                    'state': 'APPLIED', 'request_attempted': True}
        client.send.side_effect = send
        flow = self.flow(client)
        self.addCleanup(release.set)
        persisted = []
        self.assertEqual(flow.submit(self.candidate(), 'stop1', lambda: persisted.append(flow.records[0]['status'])), 'IN_FLIGHT')
        self.assertTrue(started.wait(2))
        self.assertEqual(persisted, ['IN_FLIGHT'])
        self.assertEqual(flow.submit(self.candidate(), 'stop2', lambda: None), 'BUSY')
        release.set()
        flow.close(lambda: None)
        self.assertEqual(flow.records[0]['status'], 'APPLIED')
        client.send.assert_called_once()

    def test_unknown_never_retries_or_reassigns_same_plate(self):
        client = Mock(enabled=True)
        client.send.side_effect = RuntimeError('transport failed')
        flow = self.flow(client)
        flow.submit(self.candidate(), 'stop1', lambda: None)
        from concurrent.futures import wait
        wait([flow._future])
        flow.poll(lambda: None)
        self.assertEqual(flow.records[0]['status'], 'DELIVERY_UNKNOWN')
        self.assertEqual(flow.submit(self.candidate(), 'stop2', lambda: None), 'BLOCKED')
        client.send.assert_called_once()

    def test_failed_intent_save_prevents_http(self):
        client = Mock(enabled=True)
        flow = self.flow(client)
        with self.assertRaises(OSError):
            flow.submit(self.candidate(), 'stop1', Mock(side_effect=OSError('disk full')))
        client.send.assert_not_called()
        self.assertEqual(flow.submit(self.candidate(), 'stop1', lambda: None), 'DUPLICATE')

    def test_changed_response_identity_is_unknown(self):
        client = Mock(enabled=True)
        client.send.return_value = {'event_id': 'other', 'state': 'APPLIED', 'request_attempted': True}
        flow = self.flow(client)
        flow.submit(self.candidate(), 'stop1', lambda: None)
        flow.close(lambda: None)
        self.assertEqual(flow.records[0]['status'], 'DELIVERY_UNKNOWN')


    def test_auth_failure_and_rejection_stop_all_following_candidates(self):
        from concurrent.futures import wait
        for state in ('AUTH_REQUIRED', 'REJECTED'):
            with self.subTest(state=state):
                client = Mock(enabled=True)
                client.send.side_effect = lambda event: {'event_id': event['event_id'],
                    'event_type': 'VEHICLE_SPACE_MATCH', 'state': state,
                    'request_attempted': True, 'receipt_verified': False}
                flow = self.flow(client)
                flow.submit(self.candidate(), 'first', lambda: None)
                wait([flow._future])
                flow.poll(lambda: None)
                candidate = self.candidate()
                candidate['payload']['plate_number'] = '12가3456'
                self.assertEqual(flow.submit(candidate, 'second', lambda: None), 'BLOCKED')
                self.assertTrue(flow.blocked)
                client.send.assert_called_once()

    def test_real_client_validates_mock_boot_response_through_async_flow(self):
        import json
        from ai_vision.recognition.vehicle_http import SpaceMatchHTTPClient
        candidate = self.candidate()
        payload = candidate['payload']
        session, response = mock_http()
        response.iter_content.return_value = [json.dumps({
            'eventId': payload['event_id'], 'eventType': 'VEHICLE_SPACE_MATCH',
            'plateNumber': '91소6408', 'spaceCode': '1F-A01',
            'outcome': 'PROCESSED', 'parkingUsageId': 123, 'conflictReason': None}).encode()]
        flow = self.flow(SpaceMatchHTTPClient('http://example.invalid', 'KEY', True, session_factory=lambda: session))
        flow.submit(candidate, 'stop1', lambda: None)
        flow.close(lambda: None)
        self.assertEqual(flow.records[0]['status'], 'APPLIED')
        self.assertTrue(flow.records[0]['receipt']['receipt_verified'])
        session.post.assert_called_once()
        self.assertTrue(session.post.call_args.args[0].endswith('/api/parking/ai/space-match-events'))


class SpaceReleaseFlowTests(unittest.TestCase):
    candidate = SpaceMatchDeliveryTests.candidate
    def test_handoff_different_usage_response_is_not_silently_accepted(self):
        from ai_vision.recognition.vehicle_delivery_flow import SpaceMatchDeliveryFlow
        client = Mock(enabled=True)
        client.send.side_effect = lambda event: {'event_id': event['event_id'], 'event_type': event['event_type'],
            'state': 'APPLIED', 'request_attempted': True, 'receipt_verified': True, 'parking_usage_id': 71}
        flow = SpaceMatchDeliveryFlow(client)
        self.addCleanup(flow.close, lambda: None)
        flow.submit(self.candidate() | {'expected_parking_usage_id': 70}, 'handoff', lambda: None)
        self.complete(flow)
        self.assertTrue(flow.blocked)
        self.assertEqual(flow.records[0]['blocking_reason'], 'ENTRY_USAGE_CHANGED')

    def test_verified_same_usage_exit_allows_next_entry_but_other_usage_does_not(self):
        flow, client, release = self.setup_link()
        self.assertFalse(flow.acknowledge_gate_exit('91소6408', 71))
        self.assertTrue(flow.acknowledge_gate_exit('91소6408', 70))
        self.assertEqual(flow.submit(self.candidate(), 'new_entry', lambda: None), 'IN_FLIGHT')
        self.complete(flow)
        self.assertEqual(client.send.call_count, 2)
        release.send.assert_not_called()

    def test_release_enabled_requires_verified_usable_match_version(self):
        from ai_vision.recognition.vehicle_delivery_flow import SpaceMatchDeliveryFlow
        for state in ('APPLIED', 'UNCHANGED'):
            for version in (None, True, -1, 10**18-1):
                with self.subTest(state=state, version=version):
                    client, release = Mock(enabled=True), Mock(enabled=True)
                    client.send.side_effect = lambda event: {'event_id': event['event_id'],
                        'event_type': event['event_type'], 'state': state, 'request_attempted': True,
                        'receipt_verified': True, 'parking_usage_id': 70, 'link_version': version}
                    flow = SpaceMatchDeliveryFlow(client, release)
                    try:
                        flow.submit(self.candidate(), 'first', lambda: None)
                        self.complete(flow)
                        self.assertEqual(flow.records[0]['status'], state)
                        self.assertEqual(flow.records[0]['blocking_reason'], 'SPACE_RELEASE_VERSION_UNAVAILABLE')
                        self.assertEqual(flow.submit(self.candidate(), 'next', lambda: None), 'BLOCKED')
                        self.assertFalse(flow.release_empty({'1F-A01'}, 'PARKING_1',
                                                          '2020-01-01T00:00:01Z', lambda: None))
                        release.send.assert_not_called()
                        client.send.assert_called_once()
                    finally:
                        flow.close(lambda: None)

    def test_legacy_match_without_release_still_accepts_missing_version(self):
        from ai_vision.recognition.vehicle_delivery_flow import SpaceMatchDeliveryFlow
        client = Mock(enabled=True)
        client.send.side_effect = lambda event: {'event_id': event['event_id'],
            'event_type': event['event_type'], 'state': 'APPLIED', 'request_attempted': True,
            'receipt_verified': True, 'parking_usage_id': 70, 'link_version': None}
        flow = SpaceMatchDeliveryFlow(client)
        self.addCleanup(flow.close, lambda: None)
        flow.submit(self.candidate(), 'first', lambda: None)
        self.complete(flow)
        self.assertFalse(flow.blocked)
        self.assertEqual(flow.records[0]['status'], 'APPLIED')

    def setup_link(self, release_failure=False):
        from ai_vision.recognition.vehicle_delivery_flow import SpaceMatchDeliveryFlow
        client, release = Mock(enabled=True), Mock(enabled=True)
        client.send.side_effect = lambda event: {'event_id': event['event_id'], 'event_type': event['event_type'],
            'state': 'APPLIED', 'receipt_verified': True, 'request_attempted': True, 'parking_usage_id': 70, 'link_version': 4}
        if release_failure:
            release.send.side_effect = RuntimeError('timeout')
        else:
            release.send.side_effect = lambda event: {'event_id': event['event_id'], 'event_type': event['event_type'],
                'state': 'APPLIED', 'receipt_verified': True, 'request_attempted': True, 'parking_usage_id': 70, 'link_version': 5}
        flow = SpaceMatchDeliveryFlow(client, release)
        self.addCleanup(flow.close, lambda: None)
        flow.submit(self.candidate(), 'first', lambda: None)
        self.complete(flow)
        return flow, client, release

    def complete(self, flow):
        from concurrent.futures import wait
        wait([flow._future])
        flow.poll(lambda: None)

    def test_release_then_new_assignment_only_after_verified_success(self):
        flow, client, release = self.setup_link()
        self.assertEqual(flow.submit(self.candidate(), 'next', lambda: None), 'BUSY')
        self.assertFalse(flow.release_empty(set(), 'PARKING_1', '2020-01-01T00:00:01Z', lambda: None))
        self.assertTrue(flow.release_empty({'1F-A01'}, 'PARKING_1', '2020-01-01T00:00:01Z', lambda: None))
        self.assertEqual(flow.submit(self.candidate(), 'next', lambda: None), 'BUSY')
        self.complete(flow)
        self.assertEqual(flow.records[-1]['payload']['event_type'], 'VEHICLE_SPACE_RELEASE')
        self.assertEqual(flow.submit(self.candidate(), 'next', lambda: None), 'IN_FLIGHT')
        self.complete(flow)
        self.assertEqual(client.send.call_count, 2)
        release.send.assert_called_once()

    def test_unknown_release_blocks_reassignment_and_never_retries(self):
        flow, client, release = self.setup_link(True)
        flow.release_empty({'1F-A01'}, 'PARKING_1', '2020-01-01T00:00:01Z', lambda: None)
        self.complete(flow)
        self.assertEqual(flow.records[-1]['status'], 'DELIVERY_UNKNOWN')
        self.assertFalse(flow.release_empty({'1F-A01'}, 'PARKING_1', '2020-01-01T00:00:02Z', lambda: None))
        self.assertEqual(flow.submit(self.candidate(), 'next', lambda: None), 'BLOCKED')
        client.send.assert_called_once()
        release.send.assert_called_once()

    def test_unknown_release_stops_requests_for_other_plates_too(self):
        flow, client, release = self.setup_link(True)
        flow.release_empty({'1F-A01'}, 'PARKING_1', '2020-01-01T00:00:01Z', lambda: None)
        self.complete(flow)
        candidate = self.candidate()
        candidate['payload']['plate_number'] = '12가3456'
        self.assertEqual(flow.submit(candidate, 'different_plate', lambda: None), 'BLOCKED')
        client.send.assert_called_once()

    def test_release_intent_save_failure_never_calls_http(self):
        flow, client, release = self.setup_link()
        with self.assertRaises(OSError):
            flow.release_empty({'1F-A01'}, 'PARKING_1', '2020-01-01T00:00:01Z', Mock(side_effect=OSError()))
        release.send.assert_not_called()
        self.assertFalse(flow.release_empty({'1F-A01'}, 'PARKING_1', '2020-01-01T00:00:01Z', lambda: None))

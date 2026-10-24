# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_vehicle_response.py

import json
import unittest
from ai_vision.recognition.vehicle_response import assess_response
from ai_vision.recognition.vehicle_response import assess_space_match_response


def sample_event():
    # 합성 이벤트는 통신 결과 분류용이며 실제 영상 인식 결과와 구분합니다.
    return {"event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479", "event_type": "VEHICLE_PASSAGE",
            "detected_at": "2020-01-01T00:00:00Z", "camera_id": "SIMULATION_ONLY", "direction": "ENTRY",
            "plate_number": "91소6408", "confidence": .8}


def sample_space_event():
    return {k: v for k, v in sample_event().items() if k != 'direction'} | {
        'event_type': 'VEHICLE_SPACE_MATCH', 'space_code': '1F-A01', 'method': 'TRACKING'}


class VehicleResponseTests(unittest.TestCase):
    def test_space_response_matches_space_and_preserves_pending(self):
        event = sample_space_event()
        body = {'eventId': event['event_id'], 'eventType': event['event_type'], 'plateNumber': event['plate_number'],
                'spaceCode': event['space_code'], 'parkingUsageId': 70}
        for outcome, state in [('PROCESSED', 'APPLIED'), ('UNCHANGED', 'UNCHANGED'), ('PENDING', 'HELD')]:
            result = assess_space_match_response(event, 200, json.dumps(body | {'outcome': outcome}))
            self.assertEqual(result['state'], state)
            self.assertTrue(result['receipt_verified'])
            self.assertFalse(result['automatic_retry_allowed'])
        result = assess_space_match_response(event, 200, json.dumps(body | {'outcome': 'PENDING', 'parkingUsageId': None}))
        self.assertEqual(result['state'], 'HELD')

    def test_space_response_rejects_other_space_passage_and_missing_usage(self):
        event = sample_space_event()
        body = {'eventId': event['event_id'], 'eventType': event['event_type'], 'plateNumber': event['plate_number'],
                'spaceCode': event['space_code'], 'parkingUsageId': 70, 'outcome': 'PROCESSED'}
        for change in ({'spaceCode': '1F-A02'}, {'spaceCode': None}, {'eventType': 'VEHICLE_PASSAGE'},
                       {'parkingUsageId': None}, {'parkingUsageId': True}):
            result = assess_space_match_response(event, 200, json.dumps(body | change))
            self.assertEqual(result['state'], 'DELIVERY_UNKNOWN')
            self.assertFalse(result['receipt_verified'])

    def test_space_response_timeout_does_not_claim_rejection_or_retry(self):
        result = assess_space_match_response(sample_space_event(), transport_error='TIMEOUT')
        self.assertEqual(result['state'], 'DELIVERY_UNKNOWN')
        self.assertFalse(result['automatic_retry_allowed'])

    def setUp(self):
        self.event = sample_event()
        self.body = {"eventId": self.event["event_id"], "eventType": "VEHICLE_PASSAGE", "plateNumber": "91소6408",
                     "spaceCode": None, "parkingUsageId": 1, "outcome": "PROCESSED", "detail": "private/internal/path"}

    def test_known_outcomes_preserve_identity_and_never_auto_retry(self):
        for outcome, expected in (("PROCESSED", "APPLIED"), ("UNCHANGED", "UNCHANGED"), ("PENDING", "HELD")):
            result = assess_response(self.event, 200, json.dumps({**self.body, "outcome": outcome}))
            self.assertEqual(result["state"], expected)
            self.assertEqual(result["event_id"], self.event["event_id"])
            self.assertTrue(result["receipt_verified"])
            self.assertFalse(result["automatic_retry_allowed"])
            self.assertNotIn("private", str(result))

    def test_http_success_does_not_hide_wrong_event_type_plate_or_space(self):
        for changes in ({"eventId": "00000000-0000-0000-0000-000000000000"}, {"eventType": "PARKING_OCCUPANCY"},
                        {"plateNumber": "12가3456"}, {"spaceCode": "1F-A01"}):
            result = assess_response(self.event, 200, json.dumps({**self.body, **changes}))
            self.assertEqual(result["reason_code"], "RESPONSE_IDENTITY_MISMATCH")
            self.assertFalse(result["receipt_verified"])

    def test_unknown_outcome_is_not_success(self):
        result = assess_response(self.event, 200, json.dumps({**self.body, "outcome": "DUPLICATE"}))
        self.assertEqual(result["state"], "DELIVERY_UNKNOWN")
        self.assertFalse(result["automatic_retry_allowed"])

    def test_bad_json_duplicates_size_encoding_and_missing_fields_are_unknown(self):
        for body in ("{", "[]", '{"eventId":"a","eventId":"b"}', "x" * 65537, b"\xff", "{}",
                     json.dumps({**self.body, "parkingUsageId": True})):
            with self.subTest(body=str(body)[:40]):
                result = assess_response(self.event, 200, body)
                self.assertEqual(result["reason_code"], "INVALID_RESPONSE")

    def test_http_errors_and_redirects_are_distinct(self):
        for code, expected in ((307, "REJECTED"), (400, "REJECTED"), (401, "AUTH_REQUIRED"),
                               (403, "AUTH_REQUIRED"), (409, "REJECTED"), (408, "DELIVERY_UNKNOWN"),
                               (429, "DELIVERY_UNKNOWN"), (500, "DELIVERY_UNKNOWN"), (204, "DELIVERY_UNKNOWN")):
            result = assess_response(self.event, code, "private error")
            self.assertEqual(result["state"], expected)
            self.assertFalse(result["automatic_retry_allowed"])
            self.assertNotIn("private", str(result))

    def test_transport_errors_are_ambiguous_and_input_is_preserved(self):
        before = dict(self.event)
        for error in ("TIMEOUT", "CONNECTION_ERROR"):
            result = assess_response(self.event, transport_error=error)
            self.assertEqual(result["state"], "DELIVERY_UNKNOWN")
            self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(self.event, before)

    def test_invalid_response_arguments_are_rejected(self):
        for kwargs in ({}, {"status_code": True}, {"status_code": 999}, {"transport_error": "OTHER"},
                       {"status_code": 200, "transport_error": "TIMEOUT"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                assess_response(self.event, **kwargs)


class SpaceReleaseResponseTests(unittest.TestCase):
    def test_release_success_requires_original_usage_and_next_generation(self):
        from ai_vision.tests.recognition.test_vehicle_contract import SpaceReleaseContractTests
        from ai_vision.recognition.vehicle_response import assess_space_release_response
        event = SpaceReleaseContractTests().event()
        body = {'eventId': event['event_id'], 'eventType': event['event_type'], 'plateNumber': '91소6408',
                'spaceCode': '1F-A01', 'parkingUsageId': 70, 'linkVersion': 5, 'outcome': 'PROCESSED'}
        result = assess_space_release_response(event, 200, json.dumps(body))
        self.assertEqual(result['state'], 'APPLIED')
        self.assertEqual(result['link_version'], 5)
        for change in ({'linkVersion': 4}, {'linkVersion': None}, {'linkVersion': True},
                       {'parkingUsageId': 71}, {'spaceCode': '1F-A02'}, {'outcome': 'UNCHANGED'}):
            with self.subTest(change=change):
                result = assess_space_release_response(event, 200, json.dumps(body | change))
                self.assertEqual(result['state'], 'DELIVERY_UNKNOWN')
                self.assertFalse(result['receipt_verified'])
        result = assess_space_release_response(event, 200, json.dumps(body | {'outcome': 'PENDING', 'linkVersion': None}))
        self.assertEqual(result['state'], 'HELD')
        self.assertFalse(result['automatic_retry_allowed'])

    def test_match_keeps_nullable_version_for_existing_server(self):
        from ai_vision.recognition.vehicle_response import assess_space_match_response
        event = sample_space_event()
        body = {'eventId': event['event_id'], 'eventType': event['event_type'], 'plateNumber': '91소6408',
                'spaceCode': event['space_code'], 'parkingUsageId': 70, 'outcome': 'PROCESSED'}
        self.assertIsNone(assess_space_match_response(event, 200, json.dumps(body))['link_version'])
        self.assertEqual(assess_space_match_response(event, 200, json.dumps(body | {'linkVersion': 4}))['link_version'], 4)
        self.assertEqual(assess_space_match_response(event, 200, json.dumps(body | {'linkVersion': True}))['state'], 'DELIVERY_UNKNOWN')

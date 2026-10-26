# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_vehicle_contract.py

import unittest
from datetime import datetime, timedelta, timezone
from ai_vision.recognition.vehicle_contract import validate_vehicle_payload, parse_detected_at, validate_camera_id
from ai_vision.recognition.vehicle_contract import validate_space_match_payload


class VehicleContractTests(unittest.TestCase):
    def space_payload(self):
        return {k: v for k, v in self.payload.items() if k != 'direction'} | {
            'event_type': 'VEHICLE_SPACE_MATCH', 'space_code': '1F-A01', 'method': 'TRACKING'}

    def test_space_match_normalizes_common_fields_without_turning_into_passage(self):
        payload = self.space_payload() | {'plate_number': '91 소 6408', 'direction': None}
        result = validate_space_match_payload(payload, self.now)
        self.assertEqual(result['event_type'], 'VEHICLE_SPACE_MATCH')
        self.assertEqual(result['space_code'], '1F-A01')
        self.assertEqual(result['plate_number'], '91소6408')
        self.assertNotIn('direction', result)
        self.assertEqual(payload['plate_number'], '91 소 6408')

    def test_space_match_rejects_wrong_contract_and_unconfirmed_values(self):
        for change in ({'event_type': 'VEHICLE_PASSAGE'}, {'direction': 'EXIT'}, {'method': 'RELEASE'},
                       {'space_code': 'A-01'}, {'space_code': '0F-A01'}, {'plate_number': '91±6408'},
                       {'confidence': True}, {'reservation_id': 90}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_space_match_payload(self.space_payload() | change, self.now)
        with self.assertRaises(ValueError):
            validate_vehicle_payload(self.space_payload(), self.now)

    def test_space_match_requires_all_fields_and_real_time(self):
        payload = self.space_payload()
        for key in payload:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_space_match_payload({k: v for k, v in payload.items() if k != key}, self.now)
        with self.assertRaises(ValueError):
            validate_space_match_payload(payload | {'detected_at': 2.5}, self.now)

    def setUp(self):
        self.now = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.payload = {"event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479", "event_type": "VEHICLE_PASSAGE",
                        "detected_at": "2020-01-01T09:00:00+09:00", "camera_id": "TEST_GATE",
                        "direction": "ENTRY", "plate_number": "91소6408", "confidence": .8}

    def test_payload_normalization_preserves_input(self):
        original = {**self.payload, "plate_number": "91 소 6408", "space_code": None}
        result = validate_vehicle_payload(original, self.now)
        self.assertEqual(result["plate_number"], "91소6408")
        self.assertEqual(original["plate_number"], "91 소 6408")
        self.assertNotIn("space_code", result)

    def test_backend_future_tolerance_has_explicit_boundary(self):
        at = self.now + timedelta(seconds=60)
        validate_vehicle_payload({**self.payload, "detected_at": at.isoformat()}, self.now)
        with self.assertRaises(ValueError):
            validate_vehicle_payload({**self.payload, "detected_at": (at + timedelta(microseconds=1)).isoformat()}, self.now)

    def test_invalid_payload_fields_are_rejected(self):
        for changes in ({"event_id": "bad"}, {"direction": "DOWN"}, {"direction": []},
                        {"event_type": "VEHICLE_SPACE_MATCH"}, {"space_code": "1F-A01"}, {"method": "TRACKING"},
                        {"plate_number": "ABC123"}, {"camera_id": " "}, {"unexpected": 1},
                        {"detected_at": "2020-01-01T00:00:00"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_vehicle_payload({**self.payload, **changes}, self.now)
        with self.assertRaises(ValueError):
            validate_vehicle_payload({}, self.now)

    def test_invalid_confidence_is_not_coerced_or_rounded_into_range(self):
        for value in (True, "0.8", float("nan"), float("inf"), -1, 1.00001, 10 ** 500):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_vehicle_payload({**self.payload, "confidence": value}, self.now)

    def test_timezone_and_java_camera_length(self):
        self.assertEqual(parse_detected_at("2020-01-01T00:00:00Z"), self.now)
        for value in ("2020-01-01", "2020-01-01T00:00:00+09:99", "2020-01-01T00:00:00+19:00"):
            with self.assertRaises(ValueError):
                parse_detected_at(value)
        validate_camera_id("😀" * 30)
        with self.assertRaises(ValueError):
            validate_camera_id("😀" * 31)
        with self.assertRaises(ValueError):
            validate_vehicle_payload(self.payload, datetime(2020, 1, 1))


class SpaceReleaseContractTests(unittest.TestCase):
    def event(self):
        return {'event_id': '02f56fb0-cb4f-4fb0-867a-6c31b7b88da3', 'event_type': 'VEHICLE_SPACE_RELEASE',
                'detected_at': '2020-01-01T00:00:00Z', 'camera_id': 'PARKING_1', 'plate_number': '91소6408',
                'space_code': '1F-A01', 'parking_usage_id': 70, 'link_version': 4, 'reason': 'CONFIRMED_EMPTY'}

    def test_release_requires_exact_identity_generation_and_empty_evidence(self):
        from ai_vision.recognition.vehicle_contract import validate_space_release_payload
        event = self.event()
        self.assertEqual(validate_space_release_payload(event)['link_version'], 4)
        self.assertEqual(event['detected_at'], '2020-01-01T00:00:00Z')
        for change in ({'link_version': True}, {'link_version': -1}, {'link_version': 10**18},
                       {'parking_usage_id': None}, {'parking_usage_id': 0}, {'reason': 'TRACK_LOST'},
                       {'direction': 'EXIT'}, {'confidence': .9}, {'event_type': 'VEHICLE_SPACE_MATCH'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_space_release_payload(event | change)

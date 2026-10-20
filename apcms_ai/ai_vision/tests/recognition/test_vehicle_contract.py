# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_vehicle_contract.py

import unittest
from datetime import datetime, timedelta, timezone
from ai_vision.recognition.vehicle_contract import validate_vehicle_payload, parse_detected_at, validate_camera_id


class VehicleContractTests(unittest.TestCase):
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

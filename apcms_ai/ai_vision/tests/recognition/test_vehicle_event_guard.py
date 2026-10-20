# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_vehicle_event_guard.py

import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from ai_vision.recognition.vehicle_contract import parse_detected_at
from ai_vision.recognition.vehicle_event_guard import VehicleEventGuard
from ai_vision.recognition.vehicle_response import assess_response
from ai_vision.tests.recognition.test_vehicle_response import sample_event


class VehicleEventGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = VehicleEventGuard()
        self.event = sample_event()

    def shifted(self, seconds, **changes):
        at = parse_detected_at(self.event["detected_at"]) + timedelta(seconds=seconds)
        return {**self.event, "detected_at": at.isoformat(), "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, str(seconds))), **changes}

    def test_same_track_new_uuid_and_confidence_do_not_create_second_event(self):
        first = self.guard.consider("run", 1, self.event)
        duplicate = self.guard.consider("run", 1, {**self.event, "event_id": "00000000-0000-0000-0000-000000000001", "confidence": .9})
        self.assertEqual(first["decision"], "NEW_CANDIDATE")
        self.assertEqual(duplicate["decision"], "SUPPRESSED_SAME_TRACK")
        self.assertEqual(duplicate["event_id"], first["event_id"])
        self.assertIsNone(duplicate["payload"])

    def test_equivalent_timezones_are_same_passage(self):
        self.guard.consider("run", 1, self.event)
        result = self.guard.consider("run", 1, {**self.event, "detected_at": "2020-01-01T09:00:00+09:00"})
        self.assertEqual(result["decision"], "SUPPRESSED_SAME_TRACK")

    def test_same_track_changed_plate_direction_or_time_is_held(self):
        self.guard.consider("run", 1, self.event)
        for event in ({**self.event, "plate_number": "12가3456"}, {**self.event, "direction": "EXIT"}, self.shifted(1)):
            self.assertEqual(self.guard.consider("run", 1, event)["decision"], "HELD_TRACK_CONFLICT")

    def test_track_switch_is_suppressed_and_window_boundary_can_create_candidate(self):
        self.guard.consider("run", 1, self.event)
        self.assertEqual(self.guard.consider("run", 2, self.shifted(4.999))["decision"], "SUPPRESSED_RECENT_PLATE")
        self.assertEqual(self.guard.consider("run", 3, self.shifted(5))["decision"], "NEW_CANDIDATE")
        # 보류된 기존 ID는 시간이 지나도 같은 실행에서 다시 생성하지 않습니다.
        self.assertEqual(self.guard.consider("run", 2, self.shifted(4.999))["decision"], "SUPPRESSED_SAME_TRACK")

    def test_out_of_order_is_held_without_replacing_latest_event(self):
        self.guard.consider("run", 1, self.shifted(10))
        self.assertEqual(self.guard.consider("run", 2, self.shifted(1))["decision"], "HELD_OUT_OF_ORDER")
        self.assertEqual(self.guard.consider("run", 3, self.shifted(11))["decision"], "SUPPRESSED_RECENT_PLATE")

    def test_opposite_direction_and_other_camera_are_independent(self):
        self.guard.consider("run", 1, self.event)
        self.assertEqual(self.guard.consider("run", 2, self.shifted(0, direction="EXIT"))["decision"], "NEW_CANDIDATE")
        other = {**self.event, "camera_id": "OTHER_CAMERA", "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "camera"))}
        self.assertEqual(self.guard.consider("run", 1, other)["decision"], "NEW_CANDIDATE")

    def test_timeout_is_recorded_and_never_reopens_candidate(self):
        self.guard.consider("run", 1, self.event)
        timeout = assess_response(self.event, transport_error="TIMEOUT")
        self.guard.record_result("run", 1, self.event["camera_id"], timeout)
        duplicate = self.guard.consider("run", 1, self.event)
        self.assertEqual(duplicate["receipt_state"], "DELIVERY_UNKNOWN")
        self.assertFalse(duplicate["automatic_retry_allowed"])
        self.assertIsNone(duplicate["payload"])
        self.guard.record_result("run", 1, self.event["camera_id"], timeout)
        with self.assertRaises(ValueError):
            self.guard.record_result("run", 1, self.event["camera_id"], {**timeout, "state": "REJECTED"})

    def test_mutating_returned_payload_does_not_change_original_candidate(self):
        first = self.guard.consider("run", 1, self.event)
        first["payload"]["plate_number"] = "12가3456"
        self.assertEqual(self.guard.consider("run", 1, self.event)["decision"], "SUPPRESSED_SAME_TRACK")

    def test_concurrent_inputs_create_exactly_one_candidate(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.guard.consider("run", 1, self.event), range(32)))
        self.assertEqual(sum(result["decision"] == "NEW_CANDIDATE" for result in results), 1)

    def test_capacity_holds_new_tracks_without_evicting_old_records(self):
        guard = VehicleEventGuard(max_entries=1)
        guard.consider("run", 1, self.event)
        self.assertEqual(guard.consider("run", 2, self.shifted(10))["decision"], "HELD_CAPACITY")
        self.assertEqual(guard.consider("run", 1, self.event)["decision"], "SUPPRESSED_SAME_TRACK")

    def test_invalid_policy_keys_and_unrelated_receipts_are_rejected(self):
        for kwargs in ({"cooldown_seconds": True}, {"cooldown_seconds": 0}, {"cooldown_seconds": float("nan")}, {"max_entries": 0}):
            with self.assertRaises(ValueError):
                VehicleEventGuard(**kwargs)
        for session, track in (("../run", 1), ("run", True), ("run", -1)):
            with self.assertRaises(ValueError):
                self.guard.consider(session, track, self.event)
        self.guard.consider("run", 1, self.event)
        result = assess_response(self.event, transport_error="TIMEOUT")
        for change in ({"event_id": "other"}, {"automatic_retry_allowed": True}, {"receipt_verified": True}, {"state": []}):
            with self.assertRaises(ValueError):
                self.guard.record_result("run", 1, self.event["camera_id"], {**result, **change})

    def test_reused_uuid_cannot_identify_another_new_passage(self):
        self.guard.consider("run", 1, self.event)
        later = self.shifted(10, event_id=self.event["event_id"])
        self.assertEqual(self.guard.consider("run", 2, later)["decision"], "HELD_EVENT_ID_REUSE")

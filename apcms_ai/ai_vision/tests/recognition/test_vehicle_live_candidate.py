# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_vehicle_live_candidate.py

import copy
import unittest
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.vehicle_delivery_flow import VehicleDeliveryFlow
from ai_vision.recognition.vehicle_http import VehicleHTTPClient
from ai_vision.recognition.vehicle_live_candidate import create_live_candidate
from ai_vision.tests.recognition.test_vehicle_http import mock_http


def live_passage():
    samples = [{"frame_index": f, "video_seconds": t, "plate_number": "91소6408", "plate_type": "KOREAN_VALID",
                "plate_detection_confidence": c} for f, t, c in ((10, 1, .9), (13, 1.3, .8))]
    return {"record_type": "LIVE_TRACKED_PASSAGE", "http_enabled": False, "track_id": 7,
            "screen_direction": "DOWN", "crossing_video_seconds": 1,
            "samples": samples, "plate_consensus": summarize_plate_samples(samples)}


class VehicleLiveCandidateTests(unittest.TestCase):
    def convert(self, passage, **kwargs):
        options = {"camera_id": "SIMULATION_ONLY", "down_direction": "ENTRY", "detected_at": "2020-01-01T00:00:01Z"}
        return create_live_candidate(passage, **{**options, **kwargs})

    def test_confirmed_live_result_has_explicit_time_and_conservative_confidence(self):
        passage = live_passage()
        before = copy.deepcopy(passage)
        result = self.convert(passage)
        self.assertEqual(result["status"], "CANDIDATE_ONLY")
        self.assertEqual(result["payload"]["confidence"], .8)
        self.assertEqual(result["payload"]["detected_at"], "2020-01-01T00:00:01+00:00")
        self.assertEqual(passage, before)

    def test_foreign_unconfirmed_and_conflicting_plates_are_blocked(self):
        for variant in ("foreign", "single", "conflict"):
            passage = live_passage()
            if variant == "foreign":
                for sample in passage["samples"]:
                    sample.update(plate_number="ABC123", plate_type="FOREIGN_OR_OTHER")
            elif variant == "single":
                passage["samples"] = passage["samples"][:1]
            else:
                passage["samples"][1]["plate_number"] = "12가3456"
            passage["plate_consensus"] = summarize_plate_samples(passage["samples"])
            result = self.convert(passage)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIsNone(result["payload"])

    def test_offline_or_forged_consensus_and_missing_settings_are_rejected(self):
        passage = live_passage()
        with self.assertRaises(ValueError):
            self.convert({**passage, "record_type": "LOCAL_TRACKED_PASSAGE"})
        for kwargs in ({"camera_id": ""}, {"down_direction": None}, {"detected_at": "2020-01-01T00:00:00"}):
            with self.assertRaises(ValueError):
                self.convert(passage, **kwargs)
        passage["plate_consensus"]["plate_number"] = "12가3456"
        with self.assertRaises(ValueError):
            self.convert(passage)

    def test_camera_direction_is_explicit_and_up_is_opposite(self):
        passage = live_passage()
        self.assertEqual(self.convert(passage, down_direction="EXIT")["payload"]["direction"], "EXIT")
        passage["screen_direction"] = "UP"
        self.assertEqual(self.convert(passage)["payload"]["direction"], "EXIT")

    def test_missing_detection_confidence_is_not_replaced_with_fixed_score(self):
        passage = live_passage()
        del passage["samples"][0]["plate_detection_confidence"]
        result = self.convert(passage)
        self.assertIn("MISSING_DETECTION_CONFIDENCE", result["reasons"])
        self.assertIsNone(result["payload"])

    def test_regenerated_uuid_on_repeated_conversion_still_makes_one_mock_post(self):
        session, _ = mock_http()
        flow = VehicleDeliveryFlow(VehicleHTTPClient("http://example.invalid", "KEY", True, session_factory=lambda: session))
        first, second = self.convert(live_passage()), self.convert(live_passage())
        self.assertNotEqual(first["payload"]["event_id"], second["payload"]["event_id"])
        # 모의 응답 UUID도 최초 후보 UUID와 일치하게 구성합니다.
        import json
        session.post.return_value.iter_content.return_value = [json.dumps({"eventId": first["payload"]["event_id"],
            "eventType": "VEHICLE_PASSAGE", "plateNumber": "91소6408", "outcome": "PROCESSED"}).encode("utf-8")]
        self.assertEqual(flow.process("run", first)["receipt_state"], "APPLIED")
        self.assertEqual(flow.process("run", second)["decision"], "SUPPRESSED_SAME_TRACK")
        session.post.assert_called_once()


class SpaceMatchCandidateTests(unittest.TestCase):
    def test_current_live_match_maps_db_code_and_preserves_source_time(self):
        from ai_vision.recognition.vehicle_live_candidate import create_space_match_candidate
        current = {'track_id': 2, 'space_id': 'A-01', 'plate_number': '91소6408'}
        event = {**current, 'kind': 'LIVE_SPACE_MATCH', 'plate_detection_confidence': .83}
        result = create_space_match_candidate(event, [current], 'PARKING_1', '2020-01-01T00:00:00Z')
        self.assertEqual(result['payload']['space_code'], '1F-A01')
        self.assertEqual(result['payload']['confidence'], .83)
        self.assertEqual(result['payload']['event_type'], 'VEHICLE_SPACE_MATCH')
        self.assertTrue(result['payload']['detected_at'].startswith('2020-01-01'))
        self.assertEqual(create_space_match_candidate(event, [], 'PARKING_1', '2020-01-01T00:00:00Z')['status'], 'BLOCKED')
        with self.assertRaises(ValueError):
            create_space_match_candidate({**event, 'kind': 'LOCAL_SPACE_MATCH'}, [current], 'PARKING_1', '2020-01-01T00:00:00Z')

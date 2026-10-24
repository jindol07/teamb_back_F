# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_session.py

import copy
import json
import unittest
from unittest.mock import Mock
from dataclasses import replace
from datetime import datetime, timezone

from ai_vision.recognition.live_gate_clock import LiveGateClock
from ai_vision.recognition.live_gate_session import LiveGateSession
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.vehicle_delivery_flow import VehicleDeliveryFlow
from ai_vision.recognition.vehicle_http import VehicleHTTPClient
from ai_vision.tests.recognition.test_vehicle_http import mock_http


def passage():
    samples = [{"frame_index": i, "video_seconds": t, "plate_number": "91소6408", "plate_type": "KOREAN_VALID",
                "plate_detection_confidence": .8} for i, t in ((0, 0), (1, .3))]
    return {"record_type": "LIVE_TRACKED_PASSAGE", "http_enabled": False, "track_id": 7, "screen_direction": "DOWN",
            "crossing_video_seconds": .6, "samples": samples, "plate_consensus": summarize_plate_samples(samples)}


class LiveGateSessionTests(unittest.TestCase):
    def test_single_vehicle_mode_transfers_verified_entry_and_exit_to_other_reader(self):
        import tempfile
        from pathlib import Path
        from ai_vision.paths import RESULT_DIR
        from ai_vision.recognition.single_vehicle_handoff import SingleVehicleHandoffReader
        client = Mock(enabled=True)
        client.send.side_effect = lambda event: {'event_id': event['event_id'], 'event_type': 'VEHICLE_PASSAGE',
            'state': 'APPLIED', 'request_attempted': True, 'receipt_verified': True,
            'automatic_retry_allowed': False, 'parking_usage_id': 70}
        with tempfile.TemporaryDirectory(dir=RESULT_DIR) as folder:
            clock = LiveGateClock(datetime(2020,1,1,tzinfo=timezone.utc), 0)
            gate = LiveGateSession('TEST_GATE', 'ENTRY', clock, VehicleDeliveryFlow(client), Path(folder)/'handoff.json')
            reader = SingleVehicleHandoffReader(Path(folder)/'handoff.json', clock=lambda: stamp.captured_at)
            for i,t in enumerate((0,.3,.6)):
                stamp = gate.capture(i,t)
            gate.consume(passage(),stamp)
            self.assertEqual(reader.read()['plate_number'],'91소6408')
            other = copy.deepcopy(passage())
            other['track_id'] = 20
            for s in other['samples']:
                s['plate_number'] = '12가3456'
            other['plate_consensus'] = summarize_plate_samples(other['samples'])
            gate.consume(other,stamp)
            self.assertIsNone(reader.read())
            client.send.assert_called_once()
            for i,t in enumerate((.9,1.2,1.5),3):
                stamp = gate.capture(i,t)
            exit_row = copy.deepcopy(passage())
            exit_row.update(track_id=8, screen_direction='UP', crossing_video_seconds=1.5)
            for s,i,t in zip(exit_row['samples'],(3,4),(.9,1.2)):
                s.update(frame_index=i,video_seconds=t)
            exit_row['plate_consensus'] = summarize_plate_samples(exit_row['samples'])
            gate.consume(exit_row,stamp)
            self.assertEqual(gate.handoff.state['status'],'EMPTY')
            self.assertIsNone(reader.read())
            self.assertEqual(reader.last_exit['parking_usage_id'],70)
            self.assertEqual(client.send.call_count,2)
            gate.close()

    def setUp(self):
        clock = LiveGateClock(datetime(2020, 1, 1, tzinfo=timezone.utc), 0)
        self.session = LiveGateSession("TEST_GATE", "ENTRY", clock)
        for index, time in enumerate((0, .3, .6)):
            self.stamp = self.session.capture(index, time)

    def test_default_flow_is_disabled_and_summary_counts_passages(self):
        result = self.session.consume(passage(), self.stamp)
        self.assertEqual(result["decision"], "DISABLED")
        self.assertEqual(self.session.summary()["captured_frames"], 3)
        self.assertEqual(self.session.summary()["processed_passages"], 1)
        self.assertEqual(self.session.summary()["request_attempts"], 0)

    def test_foreign_stamp_offline_source_and_wrong_frame_time_are_rejected(self):
        with self.assertRaises(ValueError):
            self.session.consume(passage(), replace(self.stamp))
        for change in ({"record_type": "LOCAL_TRACKED_PASSAGE"}, {"crossing_video_seconds": 9}):
            with self.assertRaises(ValueError):
                self.session.consume({**passage(), **change}, self.stamp)
        wrong = passage()
        wrong["samples"][1]["video_seconds"] = .4
        with self.assertRaises(ValueError):
            self.session.consume(wrong, self.stamp)

    def test_future_or_unknown_sample_frames_are_rejected(self):
        self.session.capture(3, .9)
        for index, seconds in ((3, .9), (99, .3)):
            wrong = copy.deepcopy(passage())
            wrong["samples"][1].update(frame_index=index, video_seconds=seconds)
            wrong["plate_consensus"] = summarize_plate_samples(wrong["samples"])
            with self.assertRaises(ValueError):
                self.session.consume(wrong, self.stamp)

    def test_close_is_idempotent_and_blocks_late_frames_and_results(self):
        self.session.close()
        self.session.close()
        with self.assertRaises(ValueError):
            self.session.capture(3, .9)
        with self.assertRaises(ValueError):
            self.session.consume(passage(), self.stamp)
        self.assertTrue(self.session.summary()["closed"])

    def test_session_ids_are_distinct_and_mock_http_is_suppressed(self):
        session, response = mock_http()
        def post(url, **kwargs):
            event = kwargs["json"]
            response.iter_content.return_value = [json.dumps({"eventId": event["event_id"], "eventType": "VEHICLE_PASSAGE",
                "plateNumber": event["plate_number"], "outcome": "PROCESSED"}).encode("utf-8")]
            return response
        session.post.side_effect = post
        flow = VehicleDeliveryFlow(VehicleHTTPClient("http://example.invalid", "KEY", True, session_factory=lambda: session))
        self.session.flow = flow
        self.assertEqual(self.session.consume(passage(), self.stamp)["receipt_state"], "APPLIED")
        self.session.consume(passage(), self.stamp)
        session.post.assert_called_once()
        other = LiveGateSession("TEST_GATE", "ENTRY")
        self.assertNotEqual(self.session.session_id, other.session_id)

    # 손상된 기록은 전송 판단·건수 집계 전에 거부하고 정상 기록은 계속 받을 수 있어야 합니다.
    def test_malformed_passage_does_not_reach_flow_or_change_summary(self):
        original_flow = self.session.flow
        flow = Mock()
        flow.client.enabled = False
        self.session.flow = flow
        before = self.session.summary()
        for mutate in (lambda row: row["plate_consensus"].pop("minimum_votes"),
                       lambda row: row.update(screen_direction=[]),
                       lambda row: row["samples"][1].update(frame_index=99)):
            row = passage()
            mutate(row)
            with self.assertRaises(ValueError):
                self.session.consume(row, self.stamp)
            self.assertEqual(self.session.summary(), before)
        flow.process.assert_not_called()
        self.session.flow = original_flow
        self.assertEqual(self.session.consume(passage(), self.stamp)["decision"], "DISABLED")

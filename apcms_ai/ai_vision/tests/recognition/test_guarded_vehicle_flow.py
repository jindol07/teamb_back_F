# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_guarded_vehicle_flow.py

import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from ai_vision.recognition.guarded_vehicle_flow import MockVehicleEventFlow, build_flow_report
from ai_vision.recognition.run_guarded_vehicle_flow import demo_preview
from ai_vision.recognition.simulate_vehicle_exchange import simulate_payload


class GuardedVehicleFlowTests(unittest.TestCase):
    def setUp(self):
        self.preview = demo_preview()
        self.event = self.preview["items"][0]["payload"]

    def test_repeated_candidate_calls_mock_once_and_retains_receipt(self):
        before = json.dumps(self.preview)
        with patch("ai_vision.recognition.guarded_vehicle_flow.simulate_payload", wraps=simulate_payload) as mock:
            report = build_flow_report(self.preview, passes=3)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(report["mock_call_count"], 1)
        self.assertEqual([step["receipt_state"] for step in report["steps"]], ["APPLIED"] * 3)
        self.assertTrue(all(step["receipt"] is None for step in report["steps"][1:]))
        self.assertEqual(json.dumps(self.preview), before)

    def test_all_outcomes_block_second_mock_attempt(self):
        expected = {"processed": "APPLIED", "unchanged": "UNCHANGED", "pending": "HELD", "timeout": "DELIVERY_UNKNOWN",
                    "server_error": "DELIVERY_UNKNOWN", "bad_request": "REJECTED", "unauthorized": "AUTH_REQUIRED",
                    "wrong_event": "DELIVERY_UNKNOWN", "invalid_json": "DELIVERY_UNKNOWN"}
        for scenario, state in expected.items():
            with self.subTest(scenario=scenario):
                report = build_flow_report(self.preview, scenario, passes=2)
                self.assertEqual(report["mock_call_count"], 1)
                self.assertEqual([step["receipt_state"] for step in report["steps"]], [state, state])
                self.assertTrue(all(not step["automatic_retry_allowed"] for step in report["steps"]))

    def test_shared_flow_keeps_pending_when_later_call_requests_success(self):
        flow = MockVehicleEventFlow()
        first = flow.process("run", 1, self.event, "pending")
        later = flow.process("run", 1, self.event, "processed")
        self.assertEqual((first["receipt_state"], later["receipt_state"]), ("HELD", "HELD"))
        self.assertFalse(later["mock_invoked"])

    def test_local_mock_exception_becomes_unknown_without_error_leak_or_retry(self):
        flow = MockVehicleEventFlow()
        with patch("ai_vision.recognition.guarded_vehicle_flow.simulate_payload", side_effect=RuntimeError("private/path")) as mock:
            first = flow.process("run", 1, self.event)
            second = flow.process("run", 1, self.event)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(first["receipt"]["reason_code"], "LOCAL_RESPONSE_PROCESSING_FAILED")
        self.assertEqual(second["receipt_state"], "DELIVERY_UNKNOWN")
        self.assertNotIn("private", str(first))

    def test_invalid_mock_receipt_is_not_saved_as_success(self):
        with patch("ai_vision.recognition.guarded_vehicle_flow.simulate_payload", return_value={"state": "APPLIED"}):
            result = MockVehicleEventFlow().process("run", 1, self.event)
        self.assertEqual(result["receipt_state"], "DELIVERY_UNKNOWN")

    def test_invalid_scenario_does_not_reserve_candidate(self):
        flow = MockVehicleEventFlow()
        with self.assertRaises(ValueError):
            flow.process("run", 1, self.event, "bad_scenario")
        self.assertEqual(flow.process("run", 1, self.event)["decision"], "NEW_CANDIDATE")

    def test_concurrent_candidate_inputs_invoke_mock_once(self):
        flow = MockVehicleEventFlow()
        with patch("ai_vision.recognition.guarded_vehicle_flow.simulate_payload", wraps=simulate_payload) as mock:
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda _: flow.process("run", 1, self.event), range(32)))
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(sum(row["mock_invoked"] for row in results), 1)

    def test_blocked_preview_stays_blocked_without_mock(self):
        self.preview["candidate_count"] = 0
        self.preview["items"] = [{"track_id": 1, "status": "BLOCKED", "payload": None}]
        with patch("ai_vision.recognition.guarded_vehicle_flow.simulate_payload") as mock:
            report = build_flow_report(self.preview)
        mock.assert_not_called()
        self.assertEqual(report["skipped_blocked_per_pass"], 1)
        self.assertEqual(report["steps"], [])

    def test_invalid_later_row_does_not_partially_process_valid_row(self):
        self.preview["items"].append({"track_id": 2, "status": "CANDIDATE_ONLY", "reasons": [], "payload": {}})
        self.preview["candidate_count"] = self.preview["total"] = 2
        flow = MockVehicleEventFlow()
        with patch("ai_vision.recognition.guarded_vehicle_flow.simulate_payload") as mock:
            with self.assertRaises(ValueError):
                build_flow_report(self.preview, flow=flow)
        mock.assert_not_called()
        self.assertEqual(build_flow_report(demo_preview(), flow=flow)["mock_call_count"], 1)

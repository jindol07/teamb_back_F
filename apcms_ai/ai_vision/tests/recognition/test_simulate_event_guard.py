# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_simulate_event_guard.py

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.simulate_event_guard import demo_report, evaluate_preview, main
from ai_vision.recognition.vehicle_event_guard import VehicleEventGuard
from ai_vision.tests.recognition.test_vehicle_response import sample_event


def source_preview():
    return {"run_id": "demo", "record_type": "LOCAL_VEHICLE_EVENT_PREVIEW", "http_enabled": False, "sendable": False,
            "total": 1, "candidate_count": 1,
            "items": [{"track_id": 1, "status": "CANDIDATE_ONLY", "reasons": [], "payload": sample_event()}]}


class SimulateEventGuardTests(unittest.TestCase):
    def test_demo_covers_id_switch_timeout_boundary_and_out_of_order(self):
        result = demo_report()
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(len(result["steps"]), 7)
        by_case = {step["case"]: step for step in result["steps"]}
        self.assertEqual(by_case["same_track_after_timeout"]["receipt_state"], "DELIVERY_UNKNOWN")
        self.assertEqual(by_case["out_of_order"]["decision"], "HELD_OUT_OF_ORDER")
        self.assertFalse(result["sendable"])

    def test_repeated_preview_and_shared_guard_never_regenerate_same_candidate(self):
        source = source_preview()
        before = json.dumps(source)
        guard = VehicleEventGuard()
        self.assertEqual(evaluate_preview(source, guard, passes=3)["candidate_count"], 1)
        self.assertEqual(evaluate_preview(source, guard)["candidate_count"], 0)
        self.assertEqual(json.dumps(source), before)

    def test_blocked_preview_does_not_invent_a_candidate(self):
        source = source_preview()
        source["candidate_count"] = 0
        source["items"] = [{"track_id": 1, "status": "BLOCKED", "payload": None}]
        result = evaluate_preview(source)
        self.assertEqual((result["candidate_count"], result["skipped_blocked_per_pass"]), (0, 1))

    def test_bad_later_row_does_not_partially_reserve_first_candidate(self):
        source = source_preview()
        source["items"].append({"track_id": 2, "status": "CANDIDATE_ONLY", "reasons": [], "payload": {}})
        source["total"] = source["candidate_count"] = 2
        guard = VehicleEventGuard()
        with self.assertRaises(ValueError):
            evaluate_preview(source, guard)
        self.assertEqual(evaluate_preview(source_preview(), guard)["candidate_count"], 1)
        with self.assertRaises(ValueError):
            evaluate_preview(source_preview(), passes=0)

    def test_cli_is_offline_and_existing_report_is_preserved(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            assert root.resolve().is_relative_to(base.resolve())
            output = root / "guard.json"
            with patch("ai_vision.recognition.simulate_event_guard.ResultCatalog", return_value=ResultCatalog(root / "runs")):
                with patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")):
                    with contextlib.redirect_stdout(io.StringIO()):
                        main(["--demo", "--output", str(output)])
                    before = output.read_bytes()
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        main(["--demo", "--output", str(output)])
            self.assertEqual(before, output.read_bytes())
            self.assertTrue(json.loads(before)["uses_synthetic_event"])

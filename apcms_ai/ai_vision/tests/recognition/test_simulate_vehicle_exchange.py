# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_simulate_vehicle_exchange.py

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.simulate_vehicle_exchange import build_simulation, main, SCENARIOS
from ai_vision.tests.recognition.test_vehicle_response import sample_event


def preview(items):
    return {"record_type": "LOCAL_VEHICLE_EVENT_PREVIEW", "http_enabled": False, "sendable": False,
            "total": len(items), "candidate_count": sum(item["payload"] is not None for item in items), "items": items}


class SimulateVehicleExchangeTests(unittest.TestCase):
    def test_demo_checks_all_states_and_is_explicitly_synthetic(self):
        result = build_simulation(demo=True)
        self.assertEqual(result["case_count"], len(SCENARIOS))
        self.assertTrue(result["uses_synthetic_event"])
        self.assertFalse(result["http_enabled"])
        self.assertFalse(result["sendable"])
        states = {case["state"] for case in result["cases"]}
        self.assertEqual(states, {"APPLIED", "UNCHANGED", "HELD", "REJECTED", "AUTH_REQUIRED", "DELIVERY_UNKNOWN"})
        self.assertTrue(all(not case["automatic_retry_allowed"] for case in result["cases"]))

    def test_blocked_real_preview_is_skipped_not_replaced_with_demo(self):
        result = build_simulation(preview([{"status": "BLOCKED", "payload": None}]))
        self.assertEqual((result["case_count"], result["skipped_blocked_count"]), (0, 1))
        self.assertFalse(result["uses_synthetic_event"])

    def test_candidate_scenarios_keep_original_uuid_and_input(self):
        original = preview([{"status": "CANDIDATE_ONLY", "reasons": [], "payload": sample_event()}])
        before = json.dumps(original)
        result = build_simulation(original, scenarios=["processed", "timeout"])
        self.assertEqual(result["case_count"], 2)
        self.assertEqual(len({case["event_id"] for case in result["cases"]}), 1)
        self.assertEqual(json.dumps(original), before)

    def test_invalid_modes_counts_sendability_and_duplicates_are_rejected(self):
        candidate = {"status": "CANDIDATE_ONLY", "reasons": [], "payload": sample_event()}
        for value in ({}, {**preview([]), "sendable": True}, {**preview([]), "total": True}, preview([candidate, candidate])):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_simulation(value)
        with self.assertRaises(ValueError):
            build_simulation()
        with self.assertRaises(ValueError):
            build_simulation(preview([]), demo=True)
        with self.assertRaises(ValueError):
            build_simulation(demo=True, scenarios=["timeout", "timeout"])

    def test_cli_report_is_new_file_and_never_uses_requests(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            assert root.resolve().is_relative_to(base.resolve())
            output = root / "mock.json"
            with patch("ai_vision.recognition.simulate_vehicle_exchange.ResultCatalog", return_value=ResultCatalog(root / "runs")):
                with patch("requests.sessions.Session.request", side_effect=AssertionError("network is forbidden")):
                    with contextlib.redirect_stdout(io.StringIO()):
                        main(["--demo", "--output", str(output)])
                    before = output.read_bytes()
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        main(["--demo", "--output", str(output)])
            self.assertEqual(output.read_bytes(), before)
            self.assertTrue(json.loads(before)["uses_synthetic_event"])

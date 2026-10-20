# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_run_vehicle_delivery_check.py

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.run_vehicle_delivery_check import build_check_report, main
from ai_vision.recognition.simulate_vehicle_exchange import SCENARIOS


class RunVehicleDeliveryCheckTests(unittest.TestCase):
    def test_disabled_mode_makes_no_session_and_no_reservation(self):
        with patch("requests.Session", side_effect=AssertionError("session forbidden")):
            report = build_check_report()
        self.assertEqual(report["mock_post_calls"], 0)
        self.assertTrue(all(row["decision"] == "DISABLED" for row in report["steps"]))
        self.assertFalse(report["real_http_used"])

    def test_all_mock_http_scenarios_make_one_post_and_no_real_network(self):
        with patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")):
            for scenario in SCENARIOS:
                report = build_check_report("mock-http", scenario, passes=3)
                self.assertEqual(report["mock_post_calls"], 1, scenario)
                states = [row["receipt_state"] for row in report["steps"]]
                self.assertEqual(states, [states[0]] * 3)
                self.assertFalse(report["real_http_used"])

    def test_cli_report_is_synthetic_and_preserves_existing_file(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            assert root.resolve().is_relative_to(base.resolve())
            output = root / "delivery.json"
            with patch("ai_vision.recognition.run_vehicle_delivery_check.ResultCatalog", return_value=ResultCatalog(root / "runs")):
                with contextlib.redirect_stdout(io.StringIO()):
                    main(["--mode", "mock-http", "--scenario", "timeout", "--output", str(output)])
                before = output.read_bytes()
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(["--output", str(output)])
            self.assertTrue(json.loads(before)["uses_synthetic_event"])
            self.assertEqual(before, output.read_bytes())

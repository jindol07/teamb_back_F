# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_report.py

import copy
import unittest

from ai_vision.recognition.live_gate_report import validate_report
from ai_vision.recognition.run_live_gate import _demo
from ai_vision.recognition.live_gate_context import build_run_context


class LiveGateReportTests(unittest.TestCase):
    def test_demo_and_empty_session(self):
        # 1. 합성 실행도 실제 생성기의 결과를 그대로 검사합니다.
        source = _demo()
        report = validate_report(source)
        self.assertEqual(report["rows"][0]["plate_number"], "91소6408")
        self.assertEqual(report["unknown_request_attempts"], 0)
        self.assertNotIn("receipt", report["rows"][0])
        source.update(results=[], processed_passages=0, decision_counts={})
        self.assertEqual(validate_report(source)["rows"], [])

    def test_mismatched_counts_time_and_disabled_requests_rejected(self):
        source = _demo()
        variants = []
        for key, value in (("processed_passages", 2), ("request_attempts", 1), ("captured_frames", True),
                           ("closed", False), ("status", "RUNNING"), ("decision_counts", {"BLOCKED": 1})):
            changed = copy.deepcopy(source)
            changed[key] = value
            variants.append(changed)
        for key, value in (("captured_at", "2020-01-01T00:00:10+00:00"), ("sample_count", 1),
                           ("request_attempted", True), ("crossing_elapsed_seconds", float("nan"))):
            changed = copy.deepcopy(source)
            changed["results"][0][key] = value
            variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_report(changed)

    def test_unknown_request_is_distinct_from_zero(self):
        source = _demo()
        source["http_enabled"] = True
        source["decision_counts"] = {"NEW_CANDIDATE": 1}
        source["results"][0].update(http_enabled=True, decision="NEW_CANDIDATE",
                                   request_attempted=None, receipt_state="DELIVERY_UNKNOWN")
        report = validate_report(source)
        self.assertEqual(report["request_attempts"], 0)
        self.assertEqual(report["unknown_request_attempts"], 1)

    def test_cleanup_failure_remains_failed_and_contradiction_rejected(self):
        source = _demo()
        source["cleanup_errors"] = 1
        with self.assertRaises(ValueError):
            validate_report(source)
        source["status"] = "FAILED"
        self.assertEqual(validate_report(source)["cleanup_errors"], 1)

    def test_optional_diagnostics_allow_old_reports_but_reject_corrupt_new_values(self):
        source = _demo()
        self.assertIsNotNone(validate_report(source)["performance"])
        del source["performance"]
        self.assertIsNone(validate_report(source)["performance"])
        source["performance"] = {"scope": "LOCAL_WALL_TIME_ONLY"}
        with self.assertRaises(ValueError):
            validate_report(source)

    def test_processor_statistics_must_match_observation_partition(self):
        source = _demo()
        source["processor_statistics"] = {"frames": 3, "observations": 3, "already_counted": 0,
            "outside_roi": 0, "eligible": 3, "gap_resets": 0, "crossings": 1, "ocr_calls": 2, "peak_buffer_bytes": 100}
        self.assertEqual(validate_report(source)["processor_statistics"]["crossings"], 1)
        source["processor_statistics"]["observations"] = 4
        with self.assertRaises(ValueError):
            validate_report(source)

    def test_old_results_allow_missing_context_but_invalid_new_context_fails(self):
        source = _demo()
        self.assertEqual(validate_report(source)["run_context"]["source_type"], "SYNTHETIC")
        del source["run_context"]
        self.assertIsNone(validate_report(source)["run_context"])
        source["run_context"] = {"version": 1}
        with self.assertRaises(ValueError):
            validate_report(source)

    def test_context_source_and_recorded_frame_limit_must_match(self):
        source = _demo()
        source["uses_synthetic_source"] = False
        with self.assertRaises(ValueError):
            validate_report(source)
        source["uses_synthetic_source"] = True
        source["run_context"] = build_run_context(None, None, max_frames=1, synthetic=True)
        with self.assertRaises(ValueError):
            validate_report(source)

    def test_camera_capture_failure_requires_failed_status(self):
        for reason in ("CAMERA_OPEN_FAILED", "CAMERA_READ_FAILED"):
            source = _demo()
            source.update(status="FAILED", stop_reason=reason, error_type="ValueError", source_end_expected=False)
            self.assertEqual(validate_report(source)["stop_reason"], reason)
            source["status"] = "STOPPED"
            with self.assertRaises(ValueError):
                validate_report(source)

    def test_end_policy_is_optional_for_older_results_and_consistent_when_present(self):
        source = _demo()
        del source["source_end_expected"]
        self.assertIsNone(validate_report(source)["source_end_expected"])
        source["source_end_expected"] = False
        with self.assertRaises(ValueError):
            validate_report(source)
        source["source_end_expected"] = 1
        with self.assertRaises(ValueError):
            validate_report(source)

    def test_deadline_optional_but_recorded_limit_and_stop_reason_must_match(self):
        source = _demo()
        del source["deadline"]
        self.assertIsNone(validate_report(source)["deadline"])
        source["deadline"] = {"scope": "READ_BOUNDARY_CHECKS_ONLY", "seconds": 20, "checks": 2,
                              "last_checked_elapsed_seconds": 20, "expired_before_read": True}
        with self.assertRaises(ValueError):
            validate_report(source)
        source["stop_reason"] = "TIME_LIMIT"
        self.assertTrue(validate_report(source)["deadline"]["expired_before_read"])
        source["deadline"]["seconds"] = 10
        with self.assertRaises(ValueError):
            validate_report(source)

    def test_confirmed_label_with_too_few_recorded_votes_rejected(self):
        source = _demo()
        self.assertEqual(validate_report(source)["rows"][0]["accepted_votes"], 2)
        source["results"][0]["plate_consensus"]["votes"] = {"91소6408": 1}
        with self.assertRaises(ValueError):
            validate_report(source)

    def test_unconfirmed_plate_and_incomplete_failure_rejected(self):
        source = _demo()
        source["results"][0]["plate_consensus"]["status"] = "CONFLICT"
        with self.assertRaises(ValueError):
            validate_report(source)
        with self.assertRaises(ValueError):
            validate_report({"record_type": "LIVE_GATE_SESSION", "status": "FAILED"})

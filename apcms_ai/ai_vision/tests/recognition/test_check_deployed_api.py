# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_check_deployed_api.py

"""AWS 없이 Vision API 점검의 기대값·오류·응답 한도를 확인합니다."""

import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from pathlib import Path
from unittest.mock import Mock
from PIL import Image
import requests
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.check_deployed_api import run_check


def response(body, status=200, headers=None):
    result = Mock(status_code=status)
    result.headers = {"X-Request-ID": "a" * 32, "Server-Timing": "app;dur=1.25"} if headers is None else headers
    result.iter_content.return_value = [json.dumps(body).encode("utf-8")]
    return result


def session_with_success():
    session = Mock()
    session.get.side_effect = [response({"status": "ok", "scope": "PROCESS_ONLY"}),
                               response({"status": "CHECKED", "scope": "FILES_AND_STORAGE_ONLY"})]
    session.post.return_value = response({"success": True, "vehicle_count": 1,
        "vehicles": [{"plate_number": "91소6408", "plate_type": "KOREAN_VALID"}]})
    return session


class CheckDeployedAPITests(unittest.TestCase):
    def check_vehicles(self, vehicles, **options):
        session = session_with_success()
        session.post.return_value = response({"success": bool(vehicles), "vehicle_count": len(vehicles), "vehicles": vehicles})
        return run_check(image=self.image, session_factory=lambda: session, **options)

    def test_review_text_type_and_reason_match_without_storing_text(self):
        result = self.check_vehicles([{"plate_number": "10-1557", "plate_type": "REVIEW",
                                      "review_reasons": ["KOREAN_CHARACTER_NOT_FOUND"]}],
                                    expected_ocr_text="10-1557", expected_plate_type="REVIEW",
                                    expected_review_reason="KOREAN_CHARACTER_NOT_FOUND")
        self.assertEqual(result["status"], "PASS")
        self.assertNotIn("10-1557", str(result))

    def test_foreign_plate_can_be_checked(self):
        result = self.check_vehicles([{"plate_number": "ABC123", "plate_type": "FOREIGN_OR_OTHER",
                                      "review_reasons": ["NON_KOREAN_PLATE_FORMAT"]}],
                                    expected_ocr_text="ABC123", expected_plate_type="FOREIGN_OR_OTHER")
        self.assertEqual(result["status"], "PASS")

    def test_conditions_must_match_the_same_vehicle(self):
        result = self.check_vehicles([{"plate_number": "10-1557", "plate_type": "REVIEW"},
                                     {"plate_number": "ABC123", "plate_type": "FOREIGN_OR_OTHER"}],
                                    expected_ocr_text="10-1557", expected_plate_type="FOREIGN_OR_OTHER")
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["checks"][-1]["expected_vehicle_matched"])

    def test_legacy_reason_absence_is_not_a_reason_match(self):
        vehicle = {"plate_number": "10-1557", "plate_type": "REVIEW"}
        self.assertEqual(self.check_vehicles([vehicle], expected_plate_type="REVIEW")["status"], "PASS")
        self.assertEqual(self.check_vehicles([vehicle], expected_review_reason="KOREAN_CHARACTER_NOT_FOUND")["status"], "FAIL")

    def test_invalid_reason_metadata_is_rejected(self):
        for reasons in (None, "KOREAN_CHARACTER_NOT_FOUND", [], ["UNKNOWN"], ["NO_OCR_TEXT"]):
            with self.subTest(reasons=reasons):
                result = self.check_vehicles([{"plate_number": "10-1557", "plate_type": "REVIEW", "review_reasons": reasons}])
                self.assertEqual(result["checks"][-1]["reason"], "INVALID_RESPONSE")

    def test_conflicting_expectations_stop_before_network(self):
        for options in ({"expected_plate": "91소6408", "expected_plate_type": "REVIEW"},
                        {"expected_plate": "91소6408", "expected_ocr_text": "other"},
                        {"expected_plate": "91소6408", "expected_review_reason": "NO_OCR_TEXT"},
                        {"expected_plate_type": "REVIEW", "expected_vehicle_count": 0},
                        {"expected_ocr_text": "x" * 1025}, {"expected_plate_type": "UNKNOWN"},
                        {"expected_review_reason": "UNKNOWN"}):
            factory = Mock()
            with self.subTest(options=options), self.assertRaises(ValueError):
                run_check(image=self.image, session_factory=factory, **options)
            factory.assert_not_called()
        with self.assertRaises(ValueError):
            run_check(expected_plate_type="REVIEW")

    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        self.image = Path(temporary.name) / "private-file.png"
        Image.new("RGB", (20, 20), "white").save(self.image)

    def test_health_only_does_not_upload_and_resources_are_closed(self):
        session = session_with_success()
        result = run_check(session_factory=lambda: session)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["recognition_tested"])
        session.post.assert_not_called()
        self.assertFalse(session.trust_env)
        session.close.assert_called_once()

    def test_expected_plate_and_count_match_without_storing_sensitive_details(self):
        session = session_with_success()
        result = run_check(image=self.image, expected_plate="91소6408", expected_vehicle_count=1,
                           require_diagnostics=True, session_factory=lambda: session)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["recognition_tested"])
        self.assertTrue(result["checks"][-1]["expected_plate_matched"])
        for private in ("91소6408", "private-file", str(self.image.parent)):
            self.assertNotIn(private, str(result))
        self.assertFalse(session.post.call_args.kwargs["allow_redirects"])

    def test_unmatched_expected_plate_or_vehicle_count_fails(self):
        for options in ({"expected_plate": "12가3456"}, {"expected_vehicle_count": 0}):
            session = session_with_success()
            result = run_check(image=self.image, session_factory=lambda: session, **options)
            self.assertEqual(result["status"], "FAIL")

    def test_failed_readiness_prevents_image_upload(self):
        session = session_with_success()
        session.get.side_effect = [response({"status": "ok", "scope": "PROCESS_ONLY"}), response({}, 503)]
        result = run_check(image=self.image, session_factory=lambda: session)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["checks"][-1]["reason"], "PREREQUISITE_FAILED")
        session.post.assert_not_called()

    def test_missing_diagnostics_can_be_optional_but_invalid_is_failure(self):
        for headers, required, expected in (({}, False, "PASS"), ({}, True, "FAIL"),
                                            ({"X-Request-ID": "invalid"}, False, "FAIL")):
            session = session_with_success()
            session.get.side_effect = [response({"status": "ok", "scope": "PROCESS_ONLY"}, headers=headers),
                                       response({"status": "CHECKED", "scope": "FILES_AND_STORAGE_ONLY"}, headers=headers)]
            self.assertEqual(run_check(require_diagnostics=required, session_factory=lambda: session)["status"], expected)

    def test_timeout_oversized_and_non_json_responses_are_failures(self):
        for outcome in (requests.Timeout(), b"x" * (1024 * 1024 + 1), b"not json"):
            session = session_with_success()
            if isinstance(outcome, Exception):
                session.get.side_effect = outcome
            else:
                result = response({})
                result.iter_content.return_value = [outcome]
                session.get.side_effect = [result, response({"status": "CHECKED", "scope": "FILES_AND_STORAGE_ONLY"})]
            self.assertEqual(run_check(session_factory=lambda: session)["status"], "FAIL")
            session.close.assert_called_once()

    def test_real_loopback_http_checks_diagnostics_without_aws(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                data = {"status": "ok", "scope": "PROCESS_ONLY"} if self.path == "/health" else {"status": "CHECKED", "scope": "FILES_AND_STORAGE_ONLY"}
                raw = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("X-Request-ID", "a" * 32)
                self.send_header("Server-Timing", "app;dur=1.25")
                self.end_headers()
                self.wfile.write(raw)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = run_check(f"http://127.0.0.1:{server.server_port}", require_diagnostics=True, timeout=3)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["checks"][0]["server_duration_ms"], 1.25)
            self.assertFalse(result["recognition_tested"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())

    def test_invalid_inputs_do_not_create_http_session(self):
        factory = Mock()
        for options in ({"base_url": "http://user:pass@example.com"}, {"base_url": "http://example.com?key=secret"},
                        {"expected_plate": "91소6408"}, {"timeout": True}, {"expected_vehicle_count": -1},
                        {"image": self.image, "expected_plate": "10-1557"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                run_check(session_factory=factory, **options)
        factory.assert_not_called()

    def test_no_vehicle_contract_is_valid_and_cleanup_failure_is_reported(self):
        session = session_with_success()
        session.post.return_value = response({"success": False, "vehicle_count": 0, "vehicles": []})
        result = run_check(image=self.image, expected_vehicle_count=0, session_factory=lambda: session)
        self.assertEqual(result["status"], "PASS")
        session = session_with_success()
        session.close.side_effect = OSError("private-path")
        result = run_check(session_factory=lambda: session)
        self.assertEqual(result["status"], "FAIL")
        self.assertNotIn("private-path", str(result))

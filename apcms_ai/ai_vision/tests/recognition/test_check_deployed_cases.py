# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_check_deployed_cases.py

"""사례 묶음 점검의 사전 검사·실패 집계·중단 시 저장을 확인합니다."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.check_deployed_cases import load_cases, main, run_cases
from ai_vision.tests.recognition.test_check_deployed_api import response, session_with_success


class CheckDeployedCasesTests(unittest.TestCase):
    def test_image_change_after_preflight_stops_before_upload(self):
        self.save_cases([self.case()])
        from ai_vision.recognition.check_deployed_cases import load_cases
        cases = load_cases(self.manifest, "http://127.0.0.1:8000")
        Image.new("RGB", (20, 20), "black").save(self.folder / "private.png")
        factory = Mock()
        with patch("ai_vision.recognition.check_deployed_cases.load_cases", return_value=cases):
            result = run_cases(self.manifest, self.output, session_factory=factory)
        factory.assert_not_called()
        self.assertEqual(result["cases"][0]["result"]["reason"], "CASE_INPUT_CHANGED")

    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        Image.new("RGB", (20, 20), "white").save(self.folder / "private.png")
        self.manifest = self.folder / "private-cases.json"
        self.output = self.folder / "output"

    def save_cases(self, cases):
        self.manifest.write_text(json.dumps({"cases": cases}), encoding="utf-8")

    def case(self, identifier="private_name", **expectations):
        return {"id": identifier, "image": "private.png", **(expectations or {"expected_plate": "91소6408"})}

    def test_mixed_real_checks_are_aggregated_without_sensitive_inputs(self):
        self.save_cases([self.case(), self.case("empty", expected_vehicle_count=0),
                         self.case("review", expected_ocr_text="10-1557", expected_plate_type="REVIEW",
                                   expected_review_reason="KOREAN_CHARACTER_NOT_FOUND"),
                         self.case("foreign", expected_plate_type="FOREIGN_OR_OTHER")])
        first, second = session_with_success(), session_with_success()
        second.post.return_value = response({"success": False, "vehicle_count": 0, "vehicles": []})
        third, fourth = session_with_success(), session_with_success()
        third.post.return_value = response({"success": True, "vehicle_count": 1, "vehicles": [
            {"plate_number": "10-1557", "plate_type": "REVIEW", "review_reasons": ["KOREAN_CHARACTER_NOT_FOUND"]}]})
        fourth.post.return_value = response({"success": True, "vehicle_count": 1, "vehicles": [
            {"plate_number": "ABC123", "plate_type": "FOREIGN_OR_OTHER"}]})
        factory = Mock(side_effect=[first, second, third, fourth])
        result = run_cases(self.manifest, self.output, session_factory=factory)
        self.assertEqual((result["status"], result["passed_cases"], result["completed_cases"]), ("PASS", 4, 4))
        self.assertEqual(json.loads((self.output / "api_cases.json").read_text(encoding="utf-8")), result)
        for sensitive in ("private_name", "private.png", "91소6408", "10-1557", "ABC123", str(self.folder)):
            self.assertNotIn(sensitive, str(result))
        first.close.assert_called_once()
        second.close.assert_called_once()

    def test_mismatch_does_not_prevent_later_case(self):
        self.save_cases([self.case(), self.case("second")])
        first = session_with_success()
        first.post.return_value = response({"success": False, "vehicle_count": 0, "vehicles": []})
        factory = Mock(side_effect=[first, session_with_success()])
        result = run_cases(self.manifest, self.output, session_factory=factory)
        self.assertEqual((result["status"], result["failed_cases"], result["passed_cases"]), ("FAIL", 1, 1))
        self.assertEqual(factory.call_count, 2)

    def test_invalid_last_case_stops_all_network_requests(self):
        bad_cases = [self.case("second", expected_plate_type="UNKNOWN"),
                     {**self.case("second"), "image": "missing.png"},
                     {**self.case("second"), "unexpected": True}, self.case(),
                     {"id": "second", "image": "private.png"},
                     self.case("second", expected_vehicle_count=None)]
        for bad in bad_cases:
            self.save_cases([self.case(), bad])
            factory = Mock()
            with self.subTest(bad=bad), self.assertRaises((ValueError, OSError)):
                run_cases(self.manifest, self.output, session_factory=factory)
            factory.assert_not_called()
            self.assertFalse(self.output.exists())

    def test_existing_output_folder_stops_network(self):
        self.save_cases([self.case()])
        self.output.mkdir()
        factory = Mock()
        with self.assertRaises(FileExistsError):
            run_cases(self.manifest, self.output, session_factory=factory)
        factory.assert_not_called()

    def test_interrupt_leaves_completed_results_and_incomplete_status(self):
        self.save_cases([self.case(), self.case("second")])
        with patch("ai_vision.recognition.check_deployed_cases.run_check",
                   side_effect=[{"status": "PASS"}, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt):
                run_cases(self.manifest, self.output)
        stored = json.loads((self.output / "api_cases.json").read_text(encoding="utf-8"))
        self.assertEqual((stored["status"], stored["completed_cases"], stored["total_cases"]), ("INCOMPLETE", 1, 2))

    def test_input_change_is_sanitized_and_later_case_runs(self):
        self.save_cases([self.case(), self.case("second")])
        with patch("ai_vision.recognition.check_deployed_cases.run_check",
                   side_effect=[ValueError("private exception"), {"status": "PASS"}]):
            result = run_cases(self.manifest, self.output)
        self.assertEqual(result["failed_cases"], 1)
        self.assertNotIn("private exception", str(result))

    def test_manifest_shape_and_duplicate_keys_are_rejected(self):
        for text in ('{"cases": [], "cases": []}', '{"cases": []}', '{"cases": [null]}',
                     json.dumps({"cases": [self.case(str(index)) for index in range(101)]})):
            self.manifest.write_text(text, encoding="utf-8")
            with self.subTest(text=text[:50]), self.assertRaises(ValueError):
                load_cases(self.manifest, "http://127.0.0.1:8000")

    def test_cli_exit_codes_and_option_forwarding(self):
        for status, code in (("PASS", 0), ("FAIL", 1)):
            with patch("ai_vision.recognition.check_deployed_cases.run_cases", return_value={"status": status}) as check, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--manifest", str(self.manifest), "--output-dir", str(self.output),
                                       "--require-diagnostics", "--timeout", "40"]), code)
                self.assertEqual(check.call_args.args[-2:], (True, 40))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(["--manifest", str(self.manifest), "--output-dir", str(self.output)])
        self.assertEqual(caught.exception.code, 2)

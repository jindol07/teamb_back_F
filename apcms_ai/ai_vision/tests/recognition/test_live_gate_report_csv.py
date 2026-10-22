# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_report_csv.py

import csv
import io
import unittest

from ai_vision.recognition.live_gate_report import validate_report
from ai_vision.recognition.live_gate_report_csv import FIELDS, REVIEW_FIELDS, render_csv
from ai_vision.recognition.run_live_gate import _demo


class LiveGateReportCsvTests(unittest.TestCase):
    def test_optional_review_columns_preserve_original_prefix_and_distinguish_unknown(self):
        report = validate_report(_demo())
        for reasons, state, codes in ((None, "UNRECORDED", ""), ([], "NO_REASONS", ""),
                                      (["KOREAN_CHARACTER_NOT_FOUND", "NO_OCR_TEXT"], "HAS_REASONS",
                                       "KOREAN_CHARACTER_NOT_FOUND|NO_OCR_TEXT")):
            report["rows"][0]["review_reasons"] = reasons
            rows = list(csv.DictReader(io.StringIO(render_csv(report, True))))
            self.assertEqual(tuple(rows[0]), FIELDS + REVIEW_FIELDS)
            self.assertEqual((rows[0]["review_reason_state"], rows[0]["review_reasons"]), (state, codes))
            self.assertEqual(tuple(next(csv.DictReader(io.StringIO(render_csv(report))))), FIELDS)

    def test_non_boolean_column_option_is_rejected(self):
        with self.assertRaises(ValueError):
            render_csv(validate_report(_demo()), "true")

    def test_columns_values_and_empty_receipt(self):
        report = validate_report(_demo())
        rows = list(csv.DictReader(io.StringIO(render_csv(report))))
        self.assertEqual(tuple(rows[0]), FIELDS)
        self.assertEqual(rows[0]["plate_number"], "91소6408")
        self.assertEqual(rows[0]["receipt_state"], "")
        self.assertEqual(rows[0]["request_attempted"], "False")

    def test_vote_columns_appended_after_original_columns(self):
        report = validate_report(_demo())
        row = list(csv.DictReader(io.StringIO(render_csv(report))))[0]
        self.assertEqual(FIELDS[-3:], ("accepted_votes", "required_votes", "minimum_spacing_seconds"))
        self.assertEqual((row["accepted_votes"], row["required_votes"], row["minimum_spacing_seconds"]), ("2", "2", "0.25"))

    def test_formula_cells_quoted_and_empty_report_has_headers(self):
        report = validate_report(_demo())
        report["rows"][0]["plate_number"] = '=HYPERLINK("x")'
        rows = list(csv.DictReader(io.StringIO(render_csv(report))))
        self.assertTrue(rows[0]["plate_number"].startswith("'="))
        report["rows"][0]["request_attempted"] = None
        rows = list(csv.DictReader(io.StringIO(render_csv(report))))
        self.assertEqual(rows[0]["request_attempted"], "UNKNOWN")
        report["rows"] = []
        self.assertEqual(list(csv.reader(io.StringIO(render_csv(report)))), [list(FIELDS)])

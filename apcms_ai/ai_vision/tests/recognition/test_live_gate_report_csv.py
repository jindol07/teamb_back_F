# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_report_csv.py

import csv
import io
import unittest

from ai_vision.recognition.live_gate_report import validate_report
from ai_vision.recognition.live_gate_report_csv import FIELDS, render_csv
from ai_vision.recognition.run_live_gate import _demo


class LiveGateReportCsvTests(unittest.TestCase):
    def test_columns_values_and_empty_receipt(self):
        report = validate_report(_demo())
        rows = list(csv.DictReader(io.StringIO(render_csv(report))))
        self.assertEqual(tuple(rows[0]), FIELDS)
        self.assertEqual(rows[0]["plate_number"], "91소6408")
        self.assertEqual(rows[0]["receipt_state"], "")
        self.assertEqual(rows[0]["request_attempted"], "False")

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

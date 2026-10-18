# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_review_passages.py

import contextlib
import io
import unittest
from unittest.mock import patch

from ai_vision.recognition.review_passages import main


class ReviewPassagesCLITests(unittest.TestCase):
    def test_template_dispatch_and_pending_explanation(self):
        with patch("ai_vision.recognition.review_passages.create_template", return_value=2) as create:
            with contextlib.redirect_stdout(io.StringIO()) as stream:
                main(["template", "--run-id", "demo", "--output", "review.csv"])
        self.assertEqual(create.call_args.args[1], "demo")
        self.assertIn("PENDING", stream.getvalue())

    def test_report_dispatch(self):
        report = {"verified_plate_rows": 1, "review_status_counts": {"PENDING": 2}}
        with patch("ai_vision.recognition.review_passages.create_report", return_value=report) as create:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["report", "--run-id", "demo", "--labels", "labels.csv", "--output", "report.json"])
        self.assertEqual(str(create.call_args.args[2]), "labels.csv")

    def test_missing_arguments_have_nonzero_exit(self):
        for args in ([], ["template"], ["report", "--run-id", "demo", "--output", "report.json"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(error.exception.code, 2)

    def test_validation_failure_has_nonzero_exit(self):
        with patch("ai_vision.recognition.review_passages.create_template", side_effect=ValueError("stale")):
            with contextlib.redirect_stderr(io.StringIO()) as stream, self.assertRaises(SystemExit) as error:
                main(["template", "--run-id", "demo", "--output", "review.csv"])
        self.assertEqual(error.exception.code, 1)
        self.assertIn("stale", stream.getvalue())

    def test_bundle_dispatch_and_page_options(self):
        result = {"total": 30, "shown": 5, "image_count": 8}
        with patch("ai_vision.recognition.review_passages.create_bundle", return_value=result) as create:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["bundle", "--run-id", "demo", "--output", "review.html", "--offset", "20", "--limit", "5"])
        self.assertEqual(create.call_args.args[-2:], (20, 5))

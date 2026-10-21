# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_result_validation.py

import unittest
import copy
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.result_validation import public_passage, validate_summary


class ResultValidationTests(unittest.TestCase):
    def test_summary_counts_and_coverage_must_agree(self):
        result = {"kind": "pipeline", "total_crossings": 2, "ocr_processed": 1,
                  "crossing_counts": {"DOWN": 2}, "plate_status_counts": {"CONFLICT": 1}, "ocr_coverage": "PARTIAL"}
        validate_summary(result)
        for changes in ({"crossing_counts": {"DOWN": 3}}, {"plate_status_counts": {}},
                        {"ocr_coverage": "ALL_RECORDED_TRACKS"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_summary({**result, **changes})

    def test_ocr_count_order(self):
        with self.assertRaises(ValueError):
            validate_summary({"kind": "ocr", "confirmed_plates": 2, "processed_tracks": 1, "crossings_in_run": 1})

    def test_malformed_nested_samples_raise_validation_error(self):
        row = {"http_enabled": False, "record_type": "LOCAL_TRACKED_PASSAGE", "track_id": 1,
               "screen_direction": "DOWN", "crossing_video_seconds": 1}
        for changes in ({"samples": [None], "plate_consensus": {}},
                        {"samples": [], "plate_consensus": []}, {"samples": None, "plate_consensus": {}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                public_passage({**row, **changes})

    def valid_row(self):
        samples = [{"frame_index": i, "video_seconds": i * .3,
                    "plate_number": "91소6408", "plate_type": "KOREAN_VALID"} for i in range(2)]
        return {"http_enabled": False, "record_type": "LOCAL_TRACKED_PASSAGE", "track_id": 1,
                "screen_direction": "DOWN", "crossing_video_seconds": .6,
                "samples": samples, "plate_consensus": summarize_plate_samples(samples)}

    def test_every_missing_consensus_field_is_validation_error(self):
        for key in self.valid_row()["plate_consensus"]:
            row = self.valid_row()
            del row["plate_consensus"][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                public_passage(row)

    def test_invalid_direction_and_nested_votes_are_validation_errors(self):
        for direction in ([], {}, None, True):
            with self.subTest(direction=direction), self.assertRaises(ValueError):
                public_passage({**self.valid_row(), "screen_direction": direction})
        for field, value in (("votes", []), ("votes", {"91소6408": True}),
                             ("observed_valid_numbers", [None]), ("minimum_votes", "2"),
                             ("minimum_spacing_seconds", None)):
            row = self.valid_row()
            row["plate_consensus"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                public_passage(row)

    def test_valid_input_is_unchanged_and_forged_votes_are_rejected(self):
        row = self.valid_row()
        before = copy.deepcopy(row)
        self.assertEqual(public_passage(row)["plate_status"], "CONFIRMED")
        self.assertEqual(row, before)
        row["plate_consensus"]["votes"]["91소6408"] = 3
        with self.assertRaises(ValueError):
            public_passage(row)

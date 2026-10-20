# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_plate_consensus.py

# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_plate_consensus.py

import unittest

from ai_vision.recognition.plate_consensus import summarize_plate_samples, validate_plate_summary
from ai_vision.recognition.recognize_tracked_passages import select_samples


class PlateConsensusTests(unittest.TestCase):
    def test_invalid_time_or_policy_rejected(self):
        for time in [float("nan"), float("inf"), -1, True]:
            with self.subTest(time=time), self.assertRaises(ValueError):
                summarize_plate_samples([self.sample(0, time)])
        with self.assertRaises(ValueError):
            summarize_plate_samples([], minimum_spacing=.1)

    def test_same_frame_conflicting_numbers_are_not_hidden(self):
        samples = [self.sample(0, 0), self.sample(0, 0, "12가3456"), self.sample(18, .3)]
        self.assertEqual(summarize_plate_samples(samples)["status"], "CONFLICT")
    def sample(self, frame, time, text="91소6408", kind="KOREAN_VALID"):
        return {"frame_index": frame, "video_seconds": time, "plate_number": text, "plate_type": kind}

    # 1. 다른 시점에서 같은 번호가 반복될 때만 확정
    def test_repeated_plate_confirmed(self):
        result = summarize_plate_samples([self.sample(0, 0), self.sample(18, .3)])
        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(result["plate_number"], "91소6408")

    # 2. 같은 프레임이나 너무 가까운 프레임으로 표 수를 늘리지 않음
    def test_duplicate_and_nearby_frames_not_extra_votes(self):
        for samples in [[self.sample(0, 0), self.sample(0, 0)],
                        [self.sample(0, 0), self.sample(1, .01)]]:
            self.assertEqual(summarize_plate_samples(samples)["status"], "INSUFFICIENT_EVIDENCE")
        with self.assertRaises(ValueError):
            summarize_plate_samples([self.sample(0, 0), self.sample(0, .3)])

    # 3. 서로 다른 유효 번호가 한 번이라도 보이면 다수결로 확정하지 않음
    def test_conflict_is_not_hidden_by_majority_or_spacing(self):
        result = summarize_plate_samples([self.sample(0, 0), self.sample(1, .01, "12가3456"),
                                         self.sample(18, .3)])
        self.assertEqual(result["status"], "CONFLICT")
        self.assertEqual(result["plate_number"], "")

    def test_foreign_and_invalid_formats_not_confirmed(self):
        samples = [self.sample(0, 0, "AB1234", "FOREIGN_OR_OTHER"),
                   self.sample(18, .3, "WRONG", "KOREAN_VALID")]
        self.assertEqual(summarize_plate_samples(samples)["status"], "NO_VALID_KOREAN_PLATE")

    # 4. 선택 프레임은 통과 전후 범위와 시간 간격을 모두 만족해야 함
    def test_sample_selection_window_and_spacing(self):
        rows = [{"frame_index": i, "video_seconds": t, "box": [0, 0, 100, 100]}
                for i, t in enumerate([0, 8, 8.1, 8.3, 9, 10.5, 11])]
        selected = select_samples(rows, 10)
        self.assertEqual(len(selected), 3)
        self.assertTrue(all(8 <= row["video_seconds"] <= 10.75 for row in selected))
        self.assertTrue(all(b["video_seconds"] - a["video_seconds"] >= .25 - 1e-9
                            for a, b in zip(selected, selected[1:])))


class SavedPlateSummaryTests(unittest.TestCase):
    def sample(self, index, plate="91소6408"):
        return {"frame_index": index, "video_seconds": index * .3, "plate_number": plate, "plate_type": "KOREAN_VALID"}

    def test_all_generated_statuses_validate_with_original_sample_count(self):
        for samples, expected in (([], "NO_VALID_KOREAN_PLATE"), ([self.sample(0)], "INSUFFICIENT_EVIDENCE"),
                ([self.sample(0), self.sample(1)], "CONFIRMED"),
                ([self.sample(0), self.sample(1, "12가3456")], "CONFLICT")):
            with self.subTest(status=expected):
                checked = validate_plate_summary(summarize_plate_samples(samples), len(samples))
                self.assertEqual(checked["plate_status"], expected)
                self.assertEqual(checked["accepted_votes"], len(samples))

    def test_forged_confirmed_votes_and_conditions_rejected(self):
        summary = summarize_plate_samples([self.sample(0), self.sample(1)])
        for changes in ({"votes": {}}, {"votes": {"91소6408": 1}}, {"votes": {"91소6408": True}},
                        {"votes": {"91소6408": 3}}, {"minimum_votes": 1},
                        {"minimum_spacing_seconds": .1}, {"plate_type": None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_plate_summary({**summary, **changes}, 2)

    def test_observed_numbers_and_votes_must_agree(self):
        summary = summarize_plate_samples([self.sample(0), self.sample(1)])
        for observed in ([], ["bad"], ["91소6408", "91소6408"], ["12가3456"]):
            with self.assertRaises(ValueError):
                validate_plate_summary({**summary, "observed_valid_numbers": observed}, 2)
        with self.assertRaises(ValueError):
            validate_plate_summary(summary, True)

    def test_conflict_due_to_unaccepted_close_sample_stays_conflict(self):
        samples = [self.sample(0), {**self.sample(1, "12가3456"), "video_seconds": .01}, self.sample(2)]
        checked = validate_plate_summary(summarize_plate_samples(samples), 3)
        self.assertEqual((checked["plate_status"], checked["accepted_votes"]), ("CONFLICT", 2))


if __name__ == "__main__":
    unittest.main()

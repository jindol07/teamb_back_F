# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_evaluate_crossings.py

import unittest

from ai_vision.recognition.evaluate_crossings import evaluate


class CrossingEvaluationTests(unittest.TestCase):
    def annotations(self):
        # 1. 겹치는 허용 시간 구간을 가진 차량 두 대로 일대일 대응을 시험
        return {"label_status": "TEST_ONLY",
                "scope": {"start_seconds": 0, "end_seconds": 10, "x_min": 0, "x_max": 100},
                "vehicles": [{"label_id": "A", "direction": "DOWN", "earliest_seconds": 1, "latest_seconds": 4},
                             {"label_id": "B", "direction": "DOWN", "earliest_seconds": 1, "latest_seconds": 2}]}

    def event(self, time, track_id, direction="DOWN", x=50):
        return {"video_seconds": time, "track_id": track_id,
                "direction": direction, "crossing_point": [x, 100]}

    def test_overlap_reassigns_without_missing_vehicle(self):
        # 먼저 선택한 기록을 다른 차량에 넘겨 두 차량 모두 대응할 수 있어야 함
        report = evaluate([self.event(2, 1), self.event(4, 2)], self.annotations())
        self.assertEqual(report["matched_vehicles"], 2)
        self.assertEqual(report["missing_label_ids"], [])

    def test_duplicate_cannot_match_one_vehicle_twice(self):
        annotations = self.annotations()
        annotations["vehicles"] = annotations["vehicles"][:1]
        report = evaluate([self.event(2, 1), self.event(2.1, 2)], annotations)
        self.assertEqual(report["matched_vehicles"], 1)
        self.assertEqual(len(report["duplicate_candidate_indices"]), 1)

    def test_wrong_direction_and_outside_scope(self):
        # 역방향은 대응하지 않고, 다른 차로와 검토 시간 밖 기록은 평가에서 제외
        report = evaluate([self.event(2, 1, "UP"), self.event(2, 2, x=200),
                           self.event(10, 3)], self.annotations())
        self.assertEqual(report["recorded_events"], 1)
        self.assertEqual(report["matched_vehicles"], 0)
        self.assertEqual(report["extra_event_indices"], [1])

    def test_invalid_labels_rejected(self):
        annotations = self.annotations()
        annotations["vehicles"][1]["label_id"] = "A"
        with self.assertRaises(ValueError):
            evaluate([], annotations)


if __name__ == "__main__":
    unittest.main()

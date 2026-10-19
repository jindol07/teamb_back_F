# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_passage_query.py

import unittest
from ai_vision.recognition.passage_query import PassageQuery


class PassageQueryTests(unittest.TestCase):
    def test_combined_filters_include_time_boundaries(self):
        row = {"screen_direction": "DOWN", "plate_status": "CONFIRMED", "video_seconds": 2}
        self.assertTrue(PassageQuery("DOWN", "CONFIRMED", 2, 2).matches(row))
        self.assertFalse(PassageQuery("UP").matches(row))
        self.assertFalse(PassageQuery(end_seconds=1).matches(row))
        self.assertFalse(PassageQuery(plate_status="CONFLICT").matches(row))

    def test_invalid_conditions_are_rejected(self):
        # 서버와 CLI의 검색 조건이 같은 방식으로 거절되는지 확인합니다.
        for kwargs in ({"direction": "ENTRY"}, {"plate_status": "VALID"}, {"start_seconds": True},
                       {"start_seconds": float("nan")}, {"end_seconds": float("inf")},
                       {"start_seconds": -1}, {"start_seconds": 2, "end_seconds": 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                PassageQuery(**kwargs)

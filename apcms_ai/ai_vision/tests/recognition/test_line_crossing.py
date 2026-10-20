# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_line_crossing.py

# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_line_crossing.py

# 기준선 판별 규칙 검증: YOLO나 영상 없이 가상의 중심점 이동으로 시험
import unittest

from ai_vision.recognition.line_crossing import LineCrossingCounter


class LineCrossingTests(unittest.TestCase):
    def test_repeated_timestamp_does_not_confirm_side(self):
        counter = self.counter()
        counter.update(1, (80, 70), 0)
        counter.update(1, (80, 70), 0)
        self.assertEqual(counter.states[1].side, 0)
        counter.update(1, (80, 70), .1)
        self.assertEqual(counter.states[1].side, -1)

    def test_invalid_coordinates_and_reverse_time_rejected(self):
        counter = self.counter()
        with self.assertRaises(ValueError):
            counter.update(1, (float("nan"), 80), 0)
        counter.update(1, (80, 70), 1)
        with self.assertRaises(ValueError):
            counter.update(1, (80, 70), .5)
    # 1. 테스트 공통 설정과 가상 차량 이동 입력
    def counter(self):
        # y=100, x=20~180인 선분. 위아래 10px은 보류하고 같은 쪽 2회면 확정
        return LineCrossingCounter(100, 20, 180, margin=10, stable_frames=2)

    def feed(self, counter, ys, track_id=1, x=80, start=0):
        # ys의 y좌표들을 0.1초 간격으로 전달하고 확정된 통과 이벤트만 모음
        # := 는 반환값을 event에 저장하며 검사하는 대입 표현식
        return [event for index, y in enumerate(ys)
                if (event := counter.update(track_id, (x, y), start + index * 0.1))]

    # 2. 양방향 통과와 처음부터 선 아래에서 시작하는 차량을 구분합니다.
    def test_both_directions(self):
        counter = self.counter()
        self.assertEqual(self.feed(counter, [70, 75, 95, 115, 120])[0]["direction"], "DOWN")
        self.assertEqual(self.feed(counter, [130, 125, 105, 85, 80], 2)[0]["direction"], "UP")
        self.assertEqual(self.feed(counter, [130, 135, 140], 3), [])

    # 3. 선 주변 흔들림과 이미 집계한 ID의 재통과는 집계하지 않습니다.
    def test_jitter_and_duplicate(self):
        counter = self.counter()
        events = self.feed(counter, [70, 75, 99, 105, 98, 115, 100, 80, 75])
        self.assertEqual(events, [])
        self.assertEqual(len(self.feed(counter, [70, 75, 120, 125, 70, 75], start=1)), 1)

    # 4. 가림 뒤 갑자기 반대쪽에 나타나거나 선분 밖을 지나면 무시합니다.
    def test_gap_and_outside_segment(self):
        counter = self.counter()
        self.feed(counter, [70, 75])
        self.assertEqual(self.feed(counter, [120, 125], start=2), [])
        self.assertEqual(self.feed(counter, [70, 75, 120, 125], 2, x=200), [])

    def test_counted_id_stays_suppressed_after_gap(self):
        # 5. 위치 상태가 만료되어도 이미 집계한 ID 기록은 유지되어야 함
        counter = self.counter()
        self.assertEqual(len(self.feed(counter, [70, 75, 120, 125])), 1)
        self.assertEqual(self.feed(counter, [70, 75, 120, 125], start=3), [])

    def test_crossing_point_uses_segment_intersection(self):
        # 6. 양 끝 중심점이 선분 밖이어도 중간 궤적이 선분을 지나면 통과로 판단
        counter = self.counter()
        for point, time in [((0, 70), 0), ((0, 80), .1), ((200, 120), .4)]:
            self.assertIsNone(counter.update(1, point, time))
        event = counter.update(1, (200, 120), .5)
        self.assertEqual(event["crossing_point"], [100.0, 100])

    def test_position_jump_does_not_count_as_crossing(self):
        # 7. 0.01초 만에 y=135에서 70으로 튀면 연결 오류로 보고 통과를 보류
        counter = self.counter()
        self.feed(counter, [130, 135])
        self.assertIsNone(counter.update(1, (80, 70), .11))
        self.assertIsNone(counter.update(1, (80, 75), .2))

    def test_explicit_reset_keeps_counted_ids_suppressed(self):
        counter = self.counter()
        self.assertEqual(len(self.feed(counter, [70, 75, 120, 125])), 1)
        self.assertTrue(counter.reset_track(1))
        self.assertFalse(counter.reset_track(1))
        self.assertIn(1, counter.counted_ids)
        self.assertEqual(self.feed(counter, [70, 75, 120, 125], start=1), [])

    def test_continuity_reason_matches_gap_and_speed_rules_without_mutating(self):
        counter = self.counter()
        counter.update(1, (80, 70), 0)
        self.assertEqual(counter.continuity_break_reason(1, (80, 130), .01), "SPEED")
        self.assertEqual(counter.continuity_break_reason(1, (80, 70), 1.1), "GAP")
        self.assertIsNone(counter.continuity_break_reason(1, (80, 70), 1))
        self.assertEqual(counter.states[1].last_time, 0)
        with self.assertRaises(ValueError):
            counter.reset_track(True)


if __name__ == "__main__":
    unittest.main()

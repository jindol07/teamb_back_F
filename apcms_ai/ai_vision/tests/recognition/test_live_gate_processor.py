# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_processor.py

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import numpy as np
import cv2  # 기존 sys.modules 모의 처리 전에 네이티브 OpenCV 의존성을 초기화합니다.
from ai_vision.recognition.live_gate_clock import FrameStamp
from ai_vision.recognition.live_gate_processor import LiveGateProcessor

CONFIG = {"tracker": "bytetrack", "line_y": .5, "line_x": [.1, .9], "roi": [0, 0, 1, 0, 1, 1, 0, 1]}


def stamp(index):
    seconds = index * .3
    return FrameStamp(index, seconds, datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds))


class LiveGateProcessorTests(unittest.TestCase):
    def crossing(self, processor):
        passages = []
        for index in range(7):
            passages.extend(processor.process(np.full((100, 100, 3), index, dtype=np.uint8), stamp(index)))
        return passages

    def tracker(self, frame):
        index = int(frame[0, 0, 0])
        y = 20 if index < 3 else (50 if index == 3 else 80)
        return [{"track_id": 7, "box": [40, y - 10, 60, y + 10]}]

    def test_crossing_uses_original_crops_and_three_spaced_samples(self):
        seen = []
        def reader(crop):
            seen.append(int(crop[0, 0, 0]))
            return {"plate_number": "91소6408", "plate_type": "KOREAN_VALID", "plate_detection_confidence": .9}
        processor = LiveGateProcessor(CONFIG, self.tracker, reader)
        passages = self.crossing(processor)
        self.assertEqual(len(passages), 1)
        self.assertEqual(passages[0]["screen_direction"], "DOWN")
        self.assertEqual(passages[0]["plate_consensus"]["status"], "CONFIRMED")
        self.assertEqual(seen, [4, 5, 6])
        self.assertEqual(processor._bytes, 0)

    def test_no_crossing_does_not_load_or_call_ocr(self):
        reader = Mock(side_effect=AssertionError("OCR forbidden"))
        processor = LiveGateProcessor(CONFIG, lambda frame: [], reader)
        self.assertEqual(processor.process(np.zeros((100, 100, 3), dtype=np.uint8), stamp(0)), [])
        reader.assert_not_called()

    def test_buffer_budget_drops_crops_without_inventing_plate(self):
        reader = Mock(side_effect=AssertionError("no crop"))
        processor = LiveGateProcessor(CONFIG, self.tracker, reader, max_buffer_bytes=1)
        passages = self.crossing(processor)
        self.assertEqual(passages[0]["plate_consensus"]["status"], "NO_VALID_KOREAN_PLATE")
        self.assertGreater(processor.dropped_crops, 0)
        reader.assert_not_called()

    def test_duplicate_tracks_bad_boxes_resolution_change_and_close(self):
        row = {"track_id": 1, "box": [1, 1, 20, 20]}
        for rows in ([row, row], [{**row, "box": [-1, 1, 20, 20]}]):
            processor = LiveGateProcessor(CONFIG, lambda frame: rows)
            with self.assertRaises(ValueError):
                processor.process(np.zeros((100, 100, 3), dtype=np.uint8), stamp(0))
        processor = LiveGateProcessor(CONFIG, lambda frame: [])
        processor.process(np.zeros((100, 100, 3), dtype=np.uint8), stamp(0))
        with self.assertRaises(ValueError):
            processor.process(np.zeros((120, 100, 3), dtype=np.uint8), stamp(1))
        processor.close()
        self.assertEqual(processor._bytes, 0)
        with self.assertRaises(ValueError):
            processor.process(np.zeros((100, 100, 3), dtype=np.uint8), stamp(1))

    def test_track_limit_drops_extra_observations(self):
        rows = [{"track_id": track, "box": [10, 10, 30, 30]} for track in (1, 2)]
        processor = LiveGateProcessor(CONFIG, lambda frame: rows, max_tracks=1)
        processor.process(np.zeros((100, 100, 3), dtype=np.uint8), stamp(0))
        self.assertEqual(processor.dropped_tracks, 1)

    def test_statistics_count_repeated_observations_and_survive_close(self):
        processor = LiveGateProcessor(CONFIG, self.tracker, lambda crop: {"plate_number": "", "plate_type": "NOT_DETECTED"})
        self.crossing(processor)
        processor.process(np.full((100, 100, 3), 7, dtype=np.uint8), stamp(7))
        statistics = processor.statistics()
        self.assertEqual((statistics["frames"], statistics["observations"], statistics["eligible"], statistics["already_counted"]),
                         (8, 8, 7, 1))
        self.assertEqual((statistics["crossings"], statistics["ocr_calls"]), (1, 3))
        self.assertGreater(statistics["peak_buffer_bytes"], 0)
        processor.close()
        self.assertEqual(processor.statistics(), statistics)
        statistics["frames"] = -1
        self.assertEqual(processor.statistics()["frames"], 8)

    def test_roi_exclusion_and_gap_reset_are_reported(self):
        config = {**CONFIG, "roi": [.1, .1, .9, .1, .9, .9, .1, .9]}
        rows = [{"track_id": 1, "box": [0, 0, 4, 4]}, {"track_id": 2, "box": [20, 20, 40, 40]}]
        processor = LiveGateProcessor(config, lambda frame: rows)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        processor.process(frame, stamp(0))
        processor.process(frame, stamp(5))
        statistics = processor.statistics()
        self.assertEqual((statistics["observations"], statistics["outside_roi"], statistics["eligible"], statistics["gap_resets"]),
                         (4, 2, 2, 1))

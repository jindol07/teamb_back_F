# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_processor.py

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, patch

import numpy as np
import cv2  # 기존 sys.modules 모의 처리 전에 네이티브 OpenCV 의존성을 초기화합니다.
from ai_vision.recognition.live_gate_clock import FrameStamp
from ai_vision.recognition.live_gate_processor import LiveGateProcessor

CONFIG = {"tracker": "bytetrack", "line_y": .5, "line_x": [.1, .9], "roi": [0, 0, 1, 0, 1, 1, 0, 1]}


def stamp(index):
    seconds = index * .3
    return FrameStamp(index, seconds, datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds))


class LiveGateProcessorTests(unittest.TestCase):
    def test_plate_mode_uses_plate_model_nms_and_original_confidence(self):
        processor = LiveGateProcessor(CONFIG, tracking_target='plate')
        model = Mock(names={0:'plate',1:'plate_alt'})
        box = Mock()
        box.id.item.return_value = 7
        box.xyxy.__getitem__ = Mock(return_value=Mock(tolist=lambda:[10,20,50,40]))
        box.conf.item.return_value = .73
        boxes = MagicMock()
        boxes.id = object()
        boxes.__iter__.return_value = iter([box])
        model.track.return_value = [Mock(boxes=boxes)]
        processor._model = model
        rows = processor._track(np.zeros((100,100,3),dtype=np.uint8))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['plate_detection_confidence'],.73)
        self.assertTrue(model.track.call_args.kwargs['agnostic_nms'])
        self.assertEqual(model.track.call_args.kwargs['imgsz'],1280)
        self.assertEqual(model.track.call_args.kwargs['classes'],[0,1])

    def test_plate_inference_size_preserves_original_frame_and_coordinates(self):
        processor = LiveGateProcessor(CONFIG, tracking_target='plate', tracking_imgsz=960)
        model = Mock(names={0:'plate'})
        box = MagicMock()
        box.id.item.return_value = 3
        box.xyxy[0].tolist.return_value = [100,200,300,240]
        box.conf.item.return_value = .8
        boxes = MagicMock(id=object())
        boxes.__iter__.return_value = iter([box])
        model.track.return_value = [Mock(boxes=boxes)]
        processor._model = model
        frame = np.zeros((1024,1280,3),dtype=np.uint8)
        rows = processor._track(frame)
        self.assertIs(model.track.call_args.args[0],frame)
        self.assertEqual(model.track.call_args.kwargs['imgsz'],960)
        self.assertEqual(rows[0]['box'],[100,200,300,240])

    def test_invalid_inference_size_or_vehicle_override_is_rejected(self):
        for value in (True,960.0,0,800,'960'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                LiveGateProcessor(CONFIG,tracking_target='plate',tracking_imgsz=value)
        with self.assertRaises(ValueError):
            LiveGateProcessor(CONFIG,tracking_imgsz=960)

    def test_plate_crossing_uses_direct_ocr_and_keeps_detection_evidence(self):
        def tracker(frame):
            return [row | {'plate_detection_confidence':.72} for row in self.tracker(frame)]
        processor = LiveGateProcessor(CONFIG, tracker=tracker, tracking_target='plate')
        with patch('ai_vision.recognition.recognizer.recognize_plate',return_value={
                'plate_number':'91소6408','plate_type':'KOREAN_VALID','plate_detection_confidence':.99}) as read, \
                patch.object(processor,'_read_plate',side_effect=AssertionError('Repeated detection forbidden')):
            passages = self.crossing(processor)
        self.assertEqual(len(passages),1)
        self.assertEqual(passages[0]['plate_consensus']['status'],'CONFIRMED')
        self.assertEqual(read.call_count,3)
        self.assertTrue(all(x['plate_detection_confidence']==.72 for x in passages[0]['samples']))
        self.assertEqual(read.call_args.args[0].shape[:2],(24,24))

    def test_plate_mode_rejects_missing_or_invalid_detector_confidence(self):
        for confidence in (None,True,float('nan'),-1,1.01):
            processor=LiveGateProcessor(CONFIG,tracker=lambda frame:[{
                'track_id':1,'box':[10,10,30,30],'plate_detection_confidence':confidence}],tracking_target='plate')
            with self.subTest(confidence=confidence),self.assertRaises(ValueError):
                processor.collect(np.zeros((100,100,3),dtype=np.uint8),stamp(0))

    def test_plate_observation_without_crossing_never_reads_number(self):
        read=Mock(side_effect=AssertionError('No crossing, no OCR'))
        processor=LiveGateProcessor(CONFIG,tracker=lambda frame:[{
            'track_id':1,'box':[10,10,30,30],'plate_detection_confidence':.8}],plate_reader=read,tracking_target='plate')
        for i in range(4):self.assertEqual(processor.process(np.zeros((100,100,3),dtype=np.uint8),stamp(i)),[])
        read.assert_not_called()

    def test_tracking_target_rejects_invalid_value(self):
        for value in ('car','',None,True):
            with self.assertRaises(ValueError):LiveGateProcessor(CONFIG,tracking_target=value)


    def test_missing_character_reasons_survive_live_session_and_report(self):
        from ai_vision.recognition.live_gate_clock import LiveGateClock
        from ai_vision.recognition.live_gate_session import LiveGateSession
        from ai_vision.recognition.run_live_gate import execute
        from ai_vision.recognition.live_gate_report import validate_report
        from ai_vision.recognition.live_gate_report_html import render_html
        reader = lambda crop: {"plate_number": "10-1557", "plate_type": "REVIEW",
                               "review_reasons": ["FORGED_REASON"]}
        processor = LiveGateProcessor(CONFIG, self.tracker, reader)
        capture = Mock()
        capture.read.side_effect = [(True, np.full((100, 100, 3), i, dtype=np.uint8)) for i in range(7)] + [(False, None)]
        clock = LiveGateClock(monotonic_start=0)
        session = LiveGateSession("TEST_GATE", "ENTRY", clock=clock)
        times = iter(i * .3 for i in range(7))
        report = execute(capture, processor, session, seconds=10, allow_source_end=True,
                         monotonic_reader=lambda: next(times), deadline_reader=lambda: 0)
        report["uses_synthetic_source"] = True
        self.assertEqual(report["results"][0]["review_reasons"], ["KOREAN_CHARACTER_NOT_FOUND"])
        self.assertEqual(report["results"][0]["decision"], "BLOCKED")
        self.assertEqual(report["request_attempts"], 0)
        checked = validate_report(report)
        self.assertIn("KOREAN_CHARACTER_NOT_FOUND", render_html(checked))

    def process_path(self, processor, path):
        passages = []
        for index, (seconds, x, y) in enumerate(path):
            frame = np.full((100, 100, 3), index, dtype=np.uint8)
            processor._tracker = lambda frame, x=x, y=y: [{"track_id": 7, "box": [x - 5, y - 5, x + 5, y + 5]}]
            current = FrameStamp(index, seconds, datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds))
            passages.extend(processor.process(frame, current))
        return passages

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

    def test_roi_exit_and_return_on_other_side_do_not_create_crossing(self):
        config = {**CONFIG, "roi": [.2, 0, .8, 0, .8, 1, .2, 1]}
        reader = Mock(side_effect=AssertionError("ROI 밖 이동은 통과가 아님"))
        processor = LiveGateProcessor(config, plate_reader=reader)
        path = [(0, 50, 20), (.1, 50, 20), (.2, 50, 20), (.3, 95, 20),
                (.5, 95, 80), (.8, 50, 80), (.9, 50, 80), (1, 50, 80)]
        self.assertEqual(self.process_path(processor, path), [])
        self.assertEqual(processor.statistics()["roi_resets"], 1)
        reader.assert_not_called()
        self.assertTrue(all(row["frame_index"] >= 5 for row in processor._buffers[7]))

    def test_position_jump_clears_previous_crops_before_new_track_segment(self):
        processor = LiveGateProcessor(CONFIG)
        path = [(0, 50, 80), (.3, 50, 80), (.6, 50, 80), (.61, 50, 20)]
        self.assertEqual(self.process_path(processor, path), [])
        self.assertEqual(processor.statistics()["speed_resets"], 1)
        self.assertEqual([row["frame_index"] for row in processor._buffers[7]], [3])
        self.assertEqual(processor._bytes, 10 * 10 * 3)

    def test_already_counted_id_not_reopened_by_roi_excursion(self):
        config = {**CONFIG, "roi": [.2, 0, .8, 0, .8, 1, .2, 1]}
        processor = LiveGateProcessor(config, self.tracker, lambda crop: {"plate_number": "", "plate_type": "NOT_DETECTED"})
        self.assertEqual(len(self.crossing(processor)), 1)
        processor._tracker = lambda frame: [{"track_id": 7, "box": [90, 10, 100, 30]}]
        self.assertEqual(processor.process(np.zeros((100, 100, 3), dtype=np.uint8), stamp(7)), [])
        self.assertIn(7, processor._counter.counted_ids)
        self.assertNotIn(7, processor._buffers)

    def test_expired_frame_crops_are_pruned_for_all_tracks_and_memory_released(self):
        rows = [{"track_id": track, "box": [20, 20, 40, 40]} for track in (1, 2)]
        processor = LiveGateProcessor(CONFIG, lambda frame: rows)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        processor.process(frame, stamp(0), minimum_frame_index=0)
        processor.process(frame, stamp(1), minimum_frame_index=0)
        processor.process(frame, stamp(2), minimum_frame_index=1)
        self.assertEqual(processor.statistics()["expired_history_crops"], 2)
        self.assertEqual(processor._bytes, 2 * 2 * 20 * 20 * 3)
        self.assertTrue(all(entry["frame_index"] >= 1 for entries in processor._buffers.values() for entry in entries))
        processor.close()
        self.assertEqual(processor._bytes, 0)

    def test_invalid_history_boundary_rejected_before_tracking(self):
        tracker = Mock(side_effect=AssertionError("invalid input"))
        processor = LiveGateProcessor(CONFIG, tracker)
        for value in (True, -1, .5, 1):
            with self.assertRaises(ValueError):
                processor.process(np.zeros((100, 100, 3), dtype=np.uint8), stamp(0), minimum_frame_index=value)
        tracker.assert_not_called()

    def test_duplicate_and_reversed_frames_preserve_previous_state(self):
        tracker = Mock(return_value=[{"track_id": 1, "box": [20, 20, 40, 40]}])
        processor = LiveGateProcessor(CONFIG, tracker)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        processor.process(frame, stamp(2))
        before = (processor.statistics(), processor._bytes, list(processor._buffers[1]))
        for invalid in (stamp(2), stamp(1), FrameStamp(3, .6, stamp(3).captured_at),
                        FrameStamp(3, .5, stamp(3).captured_at)):
            with self.assertRaises(ValueError):
                processor.process(frame, invalid)
        self.assertEqual(tracker.call_count, 1)
        self.assertEqual((processor.statistics(), processor._bytes, list(processor._buffers[1])), before)
        processor.process(frame, stamp(3))
        self.assertEqual(tracker.call_count, 2)

    def test_invalid_stamp_fields_never_reach_tracker(self):
        tracker = Mock()
        processor = LiveGateProcessor(CONFIG, tracker)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        invalid = [None, FrameStamp(True, 0, stamp(0).captured_at),
                   FrameStamp(-1, 0, stamp(0).captured_at),
                   FrameStamp(0, 0, datetime(2020, 1, 1))]
        invalid += [FrameStamp(0, seconds, stamp(0).captured_at)
                    for seconds in (True, -1, float("nan"), float("inf"), "0")]
        for value in invalid:
            with self.assertRaises(ValueError):
                processor.process(frame, value)
        tracker.assert_not_called()
        self.assertIsNone(processor._shape)
        self.assertEqual(processor.statistics()["frames"], 0)

    def test_history_boundary_cannot_move_backwards(self):
        tracker = Mock(return_value=[])
        processor = LiveGateProcessor(CONFIG, tracker)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        processor.process(frame, stamp(2), minimum_frame_index=2)
        with self.assertRaises(ValueError):
            processor.process(frame, stamp(3), minimum_frame_index=1)
        self.assertEqual(tracker.call_count, 1)
        processor.process(frame, stamp(3))
        self.assertEqual(processor._minimum_frame_index, 2)

    def test_long_gap_drops_old_crops_and_does_not_create_false_crossing(self):
        reader = Mock(side_effect=AssertionError("이전 차량 표본 재사용 금지"))
        processor = LiveGateProcessor(CONFIG, plate_reader=reader)
        path = [(0, 50, 20), (.3, 50, 20), (.6, 50, 20),
                (2, 50, 80), (2.3, 50, 80), (2.6, 50, 80)]
        self.assertEqual(self.process_path(processor, path), [])
        self.assertEqual(processor.statistics()["gap_resets"], 1)
        self.assertTrue(all(row["frame_index"] >= 3 for row in processor._buffers[7]))
        reader.assert_not_called()

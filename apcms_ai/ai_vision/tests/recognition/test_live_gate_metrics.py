# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_metrics.py

import copy
import unittest

from ai_vision.recognition.live_gate_metrics import LiveGateMetrics, validate_metrics, validate_processor_statistics


class LiveGateMetricsTests(unittest.TestCase):
    def test_stage_durations_errors_and_one_second_gap_boundary(self):
        metrics = LiveGateMetrics(iter((0, .25, 1, 1.75)).__next__)
        with metrics.measure("read"):
            pass
        with self.assertRaises(RuntimeError):
            with metrics.measure("process"):
                raise RuntimeError("processing failed")
        for elapsed in (0, 1, 2.5):
            metrics.record_frame(elapsed)
        value = metrics.summary()
        self.assertEqual(value["max_frame_gap_seconds"], 1.5)
        self.assertEqual(value["frame_gaps_over_one_second"], 1)
        self.assertEqual(value["stages"]["process"], {"calls": 1, "errors": 1, "total_seconds": .75, "max_seconds": .75})

    def test_empty_metrics_and_invalid_frame_times(self):
        metrics = LiveGateMetrics()
        self.assertEqual(validate_metrics(metrics.summary(), 0)["captured_frames"], 0)
        metrics.record_frame(1)
        for elapsed in (1, .5, True, float("nan"), -1):
            with self.assertRaises(ValueError):
                metrics.record_frame(elapsed)
        self.assertEqual(metrics.summary()["captured_frames"], 1)

    def test_corrupt_counts_and_durations_rejected(self):
        original = LiveGateMetrics().summary()
        variants = []
        for key, value in (("captured_frames", True), ("max_frame_gap_seconds", float("inf")),
                           ("frame_gaps_over_one_second", 1)):
            changed = copy.deepcopy(original)
            changed[key] = value
            variants.append(changed)
        for key, value in (("calls", True), ("errors", 1), ("total_seconds", -1), ("max_seconds", 2)):
            changed = copy.deepcopy(original)
            changed["stages"]["read"][key] = value
            variants.append(changed)
        for value in variants:
            with self.assertRaises(ValueError):
                validate_metrics(value, 0)

    def test_processor_observation_partition_and_ocr_limit(self):
        value = dict.fromkeys(("frames", "observations", "already_counted", "outside_roi", "eligible",
                               "gap_resets", "crossings", "ocr_calls", "peak_buffer_bytes"), 0)
        self.assertEqual(validate_processor_statistics(value, 0), value)
        value["observations"] = 1
        with self.assertRaises(ValueError):
            validate_processor_statistics(value, 0)
        value.update(frames=1, eligible=1, crossings=1, ocr_calls=4)
        with self.assertRaises(ValueError):
            validate_processor_statistics(value, 1)

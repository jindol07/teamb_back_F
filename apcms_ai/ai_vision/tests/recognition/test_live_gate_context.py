# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_context.py

import copy
import unittest

from ai_vision.recognition.live_gate_context import build_run_context, validate_run_context


CONFIG = {"tracker": "bytetrack", "line_y": .5, "line_x": [.1, .9], "roi": [0, 0, 1, 0, 1, 1, 0, 1]}


class LiveGateContextTests(unittest.TestCase):
    def test_snapshot_independent_and_hash_reproducible(self):
        source = copy.deepcopy(CONFIG)
        context = build_run_context(source, 2, 15)
        self.assertEqual(validate_run_context(context, False), context)
        other = {**CONFIG, "roi": list(map(float, CONFIG["roi"]))}
        self.assertEqual(build_run_context(other, 2, 15)["tracking_config_sha256"], context["tracking_config_sha256"])
        source["roi"][0] = .2
        self.assertEqual(context["tracking_config"]["roi"][0], 0)
        self.assertNotEqual(build_run_context(source, 2)["tracking_config_sha256"], context["tracking_config_sha256"])

    def test_changed_snapshot_digest_and_source_rejected(self):
        original = build_run_context(CONFIG, 0)
        for key, value in (("tracking_config_sha256", "0" * 64), ("source_type", "SYNTHETIC"), ("version", True)):
            changed = {**original, key: value}
            with self.assertRaises(ValueError):
                validate_run_context(changed, False)
        changed = copy.deepcopy(original)
        changed["tracking_config"]["line_y"] = .6
        with self.assertRaises(ValueError):
            validate_run_context(changed, False)

    def test_synthetic_has_no_camera_configuration(self):
        context = build_run_context(None, None, synthetic=True)
        self.assertIsNone(context["tracking_config_sha256"])
        self.assertEqual(validate_run_context(context, True), context)
        with self.assertRaises(ValueError):
            build_run_context(CONFIG, 0, synthetic=True)

    def test_invalid_limits_and_camera_index(self):
        for options in ({"seconds": True}, {"seconds": float("nan")}, {"seconds": 301},
                        {"max_frames": 0}, {"max_frames": True}):
            with self.assertRaises(ValueError):
                build_run_context(CONFIG, 0, **options)
        for index in (True, -1, 33, None):
            with self.assertRaises(ValueError):
                build_run_context(CONFIG, index)

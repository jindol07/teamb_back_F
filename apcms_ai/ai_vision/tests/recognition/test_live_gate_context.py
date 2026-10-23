# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_context.py

import copy
import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.single_vehicle_handoff import SingleVehicleHandoff, SingleVehicleHandoffReader
from ai_vision.tests.recognition.test_vehicle_response import sample_event

from ai_vision.recognition.live_gate_context import build_run_context, validate_run_context


CONFIG = {"tracker": "bytetrack", "line_y": .5, "line_x": [.1, .9], "roi": [0, 0, 1, 0, 1, 1, 0, 1]}


class SingleVehicleHandoffTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=RESULT_DIR)
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)/'handoff.json'
        self.now = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.source = SingleVehicleHandoff(self.path, 'gate_test', 'A', self.now)
        self.reader = SingleVehicleHandoffReader(self.path, clock=lambda: self.now)
        self.event = sample_event()

    def receipt(self, event, usage=70, **changes):
        return {'event_id': event['event_id'], 'event_type': 'VEHICLE_PASSAGE',
                'receipt_verified': True, 'request_attempted': True, 'state': 'APPLIED',
                'parking_usage_id': usage} | changes

    def enter(self):
        self.assertTrue(self.source.allow(self.event, self.now))
        self.source.record(self.event, self.receipt(self.event), self.now)

    def test_verified_entry_transfers_identity_and_same_usage_exit_clears_it(self):
        self.assertIsNone(self.reader.read())
        self.enter()
        self.assertEqual(self.reader.read()['parking_usage_id'], 70)
        event = self.event | {'direction': 'EXIT'}
        self.assertTrue(self.source.allow(event, self.now))
        self.source.record(event, self.receipt(event), self.now)
        self.assertIsNone(self.reader.read())

    def test_second_vehicle_blocks_without_overwriting_original_identity(self):
        self.enter()
        self.assertFalse(self.source.allow(self.event | {'plate_number': '12가3456'}, self.now))
        self.assertEqual(self.source.state['active']['plate_number'], '91소6408')
        self.assertIsNone(self.reader.read())

    def test_other_vehicle_exit_is_not_sent_or_cleared(self):
        self.enter()
        self.assertFalse(self.source.allow(self.event | {'direction': 'EXIT', 'plate_number': '12가3456'}, self.now))
        self.assertEqual(self.reader.read()['parking_usage_id'], 70)

    def test_wrong_usage_exit_does_not_clear_to_empty(self):
        self.enter()
        event = self.event | {'direction': 'EXIT'}
        self.source.record(event, self.receipt(event, usage=71), self.now)
        self.assertEqual(self.source.state['status'], 'BLOCKED')
        self.assertIsNone(self.reader.read())

    def test_unverified_or_held_entry_is_never_identity(self):
        for changes in ({'receipt_verified': False}, {'state': 'HELD'}, {'state': 'DELIVERY_UNKNOWN'},
                        {'parking_usage_id': None}, {'parking_usage_id': True}):
            self.source.record(self.event, self.receipt(self.event, **changes), self.now)
            self.assertIsNone(self.reader.read())

    def test_heartbeat_expiry_and_close_clear_identity(self):
        self.enter()
        self.now += timedelta(seconds=6)
        self.assertIsNone(self.reader.read())
        self.source.heartbeat(self.now)
        self.assertIsNotNone(self.reader.read())
        self.source.close(self.now)
        self.assertIsNone(self.reader.read())

    def test_old_file_is_not_overwritten_or_auto_reopened(self):
        self.enter()
        with self.assertRaises(FileExistsError):
            SingleVehicleHandoff(self.path, 'gate_other', 'A', self.now)
        self.assertEqual(self.reader.read()['parking_usage_id'], 70)

    def test_owner_change_and_corrupt_file_cannot_restore_identity(self):
        from ai_vision.recognition.local_io import write_json_atomic
        self.enter()
        self.reader.read()
        write_json_atomic(self.path, self.source.state | {'owner_session_id': 'gate_another'})
        self.assertIsNone(self.reader.read())
        self.path.write_text('{', encoding='utf-8')
        self.assertIsNone(self.reader.read())

    def test_explicit_future_timestamp_is_rejected(self):
        self.enter()
        self.now -= timedelta(seconds=2)
        self.assertIsNone(self.reader.read())


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

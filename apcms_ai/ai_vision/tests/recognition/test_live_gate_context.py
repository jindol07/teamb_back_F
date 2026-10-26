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

    def next_entry_without_empty_read(self):
        import uuid
        self.enter();self.reader.read()
        self.now+=timedelta(seconds=1)
        exited=self.event|{'direction':'EXIT','detected_at':self.now.isoformat()}
        self.source.record(exited,self.receipt(exited),self.now)
        self.now+=timedelta(seconds=1)
        entered=self.event|{'event_id':str(uuid.uuid4()),'detected_at':self.now.isoformat()}
        self.source.record(entered,self.receipt(entered,usage=71),self.now)
        return entered

    def test_two_cycles_finish_empty_and_retained_identity_is_not_reused(self):
        entered=self.next_entry_without_empty_read()
        self.assertEqual(self.reader.read()['parking_usage_id'],71)
        self.now+=timedelta(seconds=1)
        exited=entered|{'direction':'EXIT','detected_at':self.now.isoformat()}
        self.assertTrue(self.source.allow(exited,self.now))
        self.source.record(exited,self.receipt(exited,usage=71),self.now)
        self.assertIsNone(self.reader.read())
        self.assertEqual(self.reader.snapshot()['status'],'EMPTY')
        self.assertIsNone(self.reader.snapshot()['retained_identity'])
        self.assertEqual(self.reader.last_exit['parking_usage_id'],71)

    def test_next_entry_with_verified_previous_exit_does_not_require_reading_empty(self):
        entered=self.next_entry_without_empty_read()
        self.assertEqual(self.reader.read()['parking_usage_id'],71)
        self.assertEqual(self.reader.snapshot()['retained_identity']['event_id'],entered['event_id'])
        self.assertEqual(self.reader.last_exit['parking_usage_id'],70)

    def test_rollover_rejects_wrong_exit_reused_usage_or_entry_before_exit(self):
        from ai_vision.recognition.local_io import write_json_atomic
        self.next_entry_without_empty_read()
        original=copy.deepcopy(self.source.state)
        for kind in ('wrong_exit','same_usage','old_entry','same_event','blocked'):
            row=copy.deepcopy(original)
            if kind=='wrong_exit':row['last_exit']['parking_usage_id']=99
            if kind=='same_usage':row['active']['parking_usage_id']=70
            if kind=='old_entry':row['active']['detected_at']=self.event['detected_at']
            if kind=='same_event':row['active']['event_id']=self.event['event_id']
            if kind=='blocked':row['status']='BLOCKED'
            write_json_atomic(self.path,row)
            with self.subTest(kind=kind):
                self.assertIsNone(self.reader.read())
                self.assertEqual(self.reader.snapshot()['retained_identity']['parking_usage_id'],70)

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

    def test_heartbeat_expiry_and_close_hold_matching_but_retain_identity(self):
        self.enter()
        self.now += timedelta(seconds=6)
        self.assertIsNone(self.reader.read())
        self.source.heartbeat(self.now)
        self.assertIsNotNone(self.reader.read())
        self.source.close(self.now)
        self.assertIsNone(self.reader.read())
        self.assertEqual(self.source.state['active']['parking_usage_id'], 70)
        self.assertEqual(self.source.state['status'], 'ACTIVE')
        self.assertEqual(self.reader.snapshot()['retained_identity']['parking_usage_id'], 70)
        self.assertFalse(self.reader.snapshot()['usable_for_matching'])

    def test_long_observation_gap_retains_identity_and_live_same_owner_recovers(self):
        self.enter()
        self.reader.read()
        self.now += timedelta(minutes=30)
        self.assertIsNone(self.reader.read())
        self.assertEqual(self.reader.snapshot()['retained_identity']['parking_usage_id'], 70)
        self.source.heartbeat(self.now)
        self.assertEqual(self.reader.read()['parking_usage_id'], 70)

    def test_stopped_file_preserves_identity_even_for_new_reader_but_never_sends(self):
        self.enter()
        self.source.close(self.now)
        reader = SingleVehicleHandoffReader(self.path, clock=lambda: self.now)
        self.assertIsNone(reader.read())
        self.assertEqual(reader.status, 'SOURCE_STOPPED')
        self.assertEqual(reader.snapshot()['retained_identity']['parking_usage_id'], 70)

    def test_matching_exit_after_gap_clears_retained_identity(self):
        self.enter()
        self.reader.read()
        self.now += timedelta(seconds=20)
        self.assertIsNone(self.reader.read())
        event = self.event | {'direction': 'EXIT', 'detected_at': self.now.isoformat()}
        self.source.record(event, self.receipt(event), self.now)
        self.assertIsNone(self.reader.read())
        self.assertEqual(self.reader.status, 'EMPTY')
        self.assertIsNone(self.reader.snapshot()['retained_identity'])

    def test_wrong_exit_or_empty_state_cannot_discard_retained_identity(self):
        from ai_vision.recognition.local_io import write_json_atomic
        self.enter()
        self.reader.read()
        for exit_row in (None, {'parking_usage_id': 71, 'plate_number': '91소6408',
                               'event_id': self.event['event_id'], 'detected_at': self.now.isoformat()}):
            write_json_atomic(self.path, self.source.state | {'status': 'EMPTY', 'active': None, 'last_exit': exit_row})
            self.assertIsNone(self.reader.read())
            self.assertEqual(self.reader.snapshot()['retained_identity']['parking_usage_id'], 70)
            self.assertIsNone(self.reader.last_exit)

    def test_snapshot_is_copy_and_corruption_does_not_erase_known_entry(self):
        self.enter()
        self.reader.read()
        self.reader.snapshot()['retained_identity']['parking_usage_id'] = 999
        self.path.write_text('{', encoding='utf-8')
        self.assertIsNone(self.reader.read())
        self.assertEqual(self.reader.snapshot()['retained_identity']['parking_usage_id'], 70)

    def test_identity_cannot_be_replaced_before_matching_exit(self):
        from ai_vision.recognition.local_io import write_json_atomic
        self.enter()
        self.reader.read()
        row = self.source.state | {'active': self.source.state['active'] | {'parking_usage_id': 71}}
        write_json_atomic(self.path, row)
        self.assertIsNone(self.reader.read())
        self.assertEqual(self.reader.snapshot()['retained_identity']['parking_usage_id'], 70)

    def test_closed_source_cannot_restart_heartbeat_or_overwrite_entry(self):
        self.enter()
        self.source.close(self.now)
        original = self.path.read_bytes()
        self.source.heartbeat(self.now + timedelta(seconds=30))
        self.assertFalse(self.source.allow(self.event, self.now))
        with self.assertRaises(ValueError):
            self.source.record(self.event, self.receipt(self.event), self.now)
        self.source.close(self.now + timedelta(seconds=30))
        self.assertEqual(self.path.read_bytes(), original)

    def test_late_reader_can_clear_retained_identity_from_matching_exit_only(self):
        self.enter()
        self.reader.read()
        event = self.event | {'direction': 'EXIT'}
        self.source.record(event, self.receipt(event), self.now)
        self.now += timedelta(seconds=30)
        self.assertIsNone(self.reader.read())
        self.assertIsNone(self.reader.snapshot()['retained_identity'])
        self.assertIsNone(self.reader.last_exit)

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

# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_vehicle_space_tracker.py
"""차량·구획 상태, 비동기 관찰, 조회 사본 대조와 저장 영상 실행기를 함께 검사합니다."""

import hashlib
import json
import tempfile
import unittest
import threading
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from ai_vision.paths import RESULT_DIR
from ai_vision.parking.vehicle_space_tracker import VehicleSpaceTracker, VehicleSpaceObserver, review_match_context
from ai_vision.recognition.local_io import read_json, write_json_atomic
from ai_vision.parking.run_vehicle_space_tracking import run, main

CONFIG = {'image_width': 240, 'image_height': 140, 'spaces': [
    {'id': 'A-01', 'points': [[1, 1], [100, 1], [100, 130], [1, 130]]},
    {'id': 'A-02', 'points': [[120, 1], [230, 1], [230, 130], [120, 130]]}]}


def observation(index, track=1, box=(25, 25, 75, 90), plate='91소6408', kind='KOREAN_VALID'):
    return {'track_id': track, 'box': list(box), 'plate_sample': {
        'frame_index': index, 'video_seconds': index * .5, 'plate_number': plate, 'plate_type': kind,
        'plate_detection_confidence': .9}}


class EntryIdentityParkingTests(unittest.TestCase):

    def test_plate_nms_is_explicit_and_vehicle_tracking_keeps_previous_options(self):
        from ai_vision.parking.vehicle_space_tracker import create_vehicle_tracker
        for target in ('vehicle','plate'):
            model=Mock(names={0:'plate',1:'car'})
            model.track.return_value=[Mock(boxes=Mock(id=None))]
            with patch.dict('sys.modules',{'ultralytics':Mock(YOLO=Mock(return_value=model))}), \
                    patch('ai_vision.recognition.model_files.require_model_file'):
                _,track=create_vehicle_tracker(target)
                self.assertEqual(track(np.zeros((100,100,3),dtype=np.uint8)),[])
            options=model.track.call_args.kwargs
            if target=='plate':
                self.assertTrue(options['agnostic_nms'])
                self.assertEqual(options['iou'],.5)
            else:
                self.assertNotIn('agnostic_nms',options)
                self.assertNotIn('iou',options)


    def setUp(self):
        self.identity = {'owner_session_id': 'gate_test', 'event_id': 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
                         'parking_usage_id': 70, 'plate_number': '91소6408', 'confidence': .8}
        self.frame = np.zeros((140, 240, 3), dtype=np.uint8)
        self.track = Mock(return_value=[{'track_id': 1, 'box': [25,25,75,90], 'vehicle_detection_confidence': .9}])
        self.observer = VehicleSpaceObserver(CONFIG, tracker=self.track, handoff_reader=lambda: self.identity)
        self.addCleanup(self.observer.close)
        self.observer.prepare()

    def process(self, i, spaces=None):
        return self.observer.process(i, i*.5, self.frame, eligible_spaces={'A-01'} if spaces is None else spaces)

    def match(self):
        events=[]
        for i in range(5):
            events.extend(self.process(i)['events'])
        return events

    def test_single_stationary_target_uses_entry_identity_without_ocr(self):
        events = self.match()
        match = next(e for e in events if e['kind'] == 'LOCAL_SPACE_MATCH')
        self.assertEqual(match['identity_basis'], 'SINGLE_VEHICLE_ENTRY_HANDOFF')
        self.assertEqual(match['parking_usage_id'], 70)
        self.assertEqual(self.process(5)['progress'][0]['parking_usage_id'],70)
        self.assertEqual(self.observer.summary()['ocr_submitted'], 0)
        self.assertEqual(self.observer.tracker.states[1]['samples'], [])
        self.assertEqual(self.observer.tracker.states[1]['number'], '91소6408')

    def test_exit_or_source_loss_immediately_removes_current_identity(self):
        self.match()
        self.identity = None
        self.process(5)
        self.assertFalse(any(s['matched'] for s in self.observer.tracker.states.values()))

    def test_real_handoff_reader_observer_and_delivery_accept_second_entry_after_suppression(self):
        from datetime import datetime,timedelta,timezone
        from concurrent.futures import wait
        from ai_vision.recognition.single_vehicle_handoff import SingleVehicleHandoff,SingleVehicleHandoffReader
        from ai_vision.recognition.vehicle_delivery_flow import SpaceMatchDeliveryFlow
        from ai_vision.recognition.vehicle_live_candidate import create_space_match_candidate
        from ai_vision.tests.recognition.test_vehicle_response import sample_event
        folder=tempfile.TemporaryDirectory(dir=RESULT_DIR);self.addCleanup(folder.cleanup)
        now=datetime(2020,1,1,tzinfo=timezone.utc)
        source=SingleVehicleHandoff(Path(folder.name)/'entry.json','gate_test','A',now)
        reader=SingleVehicleHandoffReader(source.path,clock=lambda:now)
        self.observer._handoff_reader=reader.read
        event=sample_event()|{'detected_at':now.isoformat()}
        def receipt(event,usage):return {'event_id':event['event_id'],'event_type':'VEHICLE_PASSAGE',
            'state':'APPLIED','receipt_verified':True,'request_attempted':True,'parking_usage_id':usage}
        source.record(event,receipt(event,70),now)
        first=next(row for row in self.match() if row['kind']=='LOCAL_SPACE_MATCH')
        client=Mock(enabled=True)
        client.send.side_effect=lambda payload: {'event_id':payload['event_id'],'event_type':payload['event_type'],
            'state':'APPLIED','receipt_verified':True,'request_attempted':True,
            'parking_usage_id':payload['expected_parking_usage_id']}
        flow=SpaceMatchDeliveryFlow(client);self.addCleanup(flow.close,lambda:None)
        def candidate(row):return create_space_match_candidate(row|{'kind':'LIVE_SPACE_MATCH'},
            [{'track_id':row['track_id'],'space_id':row['space_id'],'plate_number':row['plate_number']}],'B',now.isoformat())
        flow.submit(candidate(first),'first',lambda:None)
        wait([flow._future]);flow.poll(lambda:None)
        self.assertEqual(flow.submit(candidate(first),'suppressed',lambda:None),'HELD_RELEASE_REQUIRED')
        now+=timedelta(seconds=1)
        exited=event|{'direction':'EXIT','detected_at':now.isoformat()}
        source.record(exited,receipt(exited,70),now)
        now+=timedelta(seconds=1)
        entered=event|{'event_id':'a47ac10b-58cc-4372-a567-0e02b2c3d479','detected_at':now.isoformat()}
        source.record(entered,receipt(entered,71),now)
        # B는 EMPTY를 한 번도 읽지 않은 상태에서 새 입차를 관찰합니다.
        outcome=self.process(5)
        self.assertFalse(any(row['kind']=='LOCAL_SPACE_MATCH' for row in outcome['events']))
        self.assertEqual(reader.last_exit['parking_usage_id'],70)
        self.assertTrue(flow.acknowledge_gate_exit('91소6408',70))
        events=[]
        for index in range(6,11):events.extend(self.process(index)['events'])
        second=next(row for row in events if row['kind']=='LOCAL_SPACE_MATCH')
        self.assertEqual(second['parking_usage_id'],71)
        self.assertEqual(self.process(11)['progress'][0]['parking_usage_id'],71)
        self.assertEqual(flow.submit(candidate(second),'second',lambda:None),'IN_FLIGHT')
        wait([flow._future]);flow.poll(lambda:None)
        self.assertEqual(client.send.call_count,2)
        self.assertEqual(flow.records[-1]['receipt']['parking_usage_id'],71)
        self.assertFalse(flow.acknowledge_gate_exit('91소6408',70))

    def test_new_entry_generation_requires_new_dwell(self):
        self.match()
        self.identity = self.identity | {'event_id': 'a47ac10b-58cc-4372-a567-0e02b2c3d479', 'parking_usage_id': 71}
        outcome = self.process(5)
        self.assertFalse(any(e['kind'] == 'LOCAL_SPACE_MATCH' for e in outcome['events']))
        self.assertIsNone(self.observer.tracker.states[1]['matched'])

    def test_multiple_targets_revoke_instead_of_guessing_identity(self):
        self.match()
        self.track.return_value += [{'track_id': 2, 'box': [135,25,180,90], 'vehicle_detection_confidence': .9}]
        self.process(5, {'A-01','A-02'})
        self.assertFalse(any(s['matched'] for s in self.observer.tracker.states.values()))

    def test_no_identity_never_accumulates_dwell_or_creates_match(self):
        self.identity = None
        for i in range(7):
            self.assertFalse(any(e['kind'] == 'LOCAL_SPACE_MATCH' for e in self.process(i)['events']))

    def test_missing_target_confidence_prevents_assignment(self):
        self.track.return_value[0].pop('vehicle_detection_confidence')
        self.assertFalse(any(e['kind'] == 'LOCAL_SPACE_MATCH' for e in self.match()))

    def test_multiple_occupied_spaces_hold_even_with_single_target(self):
        for i in range(6):
            self.assertFalse(any(e['kind'] == 'LOCAL_SPACE_MATCH' for e in self.process(i, {'A-01','A-02'})['events']))


class VerifiedEntryIdentityTests(unittest.TestCase):
    def setUp(self):
        from concurrent.futures import Future
        class ImmediateExecutor:
            def submit(self, fn, *args):
                result = Future()
                try: result.set_result(fn(*args))
                except Exception as error: result.set_exception(error)
                return result
            def shutdown(self, **kwargs): pass
        self.identity = {'owner_session_id':'entry_test', 'event_id':'f47ac10b-58cc-4372-a567-0e02b2c3d479',
                         'parking_usage_id':70, 'plate_number':'91소6408', 'confidence':.8}
        self.number = '91소6408'
        self.rows = [{'track_id':1,'box':[25,25,75,90],'plate_detection_confidence':.9}]
        self.frame = np.zeros((140,240,3),dtype=np.uint8)
        self.reader = Mock(side_effect=lambda crop:{'plate_number':self.number,
                           'plate_type':'KOREAN_VALID' if self.number else 'UNREADABLE'})
        self.observer = VehicleSpaceObserver(CONFIG, tracker=lambda frame:self.rows, plate_reader=self.reader,
            tracking_target='plate', ocr_execution='thread', handoff_reader=lambda:self.identity,
            verify_handoff_plate=True)
        self.observer.prepare();self.addCleanup(self.observer.close)
        self.observer._executor.shutdown(wait=True)
        self.observer._executor = ImmediateExecutor()

    def process(self,i,spaces=None):
        return self.observer.process(i,i*.5,self.frame,eligible_spaces={'A-01'} if spaces is None else spaces)

    def observe(self,start=0,end=9):
        return [e for i in range(start,end) for e in self.process(i)['events']]

    def test_b_ocr_must_agree_with_entry_before_candidate(self):
        from ai_vision.recognition.vehicle_live_candidate import create_space_match_candidate
        self.assertFalse(any(e['kind']=='LOCAL_SPACE_MATCH' for e in self.process(0)['events']))
        matches=[e for e in self.observe(1) if e['kind']=='LOCAL_SPACE_MATCH']
        self.assertEqual(len(matches),1)
        event=matches[0]
        self.assertEqual(event['identity_basis'],'ENTRY_AND_B_PLATE_OCR')
        self.assertEqual(event['parking_usage_id'],70)
        self.assertEqual(event['plate_consensus']['status'],'CONFIRMED')
        self.assertGreaterEqual(len(event['samples']),2)
        current=[{k:event[k] for k in ['track_id','space_id','plate_number']}]
        candidate=create_space_match_candidate({**event,'kind':'LIVE_SPACE_MATCH'},current,'PARKING_1','2020-01-01T00:00:00Z')
        self.assertEqual(candidate['expected_parking_usage_id'],70)
        self.assertEqual(candidate['identity_verification']['basis'],'ENTRY_AND_B_PLATE_OCR')
        self.assertEqual(self.observer.summary()['identity_status'],'VERIFIED')
        self.assertGreater(self.observer.summary()['ocr_submitted'],0)

    def test_other_b_plate_is_not_replaced_by_entry_number(self):
        self.number='12가3456'
        events=self.observe()
        self.assertFalse(any(e['kind']=='LOCAL_SPACE_MATCH' for e in events))
        self.assertTrue(any(e['kind']=='IDENTITY_MISMATCH' for e in events))
        self.assertEqual(self.observer.summary()['identity_status'],'PLATE_MISMATCH')
        self.assertTrue(all(s['matched'] is None for s in self.observer.tracker.states.values()))

    def test_unreadable_plate_never_uses_single_vehicle_assumption(self):
        self.number=''
        self.assertFalse(any(e['kind']=='LOCAL_SPACE_MATCH' for e in self.observe()))
        self.assertEqual(self.observer.summary()['identity_status'],'VERIFYING_PLATE')

    def test_old_entry_generation_ocr_is_discarded(self):
        self.process(0)
        self.identity={**self.identity,'event_id':'a47ac10b-58cc-4372-a567-0e02b2c3d479',
                       'parking_usage_id':71,'plate_number':'12가3456'}
        self.number='12가3456'
        self.process(1)
        self.assertEqual(self.observer.tracker.states[1]['samples'],[])
        matches=[e for e in self.observe(2,10) if e['kind']=='LOCAL_SPACE_MATCH']
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['parking_usage_id'],71)
        self.assertTrue(all(s['plate_number']=='12가3456' for s in matches[0]['samples']))

    def test_source_loss_and_multiple_targets_do_not_verify(self):
        self.observe()
        self.identity=None
        self.assertFalse(any(e['kind']=='LOCAL_SPACE_MATCH' for e in self.process(9)['events']))
        self.assertEqual(self.observer.summary()['identity_status'],'WAIT_ENTRY')
        self.assertFalse(self.observer.tracker.states)

    def test_multiple_targets_are_not_assigned_the_same_entry_number(self):
        self.rows += [{'track_id':2,'box':[130,25,180,90],'plate_detection_confidence':.9}]
        self.assertFalse(any(e['kind']=='LOCAL_SPACE_MATCH' for e in self.observe()))
        self.assertEqual(self.reader.call_count,0)
        self.assertEqual(self.observer.summary()['identity_status'],'AMBIGUOUS_OBSERVATION')

    def test_verification_requires_handoff_before_creating_worker(self):
        with self.assertRaises(ValueError):
            VehicleSpaceObserver(CONFIG,verify_handoff_plate=True)


class PlateConflictRecoveryTests(unittest.TestCase):
    def make_tracker(self):
        tracker = VehicleSpaceTracker(CONFIG, recover_plate_conflicts=True)
        for i in range(5):
            tracker.process(i, i*.5, [observation(i)])
        tracker.process(5, 2.5, [observation(5, plate='91스6408')])
        self.assertIsNone(tracker.states[1]['matched'])
        return tracker

    def test_only_five_fresh_consistent_frames_recover(self):
        tracker = self.make_tracker()
        for i in range(6, 10):
            tracker.process(i, i*.5, [observation(i)])
            self.assertIsNone(tracker.states[1]['matched'])
        events = tracker.process(10, 5, [observation(10)])
        self.assertEqual(tracker.states[1]['number'], '91소6408')
        self.assertTrue(any(e['kind'] == 'PLATE_RECOVERED' for e in events))

    def test_alternating_valid_numbers_never_recover(self):
        tracker = self.make_tracker()
        for i in range(6, 30):
            tracker.process(i, i*.5, [observation(i, plate='91스6408' if i%2 else '91소6408')])
            self.assertIsNone(tracker.states[1]['matched'])

    def test_invalid_frame_breaks_fresh_consistency(self):
        tracker = self.make_tracker()
        for i in range(6, 11):
            tracker.process(i, i*.5, [observation(i, kind='REVIEW' if i == 8 else 'KOREAN_VALID')])
        self.assertIsNone(tracker.states[1]['matched'])

    def test_five_fast_frames_do_not_meet_recovery_duration(self):
        tracker = self.make_tracker()
        for i in range(6, 11):
            row = observation(i)
            seconds = 2.5+(i-5)*.3
            row['plate_sample']['video_seconds'] = seconds
            tracker.process(i, seconds, [row])
        self.assertIsNone(tracker.states[1]['matched'])

    def test_occupancy_loss_discards_conflict_recovery_evidence(self):
        tracker = self.make_tracker()
        tracker.process(6, 3, [observation(6)], eligible_spaces=set())
        self.assertNotIn('conflict_after', tracker.states[1])
        self.assertEqual(tracker.states[1]['samples'], [])


class PlateMotionWindowTests(unittest.TestCase):
    def setUp(self):
        self.config = {'image_width': 1280, 'image_height': 1024, 'spaces': [
            {'id': 'A-01', 'points': [[1, 1], [600, 1], [600, 900], [1, 900]]},
            {'id': 'A-02', 'points': [[650, 1], [1250, 1], [1250, 900], [650, 900]]}]}
        self.tracker = VehicleSpaceTracker(self.config, motion_window_seconds=.1)
        for i in range(141):
            self.feed(i, i * .015)
        self.assertEqual(self.tracker.states[1]['matched'], 'A-01')

    def feed(self, index, seconds, dx=0, eligible=None):
        row = observation(index, box=(200+dx, 200, 290+dx, 230))
        row['plate_sample']['video_seconds'] = seconds
        if index % 20:
            row.pop('plate_sample')
        return self.tracker.process(index, seconds, [row], eligible_spaces=eligible)

    def test_pixel_jitter_at_fifteen_milliseconds_keeps_connection(self):
        for i in range(141, 180):
            events = self.feed(i, i * .015, i % 2)
            self.assertFalse(any(e['kind'] == 'MATCH_REVIEW' for e in events))
        self.assertEqual(self.tracker.states[1]['matched'], 'A-01')

    def test_sustained_motion_still_withdraws_connection(self):
        events = []
        for i in range(141, 151):
            events.extend(self.feed(i, i * .015, (i-140)*2))
        self.assertTrue(any(e.get('reason') == 'POSITION_MOVED' for e in events))
        self.assertIsNone(self.tracker.states[1]['matched'])

    def test_space_change_is_immediate(self):
        events = self.feed(141, 2.115, 500)
        self.assertTrue(any(e.get('reason') == 'SPACE_CHANGED' for e in events))
        self.assertIsNone(self.tracker.states[1]['matched'])

    def test_occupancy_loss_is_immediate(self):
        events = self.feed(141, 2.115, eligible=set())
        self.assertTrue(any(e.get('reason') == 'OCCUPANCY_NOT_CONTINUOUS' for e in events))
        self.assertEqual(self.tracker.states[1]['samples'], [])

    def test_absence_discards_connection_and_old_evidence(self):
        self.tracker.process(141, 2.115, [])
        self.feed(142, 2.13)
        self.assertIsNone(self.tracker.states[1]['matched'])
        self.assertEqual(self.tracker.states[1]['samples'], [])

    def test_input_size_defaults_and_explicit_override(self):
        from ai_vision.parking.vehicle_space_tracker import tracking_image_size
        self.assertEqual(tracking_image_size('plate'), 1280)
        self.assertEqual(tracking_image_size('vehicle'), 640)
        self.assertEqual(tracking_image_size('plate', 640), 640)
        self.assertEqual(tracking_image_size('plate', 960), 960)
        for value in (True, 640.0, 320, '1280'):
            with self.assertRaises(ValueError):
                tracking_image_size('plate', value)


class VehicleSpaceTrackerTests(unittest.TestCase):
    def test_occupancy_loss_revokes_plate_and_requires_fresh_dwell_and_samples(self):
        tracker = VehicleSpaceTracker(CONFIG)
        for i in range(5):
            tracker.process(i, i * .5, [observation(i)], eligible_spaces={'A-01'})
        old_since = tracker.states[1]['since']
        events = tracker.process(5, 2.5, [observation(5)], eligible_spaces=set())
        self.assertTrue(any(e['kind'] == 'MATCH_REVIEW' for e in events))
        self.assertIsNone(tracker.states[1]['matched'])
        self.assertEqual(tracker.states[1]['samples'], [])
        for i in range(6, 11):
            row = observation(i)
            row.pop('plate_sample')
            jobs = [{'track_id': 1, 'space_id': 'A-01', 'since': old_since,
                     'sample': observation(4)['plate_sample']}] if i == 6 else []
            tracker.process(i, i * .5, [row], completed_samples=jobs, eligible_spaces={'A-01'})
            self.assertIsNone(tracker.states[1]['matched'])
        events = []
        for i in (11, 12):
            events.extend(tracker.process(i, i * .5, [observation(i)], eligible_spaces={'A-01'}))
        self.assertEqual(len([e for e in events if e['kind'] == 'LOCAL_SPACE_MATCH']), 1)

    def test_unconfirmed_occupancy_cannot_accumulate_plate_evidence(self):
        tracker = VehicleSpaceTracker(CONFIG)
        for i in range(6):
            events = tracker.process(i, i * .5, [observation(i)], eligible_spaces=set())
            self.assertFalse(any(e['kind'] == 'LOCAL_SPACE_MATCH' for e in events))
        self.assertEqual(tracker.states[1]['count'], 0)
        self.assertEqual(tracker.states[1]['samples'], [])
        events = tracker.process(6, 3, [observation(6)], eligible_spaces={'A-01'})
        self.assertEqual(tracker.states[1]['since'], 3)
        self.assertFalse(any(e['kind'] == 'LOCAL_SPACE_MATCH' for e in events))

    def test_invalid_occupancy_gate_leaves_tracking_state_unchanged(self):
        tracker = VehicleSpaceTracker(CONFIG)
        tracker.process(0, 0, [observation(0)])
        before = deepcopy(tracker.states)
        with self.assertRaises(ValueError):
            tracker.process(1, .5, [observation(1)], eligible_spaces={'unknown'})
        self.assertEqual(tracker.states, before)
        self.assertEqual(tracker.last_frame, 0)

    def test_brief_disappearance_revokes_match_and_requires_new_plate_evidence(self):
        tracker = VehicleSpaceTracker(CONFIG)
        for i in range(5):
            tracker.process(i, i * .5, [observation(i)])
        self.assertEqual(tracker.states[1]['matched'], 'A-01')
        events = tracker.process(5, 2.5, [])
        self.assertTrue(any(e['kind'] == 'MATCH_REVIEW' for e in events))
        self.assertIsNone(tracker.states[1]['matched'])
        for i in range(6, 12):
            row = observation(i)
            row.pop('plate_sample')
            tracker.process(i, i * .5, [row])
        self.assertIsNone(tracker.states[1]['matched'])
        self.assertEqual(tracker.states[1]['samples'], [])
        events = []
        for i in (12, 13):
            events.extend(tracker.process(i, i * .5, [observation(i)]))
        self.assertEqual([e['space_id'] for e in events if e['kind'] == 'LOCAL_SPACE_MATCH'], ['A-01'])

    def test_ocr_from_before_brief_disappearance_is_not_reused(self):
        tracker = VehicleSpaceTracker(CONFIG)
        row = {'track_id': 1, 'box': [25, 25, 75, 90]}
        tracker.process(0, 0, [row])
        tracker.process(1, .5, [])
        old_job = {'track_id': 1, 'space_id': 'A-01', 'since': 0,
                   'sample': observation(0)['plate_sample']}
        tracker.process(2, 1, [row], completed_samples=[old_job])
        self.assertEqual(tracker.states[1]['since'], 1)
        self.assertEqual(tracker.states[1]['samples'], [])

    def test_dwell_plate_agreement_and_no_duplicate_match(self):
        tracker = VehicleSpaceTracker(CONFIG)
        events = []
        for i in range(9):
            events.extend(tracker.process(i, i * .5, [observation(i, plate='91소 6408' if i % 2 else '91소6408')]))
        matched = [e for e in events if e['kind'] == 'LOCAL_SPACE_MATCH']
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]['space_id'], 'A-01')
        self.assertEqual(matched[0]['plate_number'], '91소6408')
        self.assertGreaterEqual(matched[0]['video_seconds'], 2)
        self.assertFalse(matched[0]['http_enabled'])

    def test_pass_through_does_not_match(self):
        tracker = VehicleSpaceTracker(CONFIG)
        events = []
        for i in range(5):
            events.extend(tracker.process(i, i * .5, [observation(i, box=(20+i*8, 20, 60+i*8, 80))]))
        self.assertFalse(any(e['kind'] == 'LOCAL_SPACE_MATCH' for e in events))

    def test_lost_track_does_not_mean_departure_or_reuse_identity(self):
        tracker = VehicleSpaceTracker(CONFIG)
        for i in range(5):
            tracker.process(i, i * .5, [observation(i)])
        events = tracker.process(8, 4, [])
        self.assertEqual([e['kind'] for e in events], ['TRACK_LOST'])
        row = observation(9)
        row.pop('plate_sample')
        events = tracker.process(9, 4.5, [row])
        self.assertEqual([e['kind'] for e in events], ['ENTERED_SPACE'])

    def test_multiple_vehicles_and_boundary_are_not_assigned(self):
        for box in ((25, 25, 75, 90), (80, 25, 130, 90)):
            tracker = VehicleSpaceTracker(CONFIG)
            events = []
            for i in range(6):
                events.extend(tracker.process(i, i*.5, [observation(i, box=box), observation(i, track=2)]))
            self.assertFalse(any(e['kind'] == 'LOCAL_SPACE_MATCH' and e['track_id'] == 1 for e in events))

    def test_review_and_conflicting_numbers_never_match(self):
        for conflict in (False, True):
            tracker = VehicleSpaceTracker(CONFIG)
            events = []
            for i in range(6):
                row = observation(i, plate='91소6408' if i % 2 else '30고5957',
                                  kind='KOREAN_VALID' if conflict else 'REVIEW')
                events.extend(tracker.process(i, i*.5, [row]))
            self.assertFalse(any(e['kind'] == 'LOCAL_SPACE_MATCH' for e in events))

    def test_move_to_another_space_requires_fresh_dwell_and_plate(self):
        tracker = VehicleSpaceTracker(CONFIG)
        for i in range(5):
            tracker.process(i, i*.5, [observation(i)])
        events = []
        for i in range(5, 10):
            events.extend(tracker.process(i, i*.5, [observation(i, box=(145, 25, 195, 90))]))
        self.assertTrue(any(e['kind'] == 'MATCH_REVIEW' and e['space_id'] == 'A-01' for e in events))
        self.assertEqual([e['space_id'] for e in events if e['kind'] == 'LOCAL_SPACE_MATCH'], ['A-02'])

    def test_invalid_frame_and_sample_leave_state_unchanged(self):
        tracker = VehicleSpaceTracker(CONFIG)
        tracker.process(0, 0, [observation(0)])
        before = deepcopy(tracker.states)
        for index, seconds, rows in ((0, .5, [observation(1)]), (1, .5, [observation(0)]),
                                      (1, .5, [observation(1), observation(1)])):
            with self.subTest(index=index), self.assertRaises(ValueError):
                tracker.process(index, seconds, rows)
            self.assertEqual(tracker.states, before)

    def test_conflict_after_match_revokes_it(self):
        tracker = VehicleSpaceTracker(CONFIG)
        for i in range(5):
            tracker.process(i, i*.5, [observation(i)])
        events = tracker.process(5, 2.5, [observation(5, plate='30고5957')])
        self.assertTrue(any(e['kind'] == 'PLATE_CONFLICT' for e in events))
        self.assertIsNone(tracker.states[1]['matched'])

    def test_conflict_after_sample_buffer_is_full_remains_latched(self):
        tracker = VehicleSpaceTracker(CONFIG)
        for i in range(16):
            tracker.process(i, i*.5, [observation(i)])
        tracker.process(16, 8, [observation(16, plate='30고5957')])
        events = []
        for i in range(17, 33):
            events.extend(tracker.process(i, i*.5, [observation(i)]))
        self.assertFalse(any(e['kind'] == 'LOCAL_SPACE_MATCH' for e in events))
        self.assertLessEqual(len(tracker.states[1]['samples']), 12)

    def test_same_plate_on_two_tracks_revokes_both_matches(self):
        tracker = VehicleSpaceTracker(CONFIG)
        events = []
        for i in range(5):
            events.extend(tracker.process(i, i*.5, [observation(i),
                observation(i, track=2, box=(145, 25, 195, 90))]))
        self.assertTrue(any(e['kind'] == 'DUPLICATE_PLATE_REVIEW' for e in events))
        self.assertTrue(all(state['matched'] is None for state in tracker.states.values()))

    def test_missing_confidence_is_not_invented(self):
        tracker = VehicleSpaceTracker(CONFIG)
        row = observation(0)
        del row['plate_sample']['plate_detection_confidence']
        with self.assertRaises(ValueError):
            tracker.process(0, 0, [row])
        self.assertEqual(tracker.states, {})

    def test_ambiguity_invalidates_existing_match(self):
        tracker = VehicleSpaceTracker(CONFIG)
        for i in range(5):
            tracker.process(i, i*.5, [observation(i)])
        events = tracker.process(5, 2.5, [observation(5), observation(5, track=2)])
        self.assertTrue(any(e['kind'] == 'MATCH_REVIEW' for e in events))
        self.assertIsNone(tracker.states[1]['matched'])


class VehicleSpaceObserverTests(unittest.TestCase):
    def test_progress_reports_raw_ocr_wait_and_clears_after_disappearance(self):
        track = Mock(return_value=[{'track_id': 1, 'box': [25, 25, 75, 90]}])
        observer = self.observer(tracker=track, reader=Mock(return_value={
            'plate_number': '91±6408', 'plate_type': 'REVIEW'}))
        first = observer.process(0, 0, self.frame, eligible_spaces=set())
        self.assertEqual(first['progress'][0]['status'], 'WAIT_OCCUPANCY')
        for index in range(1, 7):
            result = observer.process(index, index * .5, self.frame, eligible_spaces={'A-01'})
            self.finish(observer)
        row = result['progress'][0]
        self.assertEqual(row['status'], 'WAIT_PLATE')
        self.assertEqual(row['plate_number'], '91±6408')
        self.assertEqual(row['plate_type'], 'REVIEW')
        self.assertEqual(row['space_id'], 'A-01')
        track.return_value = []
        self.assertEqual(observer.process(7, 3.5, self.frame, eligible_spaces={'A-01'})['progress'], [])

    def test_progress_marks_local_match_only_after_plate_agreement(self):
        observer = self.observer()
        for index in range(5):
            result = observer.process(index, index * .5, self.frame, eligible_spaces={'A-01'})
            self.finish(observer)
            self.assertEqual(result['progress'][0]['status'], 'LOCAL_MATCH' if index == 4 else 'WAIT_DWELL')
        self.assertEqual(result['progress'][0]['plate_number'], '91소6408')
        blocked = observer.process(5, 2.5, self.frame, eligible_spaces=set())
        self.assertEqual(blocked['progress'][0]['status'], 'WAIT_OCCUPANCY')
        self.assertEqual(blocked['progress'][0]['plate_number'], '')

    def setUp(self):
        self.frame = np.zeros((140, 240, 3), dtype=np.uint8)
        self.row = {'track_id': 1, 'box': [25, 25, 75, 90]}
        self.result = {'plate_number': '91소6408', 'plate_type': 'KOREAN_VALID',
                       'plate_detection_confidence': .9}

    def observer(self, reader=None, tracker=None, **kwargs):
        observer = VehicleSpaceObserver(CONFIG, tracker=tracker or Mock(return_value=[self.row]),
                                        plate_reader=reader or Mock(return_value=self.result), **kwargs)
        self.addCleanup(observer.close)
        observer.prepare()
        return observer

    def finish(self, observer):
        if observer._pending is not None:
            observer._pending.result(timeout=3)

    def test_brief_loss_does_not_restore_current_match_with_old_async_ocr(self):
        track = Mock(return_value=[self.row])
        reader = Mock(return_value=self.result)
        observer = self.observer(reader=reader, tracker=track)
        occupancy = Mock()
        occupancy.matching_spaces.return_value = {'A-01'}
        for index in range(5):
            observer.process(index, index * .5, self.frame)
            self.finish(observer)
        self.assertEqual(len(observer.current_matches(occupancy, 2)), 1)
        track.return_value = []
        outcome = observer.process(5, 2.5, self.frame)
        self.assertTrue(any(e['kind'] == 'MATCH_REVIEW' for e in outcome['events']))
        self.assertEqual(observer.current_matches(occupancy, 2.5), [])
        track.return_value = [self.row]
        reader.return_value = {'plate_number': '91±6408', 'plate_type': 'REVIEW'}
        for index in range(6, 13):
            observer.process(index, index * .5, self.frame)
            self.finish(observer)
            self.assertEqual(observer.current_matches(occupancy, index * .5), [])
        self.assertEqual(observer.tracker.states[1]['since'], 3)
        self.assertTrue(all(s['video_seconds'] >= 3 for s in observer.tracker.states[1]['samples']))

    def test_plate_conflict_keeps_async_ocr_running_until_fresh_recovery(self):
        row = dict(self.row, plate_detection_confidence=.9)
        reader = Mock(side_effect=[self.result,
            dict(self.result, plate_number='91스6408')] + [self.result]*14)
        observer = self.observer(reader=reader, tracker=Mock(return_value=[row]), tracking_target='plate')
        events = []
        for index in range(14):
            outcome = observer.process(index, index*.5, self.frame, eligible_spaces={'A-01'})
            events.extend(outcome['events'])
            self.finish(observer)
        self.assertTrue(any(e['kind'] == 'PLATE_CONFLICT' for e in events))
        self.assertTrue(any(e['kind'] == 'PLATE_RECOVERED' for e in events))
        self.assertEqual(observer.tracker.states[1]['number'], '91소6408')
        self.assertGreater(reader.call_count, 7)

    def test_ocr_wait_does_not_stop_tracking_or_queue_more_images(self):
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        def read(crop):
            started.set()
            if not release.wait(3):
                raise TimeoutError('시험 작업 해제 실패')
            finished.set()
            return self.result
        track = Mock(return_value=[self.row])
        observer = self.observer(reader=read, tracker=track)
        try:
            observer.process(0, 0, self.frame)
            self.assertTrue(started.wait(1))
            for index in range(1, 5):
                observer.process(index, index * .5, self.frame)
            self.assertFalse(finished.is_set())
            self.assertEqual(track.call_count, 5)
            self.assertEqual(observer.summary()['ocr_submitted'], 1)
            self.assertLessEqual(observer.summary()['peak_crop_bytes'], 8 * 1024 * 1024)
        finally:
            release.set()

    def test_late_results_keep_original_times_and_require_separate_samples(self):
        observer = self.observer()
        events = []
        for index in range(5):
            outcome = observer.process(index, index * .5, self.frame)
            events.extend(outcome['events'])
            self.finish(observer)
        state = observer.tracker.states[1]
        self.assertEqual(state['samples'][0]['frame_index'], 0)
        self.assertEqual(state['samples'][0]['video_seconds'], 0)
        self.assertEqual(state['samples'][1]['video_seconds'], .5)
        self.assertEqual(len([e for e in events if e['kind'] == 'LOCAL_SPACE_MATCH']), 1)
        occupancy = Mock()
        occupancy.matching_spaces.return_value = {'A-01'}
        self.assertEqual(observer.current_matches(occupancy, 2)[0]['plate_number'], '91소6408')
        occupancy.matching_spaces.return_value = set()
        self.assertEqual(observer.current_matches(occupancy, 2), [])

    def test_result_from_before_space_change_is_not_attached_to_new_space(self):
        release, started = threading.Event(), threading.Event()
        def read(crop):
            started.set()
            release.wait(3)
            return self.result
        rows = [[self.row], [{'track_id': 1, 'box': [145, 25, 195, 90]}]]
        track = Mock(side_effect=lambda frame: rows[0])
        observer = self.observer(reader=read, tracker=track)
        try:
            observer.process(0, 0, self.frame)
            self.assertTrue(started.wait(1))
            rows[0] = rows[1]
            observer.process(1, .5, self.frame)
            release.set()
            self.finish(observer)
            observer.process(2, 1, self.frame)
            self.assertEqual(observer.tracker.states[1]['space'], 'A-02')
            self.assertEqual(observer.tracker.states[1]['samples'], [])
        finally:
            release.set()

    def test_track_id_reused_after_gap_does_not_inherit_pending_ocr(self):
        release = threading.Event()
        def read(crop):
            release.wait(3)
            return self.result
        observer = self.observer(reader=read)
        try:
            observer.process(0, 0, self.frame)
            observer.process(1, 3, self.frame)
            release.set()
            self.finish(observer)
            observer.process(2, 3.5, self.frame)
            self.assertEqual(observer.tracker.states[1]['since'], 3)
            self.assertEqual(observer.tracker.states[1]['samples'], [])
        finally:
            release.set()

    def test_driver_buffer_is_copied_before_async_ocr(self):
        release = threading.Event()
        pixels = []
        def read(crop):
            release.wait(3)
            pixels.append(int(crop[0, 0, 0]))
            return self.result
        observer = self.observer(reader=read)
        try:
            self.frame[:] = 7
            observer.process(0, 0, self.frame)
            self.frame[:] = 99
            release.set()
            self.finish(observer)
            self.assertEqual(pixels, [7])
        finally:
            release.set()

    def test_oversize_image_is_not_submitted(self):
        reader = Mock(return_value=self.result)
        observer = self.observer(reader=reader, max_crop_bytes=1)
        observer.process(0, 0, self.frame)
        reader.assert_not_called()
        self.assertEqual(observer.summary()['oversize_crops'], 1)
        self.assertFalse(observer.summary()['pending_ocr'])

    def test_duplicate_time_does_not_add_observations_or_claim_current_match(self):
        observer = self.observer()
        observer.process(0, 0, self.frame)
        self.finish(observer)
        outcome = observer.process(1, 0, self.frame)
        self.assertEqual(outcome['observations'], [])
        self.assertEqual(observer.tracker.states[1]['count'], 1)
        self.assertEqual(observer.summary()['duplicate_time_frames'], 1)
        self.assertEqual(observer.current_matches(Mock(), 0), [])

    def test_worker_error_is_reported_and_observer_cannot_restart_after_close(self):
        observer = self.observer(reader=Mock(side_effect=RuntimeError('OCR 실패')))
        observer.process(0, 0, self.frame)
        with self.assertRaises(RuntimeError):
            self.finish(observer)
        with self.assertRaises(RuntimeError):
            observer.process(1, .5, self.frame)
        observer.close()
        with self.assertRaises(ValueError):
            observer.process(2, 1, self.frame)

    def test_late_error_is_not_hidden_during_close(self):
        observer = self.observer(reader=Mock(side_effect=RuntimeError('OCR 실패')))
        observer.process(0, 0, self.frame)
        with self.assertRaises(RuntimeError):
            self.finish(observer)
        with self.assertRaises(RuntimeError):
            observer.close()
        self.assertTrue(observer.summary()['closed'])

    def test_future_sample_is_rejected_without_changing_state(self):
        tracker = VehicleSpaceTracker(CONFIG)
        tracker.process(0, 0, [self.row])
        before = deepcopy(tracker.states)
        job = {'track_id': 1, 'space_id': 'A-01', 'since': 0, 'sample': observation(8)['plate_sample']}
        with self.assertRaises(ValueError):
            tracker.process(1, .5, [self.row], completed_samples=[job])
        self.assertEqual(tracker.states, before)


class MatchContextTests(unittest.TestCase):
    def setUp(self):
        # 실제 DB가 아닌 조회 응답 모양의 시험 자료입니다.
        self.report = {'record_type': 'LOCAL_VEHICLE_SPACE_TRACKING', 'status': 'COMPLETED',
                       'http_enabled': False, 'last_video_seconds': 3,
                       'current_matches': [{'track_id': 1, 'space_id': 'A-01', 'plate_number': '91소6408'}]}
        self.context = {'fetched_at': '2026-10-22T12:00:04+09:00',
                        'active_usages': [{'parkingUsageId': 70, 'vehicleNumber': '91소6408',
                                           'parkingSpaceId': None, 'entryAt': '2026-10-22T11:59:00', 'exitAt': None}],
                        'spaces': [{'parkingSpaceId': 16, 'spaceCode': '1F-A01',
                                    'spaceStatusCode': 'OCCUPIED', 'vehicleNumber': None}]}

    def review(self, start='2026-10-22T12:00:00+09:00'):
        return review_match_context(self.report, self.context, start)

    def test_matching_context_never_approves_reservation_or_sending(self):
        result = self.review()
        self.assertEqual(result['decision'], 'CONTEXT_MATCHED_LOCAL_ONLY')
        self.assertFalse(result['http_enabled'])
        self.assertFalse(result['reservation_checked'])
        self.assertFalse(result['camera_occupancy_checked'])
        self.assertEqual(result['items'][0]['parking_usage_id'], 70)

    def test_recording_time_must_be_explicit_and_have_timezone(self):
        for start in (None, '2026-10-22T12:00:00', 'invalid'):
            self.assertEqual(self.review(start)['reason'], 'OBSERVATION_TIME_UNKNOWN')

    def test_old_or_future_snapshot_is_held(self):
        for fetched in ('2026-10-22T12:00:02+09:00', '2026-10-22T12:00:19+09:00'):
            self.context['fetched_at'] = fetched
            self.assertEqual(self.review()['reason'], 'BOOT_CONTEXT_OUTSIDE_OBSERVATION_WINDOW')

    def test_missing_and_duplicate_active_usage(self):
        original = deepcopy(self.context['active_usages'])
        self.context['active_usages'] = []
        self.assertEqual(self.review()['items'][0]['reason'], 'ACTIVE_USAGE_MISSING_OR_AMBIGUOUS')
        self.context['active_usages'] = original * 2
        self.assertEqual(self.review()['reason'], 'AMBIGUOUS_BOOT_CONTEXT')

    def test_protected_or_empty_space_is_held(self):
        for status in ('AVAILABLE', 'RESERVED', 'DISABLED', None):
            self.context['spaces'][0]['spaceStatusCode'] = status
            self.assertEqual(self.review()['items'][0]['reason'], 'SPACE_NOT_OCCUPIED_OR_PROTECTED')

    def test_existing_links_and_other_vehicle_block_match(self):
        self.context['active_usages'][0]['parkingSpaceId'] = 17
        self.assertEqual(self.review()['items'][0]['reason'], 'VEHICLE_ALREADY_LINKED_ELSEWHERE')
        self.context['active_usages'][0]['parkingSpaceId'] = None
        self.context['active_usages'].append({'parkingUsageId': 71, 'vehicleNumber': '99하0001',
                                             'parkingSpaceId': 16, 'exitAt': None})
        self.assertEqual(self.review()['items'][0]['reason'], 'SPACE_LINKED_TO_OTHER_USAGE')
        self.context['active_usages'].pop()
        self.context['spaces'][0]['vehicleNumber'] = '99하0001'
        self.assertEqual(self.review()['items'][0]['reason'], 'SPACE_VEHICLE_CONFLICT')

    def test_failed_run_or_duplicate_matches_are_held(self):
        self.report['status'] = 'FAILED'
        self.assertEqual(self.review()['reason'], 'INVALID_OR_FAILED_LOCAL_RUN')
        self.report['status'] = 'COMPLETED'
        self.report['current_matches'] *= 2
        self.assertEqual(self.review()['reason'], 'AMBIGUOUS_MATCH_LIST')

    def test_missing_fields_and_entry_after_observation_are_held(self):
        self.context['active_usages'][0]['parkingSpaceId'] = True
        self.assertEqual(self.review()['items'][0]['reason'], 'INVALID_DATABASE_IDENTIFIERS')
        self.context['active_usages'][0]['parkingSpaceId'] = None
        self.context['active_usages'][0]['entryAt'] = '2026-10-22T12:00:05'
        self.assertEqual(self.review()['items'][0]['reason'], 'OBSERVED_BEFORE_ENTRY')

    def test_same_ocr_error_in_snapshot_does_not_validate_invalid_plate(self):
        for number in ('91±6408', '916408', '서울91소6408', '９１소６４０８'):
            with self.subTest(number=number):
                self.report['current_matches'][0]['plate_number'] = number
                self.context['active_usages'][0]['vehicleNumber'] = number
                self.assertEqual(self.review()['reason'], 'INVALID_MATCH_LIST')

    def test_plate_whitespace_is_normalized_without_mutating_source(self):
        self.report['current_matches'][0]['plate_number'] = '91소 6408'
        original = deepcopy(self.report)
        result = self.review()
        self.assertEqual(result['decision'], 'CONTEXT_MATCHED_LOCAL_ONLY')
        self.assertEqual(result['items'][0]['plate_number'], '91소6408')
        self.assertEqual(self.report, original)

    def test_normalized_duplicate_plates_are_held(self):
        self.report['current_matches'].append({'track_id': 2, 'space_id': 'A-02', 'plate_number': '91소 6408'})
        self.assertEqual(self.review()['reason'], 'AMBIGUOUS_MATCH_LIST')

    def test_aliases_cannot_assign_two_vehicles_to_one_database_space(self):
        self.report['current_matches'].append({'track_id': 2, 'space_id': '1F-A01', 'plate_number': '99하0001'})
        other = {**self.context['active_usages'][0], 'parkingUsageId': 71, 'vehicleNumber': '99하0001'}
        self.context['active_usages'].append(other)
        self.assertEqual(self.review()['reason'], 'AMBIGUOUS_MATCH_LIST')

    def test_active_lookup_requires_explicit_null_exit(self):
        for exit_at in ('', False, 0, '2026-10-22T11:59:30'):
            with self.subTest(exit_at=exit_at):
                self.context['active_usages'][0]['exitAt'] = exit_at
                self.assertEqual(self.review()['reason'], 'BOOT_ACTIVE_USAGES_INVALID')
        del self.context['active_usages'][0]['exitAt']
        self.assertEqual(self.review()['reason'], 'BOOT_ACTIVE_USAGES_INVALID')

    def test_duplicate_usage_identifier_with_different_plate_is_held(self):
        self.context['active_usages'].append({**self.context['active_usages'][0], 'vehicleNumber': '99하0001'})
        self.assertEqual(self.review()['reason'], 'AMBIGUOUS_BOOT_CONTEXT')

    def test_duplicate_database_space_identifier_is_held(self):
        self.context['spaces'].append({**self.context['spaces'][0], 'spaceCode': '1F-A02'})
        self.assertEqual(self.review()['reason'], 'AMBIGUOUS_BOOT_CONTEXT')

    def test_duplicate_database_space_code_is_held(self):
        self.context['spaces'].append({**self.context['spaces'][0], 'parkingSpaceId': 17})
        self.assertEqual(self.review()['reason'], 'AMBIGUOUS_BOOT_CONTEXT')

    def test_unmapped_space_is_held_without_exception(self):
        self.report['current_matches'][0]['space_id'] = 'A-99'
        self.assertEqual(self.review()['items'][0]['reason'], 'SPACE_MAPPING_OR_PLATE_INVALID')


class RunVehicleSpaceTrackingTests(unittest.TestCase):
    def setUp(self):
        root = RESULT_DIR / 'test_tmp'
        root.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source.mp4'
        self.source.touch()
        self.config = self.root / 'spaces.json'
        write_json_atomic(self.config, CONFIG)
        self.capture = Mock()
        self.capture.get.side_effect = [2.0, 7.0]
        frame = np.zeros((140, 240, 3), dtype=np.uint8)
        self.capture.read.side_effect = [(True, frame.copy()) for _ in range(7)] + [(False, None)]
        self.tracker = Mock(return_value=[{'track_id': 1, 'box': [25, 25, 75, 90]}])
        self.reader = Mock(return_value={'plate_number': '91소6408', 'plate_type': 'KOREAN_VALID',
                                        'plate_detection_confidence': .9})

    def test_no_match_uses_ocr_or_dwell_from_before_continuous_occupancy(self):
        occupied = np.zeros((140, 240, 3), dtype=np.uint8)
        occupied[10:120, 10:95] = 255
        self.capture.get.side_effect = [2.0, 17.0]
        self.capture.read.side_effect = [(True, np.zeros_like(occupied))] * 5 + [(True, occupied)] * 12 + [(False, None)]
        output = self.root / 'occupancy_order'
        with patch('cv2.VideoCapture', return_value=self.capture):
            run(self.source, self.config, output, tracker=self.tracker,
                plate_reader=self.reader, reference_path=self.reference_image())
        events = [json.loads(line) for line in (output / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        matches = [event for event in events if event['kind'] == 'LOCAL_SPACE_MATCH']
        self.assertTrue(matches)
        self.assertTrue(all(event['local_occupancy_confirmed'] for event in matches))
        self.assertGreaterEqual(matches[0]['video_seconds'], 6.5)

    def test_observations_and_match_use_video_time_without_sending(self):
        output = self.root / 'result'
        with patch('cv2.VideoCapture', return_value=self.capture):
            report = run(self.source, self.config, output, tracker=self.tracker, plate_reader=self.reader)
        events = [json.loads(line) for line in (output / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        matches = [e for e in events if e['kind'] == 'LOCAL_SPACE_MATCH']
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['video_seconds'], 2)
        self.assertEqual(report['status'], 'COMPLETED')
        self.assertEqual(report['frames'], 7)
        self.assertFalse(report['http_enabled'])
        self.assertFalse(report['reservation_checked'])
        self.assertEqual(self.reader.call_args.args[0].shape, (65, 50, 3))
        self.capture.release.assert_called_once()

    def test_resolution_mismatch_saves_failed_report_and_releases_camera(self):
        output = self.root / 'wrong_resolution'
        self.capture.read.side_effect = [(True, np.zeros((100, 100, 3), dtype=np.uint8))]
        with patch('cv2.VideoCapture', return_value=self.capture), self.assertRaises(ValueError):
            run(self.source, self.config, output, tracker=self.tracker, plate_reader=self.reader)
        self.assertEqual(read_json(output / 'summary.json')['status'], 'FAILED')
        self.reader.assert_not_called()
        self.capture.release.assert_called_once()

    def test_hidden_vehicle_is_not_a_current_match_at_end(self):
        self.tracker.side_effect = [self.tracker.return_value for _ in range(6)] + [[]]
        with patch('cv2.VideoCapture', return_value=self.capture):
            report = run(self.source, self.config, self.root / 'hidden',
                         tracker=self.tracker, plate_reader=self.reader)
        self.assertEqual(report['current_matches'], [])
        self.assertEqual(report['analysis_outcome'], 'NO_CURRENT_MATCH')

    def test_no_vehicle_is_reported_separately_from_execution_completion(self):
        self.tracker.return_value = []
        with patch('cv2.VideoCapture', return_value=self.capture):
            report = run(self.source, self.config, self.root / 'no_vehicle', tracker=self.tracker,
                         plate_reader=self.reader)
        self.assertEqual(report['status'], 'COMPLETED')
        self.assertEqual(report['analysis_outcome'], 'NO_VEHICLE_OBSERVATIONS')
        self.assertEqual(report['vehicle_observation_frames'], 0)
        self.assertEqual(report['ocr_requests'], 0)
        self.reader.assert_not_called()

    def capture_metadata(self, times):
        # 모의 카메라는 인코딩 2 FPS이지만 실제 수집 간격은 별도 자료로 전달합니다.
        metadata = {'status': 'COMPLETED', 'http_enabled': False, 'frame_times_seconds': times,
                    'captured_frames': len(times), 'recording_started_at': '2026-10-22T12:00:00+09:00',
                    'video_sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()}
        path = self.root / 'capture.json'
        write_json_atomic(path, metadata)
        return path, metadata

    def test_capture_times_prevent_false_dwell_from_encoded_fps(self):
        path, metadata = self.capture_metadata([i * .1 for i in range(7)])
        with patch('cv2.VideoCapture', return_value=self.capture):
            report = run(self.source, self.config, self.root / 'capture_time', tracker=self.tracker,
                         plate_reader=self.reader, capture_report=path)
        self.assertEqual(report['current_matches'], [])
        self.assertEqual(report['time_basis'], 'CAPTURE_MONOTONIC')
        self.assertAlmostEqual(report['last_video_seconds'], .6)
        self.assertEqual(report['recording_started_at'], metadata['recording_started_at'])

    def test_invalid_capture_metadata_is_rejected_before_video_open(self):
        path, metadata = self.capture_metadata([0, .5, 1, 1.5, 2, 2.5, 3])
        for changes in ({'video_sha256': 'wrong'}, {'frame_times_seconds': [0, 0]},
                        {'status': 'FAILED'}, {'recording_started_at': '2026-10-22T12:00:00'}):
            write_json_atomic(path, {**metadata, **changes})
            with patch('cv2.VideoCapture') as opened, self.assertRaises(ValueError):
                run(self.source, self.config, self.root / 'invalid_capture', capture_report=path)
            opened.assert_not_called()

    def test_capture_frame_count_mismatch_releases_camera(self):
        path, metadata = self.capture_metadata([0, .5])
        with patch('cv2.VideoCapture', return_value=self.capture), self.assertRaises(ValueError):
            run(self.source, self.config, self.root / 'wrong_count', capture_report=path)
        self.capture.release.assert_called_once()

    def test_equal_capture_times_do_not_add_consensus_or_dwell_samples(self):
        path, _ = self.capture_metadata([0, 0, .5, 1, 1.5, 2, 2.5])
        with patch('cv2.VideoCapture', return_value=self.capture):
            report = run(self.source, self.config, self.root / 'duplicate_times', tracker=self.tracker,
                         plate_reader=self.reader, capture_report=path)
        self.assertEqual(report['frames'], 7)
        self.assertEqual(report['skipped_duplicate_time_frames'], 1)
        self.assertEqual(self.tracker.call_count, 6)
        self.assertEqual(report['last_video_seconds'], 2.5)

    def test_recorded_file_and_capture_times_can_be_analyzed_together(self):
        from ai_vision.recognition.record_gate_video import record
        capture = Mock()
        capture.get.return_value = 30  # 인코딩 FPS와 실제 수집 2 FPS를 의도적으로 다르게 만듭니다.
        capture.read.return_value = (True, np.zeros((140, 240, 3), dtype=np.uint8))
        with patch('ai_vision.recognition.record_gate_video.open_camera', return_value=capture), \
                patch('ai_vision.recognition.record_gate_video.monotonic',
                      side_effect=[0, 0, .5, 1, 1.5, 2, 2.5, 3, 3.5, 3.5]):
            recorded = record(1, 3.5, self.root / 'recorded', preview=False, config_path=self.config)
        source = Path(recorded['video'])
        report = run(source, self.config, self.root / 'recorded_analysis', tracker=self.tracker,
                     plate_reader=self.reader, capture_report=source.with_suffix('.json'))
        self.assertEqual(report['frames'], 7)
        self.assertEqual(report['last_video_seconds'], 3)
        self.assertEqual(len(report['current_matches']), 1)
        self.assertEqual(report['time_basis'], 'CAPTURE_MONOTONIC')

    def test_remote_reader_is_reused_without_local_ocr(self):
        with patch('cv2.VideoCapture', return_value=self.capture), \
                patch('ai_vision.recognition.remote_plate_reader.RemotePlateReader') as remote:
            remote.return_value.read = self.reader
            report = run(self.source, self.config, self.root / 'remote', tracker=self.tracker,
                         vision_api_url='http://127.0.0.1:18000')
        remote.assert_called_once_with('http://127.0.0.1:18000')
        self.assertEqual(report['recognition_mode'], 'REMOTE_API')
        self.assertTrue(report['remote_recognition_enabled'])
        self.assertFalse(report['http_enabled'])  # Boot 전송은 비활성이고 원격 OCR만 사용합니다.
        self.assertEqual(len(report['current_matches']), 1)

    def test_remote_failure_saves_failed_report_and_releases_capture(self):
        from ai_vision.recognition.remote_plate_reader import RemotePlateError
        with patch('cv2.VideoCapture', return_value=self.capture), \
                patch('ai_vision.recognition.remote_plate_reader.RemotePlateReader') as remote:
            remote.return_value.read.side_effect = RemotePlateError('REMOTE_TIMEOUT')
            with self.assertRaises(RemotePlateError):
                run(self.source, self.config, self.root / 'timeout', tracker=self.tracker,
                    vision_api_url='http://127.0.0.1:18000')
        saved = read_json(self.root / 'timeout/summary.json')
        self.assertEqual(saved['status'], 'FAILED')
        self.assertEqual(saved['current_matches'], [])
        self.capture.release.assert_called_once()

    def test_invalid_remote_configuration_fails_before_opening_video(self):
        with patch('cv2.VideoCapture') as capture:
            for url in ('invalid', 'http://user:password@example.com'):
                with self.assertRaises(ValueError):
                    run(self.source, self.config, self.root / 'invalid', vision_api_url=url)
            with self.assertRaises(ValueError):
                run(self.source, self.config, self.root / 'invalid', plate_reader=self.reader,
                    vision_api_url='http://127.0.0.1:18000')
        capture.assert_not_called()

    def test_context_review_is_saved_without_http(self):
        fixture = MatchContextTests()
        fixture.setUp()
        context_path = self.root / 'boot_context.json'
        write_json_atomic(context_path, fixture.context)
        output = self.root / 'context_result'
        with patch('cv2.VideoCapture', return_value=self.capture):
            report = run(self.source, self.config, output, tracker=self.tracker, plate_reader=self.reader,
                         boot_context=context_path, recording_started_at='2026-10-22T12:00:00+09:00')
        saved = read_json(output / 'summary.json')
        self.assertEqual(saved['context_review']['decision'], 'CONTEXT_MATCHED_LOCAL_ONLY')
        self.assertFalse(report['http_enabled'])
        self.assertFalse(saved['context_review']['reservation_checked'])

    def test_empty_video_does_not_report_success(self):
        self.capture.read.side_effect = [(False, None)]
        with patch('cv2.VideoCapture', return_value=self.capture), self.assertRaises(ValueError):
            run(self.source, self.config, self.root / 'empty', tracker=self.tracker, plate_reader=self.reader)
        self.capture.release.assert_called_once()

    def test_existing_output_is_preserved_and_invalid_length_is_rejected(self):
        output = self.root / 'old'
        output.mkdir()
        for seconds in (False, 0, float('nan'), 301):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                run(self.source, self.config, self.root / 'new', seconds)
        with self.assertRaises(ValueError):
            run(self.source, self.config, output)

    def test_cli_passes_paths_and_limit(self):
        with patch('ai_vision.parking.run_vehicle_space_tracking.run', return_value={'status': 'COMPLETED'}) as execute:
            self.assertEqual(main(['--source', 'source.mp4', '--config', 'spaces.json', '--output-dir', 'new',
                                   '--max-seconds', '30']), 0)
        self.assertEqual(execute.call_args.args[-1], 30)

    def test_real_video_file_and_injected_observations_complete_without_model(self):
        import cv2
        source = self.root / 'generated.avi'
        writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 2, (240, 140))
        self.assertTrue(writer.isOpened())
        try:
            for _ in range(7):
                writer.write(np.zeros((140, 240, 3), dtype=np.uint8))
        finally:
            writer.release()
        report = run(source, self.config, self.root / 'real_file', tracker=self.tracker, plate_reader=self.reader)
        self.assertEqual(report['status'], 'COMPLETED')
        self.assertEqual(report['frames'], 7)

    def test_truncated_read_is_not_successful_eof(self):
        self.capture.read.side_effect = [(True, np.zeros((140, 240, 3), dtype=np.uint8)), (False, None)]
        with patch('cv2.VideoCapture', return_value=self.capture), self.assertRaises(OSError):
            run(self.source, self.config, self.root / 'truncated', tracker=self.tracker, plate_reader=self.reader)
        self.assertEqual(read_json(self.root / 'truncated/summary.json')['status'], 'FAILED')

    def test_failure_after_match_does_not_publish_current_matches(self):
        self.capture.get.side_effect = [2.0, 8.0]
        self.capture.read.side_effect = [(True, np.zeros((140, 240, 3), dtype=np.uint8))] * 6 + [(False, None)]
        output = self.root / 'failed_after_match'
        with patch('cv2.VideoCapture', return_value=self.capture), self.assertRaises(OSError):
            run(self.source, self.config, output, tracker=self.tracker, plate_reader=self.reader)
        report = read_json(output / 'summary.json')
        self.assertEqual(report['status'], 'FAILED')
        self.assertEqual(report['current_matches'], [])

    def reference_image(self):
        import cv2
        reference = self.root / 'empty_reference.png'
        reference.write_bytes(cv2.imencode('.png', np.zeros((140, 240, 3), dtype=np.uint8))[1].tobytes())
        return reference

    def test_same_video_confirmed_occupancy_and_plate_candidate_are_joined_without_events(self):
        occupied = np.zeros((140, 240, 3), dtype=np.uint8)
        occupied[10:120, 10:95] = 255
        self.capture.get.side_effect = [2.0, 11.0]
        self.capture.read.side_effect = [(True, occupied.copy())] * 11 + [(False, None)]
        with patch('cv2.VideoCapture', return_value=self.capture), \
                patch('ai_vision.parking.parking_processor.create_occupancy_event',
                      side_effect=AssertionError('저장 영상에서 전송 이벤트 생성 금지')):
            report = run(self.source, self.config, self.root / 'joined', tracker=self.tracker,
                         plate_reader=self.reader, reference_path=self.reference_image())
        self.assertEqual(report['analysis_outcome'], 'LOCAL_MATCH_WITH_OCCUPANCY')
        self.assertEqual(report['current_matches'][0]['plate_number'], '91소6408')
        self.assertEqual(report['local_occupancy']['matching_space_ids'], ['A-01'])
        self.assertTrue(report['local_occupancy_checked'])
        self.assertFalse(report['http_enabled'])
        self.assertFalse(report['reservation_checked'])
        self.assertFalse(report['physical_occupancy_checked'])
        rows = [json.loads(r) for r in (self.root / 'joined/observations.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows[-1]['local_occupancy']['matching_space_ids'], ['A-01'])

    def test_empty_occupancy_holds_even_an_agreed_plate(self):
        with patch('cv2.VideoCapture', return_value=self.capture):
            report = run(self.source, self.config, self.root / 'held', tracker=self.tracker,
                         plate_reader=self.reader, reference_path=self.reference_image())
        self.assertEqual(report['current_matches'], [])
        self.assertEqual(report['held_matches'], [])
        self.assertEqual(report['analysis_outcome'], 'NO_CURRENT_MATCH')

    def test_first_empty_observation_holds_old_occupied_confirmation(self):
        occupied = np.zeros((140, 240, 3), dtype=np.uint8)
        occupied[10:120, 10:95] = 255
        self.capture.read.side_effect = [(True, occupied.copy())] * 6 + [
            (True, np.zeros_like(occupied)), (False, None)]
        with patch('cv2.VideoCapture', return_value=self.capture):
            report = run(self.source, self.config, self.root / 'left', tracker=self.tracker,
                         plate_reader=self.reader, reference_path=self.reference_image())
        self.assertEqual(report['current_matches'], [])
        self.assertEqual(report['local_occupancy']['matching_space_ids'], [])
        self.assertEqual(report['local_occupancy']['occupancy']['occupied_count'], 1)
        self.assertEqual(report['held_matches'], [])

    def test_reference_resolution_and_missing_reference_fail_before_opening_video(self):
        import cv2
        reference = self.root / 'wrong_size.png'
        reference.write_bytes(cv2.imencode('.png', np.zeros((80, 80, 3), dtype=np.uint8))[1].tobytes())
        with patch('cv2.VideoCapture') as capture:
            with self.assertRaises(ValueError):
                run(self.source, self.config, self.root / 'bad_reference', reference_path=reference)
            with self.assertRaises(ValueError):
                run(self.source, self.config, self.root / 'missing_reference', occupancy_detector=Mock())
        capture.assert_not_called()

    def test_occupancy_failure_clears_matches_and_releases_video(self):
        output = self.root / 'bad_occupancy'
        with patch('cv2.VideoCapture', return_value=self.capture), self.assertRaises(RuntimeError):
            run(self.source, self.config, output, tracker=self.tracker, plate_reader=self.reader,
                reference_path=self.reference_image(), occupancy_detector=Mock(side_effect=RuntimeError('failed')))
        saved = read_json(output / 'summary.json')
        self.assertEqual(saved['status'], 'FAILED')
        self.assertEqual(saved['current_matches'], [])
        self.assertFalse(saved['local_occupancy_checked'])
        self.capture.release.assert_called_once()

    def test_cli_passes_optional_reference(self):
        with patch('ai_vision.parking.run_vehicle_space_tracking.run', return_value={}) as execute:
            self.assertEqual(main(['--source', 'a.mp4', '--config', 'spaces.json',
                                   '--output-dir', 'out', '--reference', 'empty.png']), 0)
        self.assertEqual(execute.call_args.kwargs['reference_path'], Path('empty.png'))

    def test_real_saved_video_joins_local_evidence_without_camera_or_network(self):
        import cv2
        source = self.root / 'occupied.mp4'
        writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), 2, (240, 140))
        self.assertTrue(writer.isOpened())
        try:
            frame = np.zeros((140, 240, 3), dtype=np.uint8)
            frame[10:120, 10:95] = 255
            for _ in range(11):
                writer.write(frame)
        finally:
            writer.release()
        report = run(source, self.config, self.root / 'real_joined', tracker=self.tracker,
                     plate_reader=self.reader, reference_path=self.reference_image())
        self.assertEqual(report['analysis_outcome'], 'LOCAL_MATCH_WITH_OCCUPANCY')
        self.assertEqual(report['frames'], 11)
        self.assertEqual(report['recognition_mode'], 'INJECTED')
        self.assertFalse(report['http_enabled'])

    def test_context_review_requires_active_entry_even_with_local_occupancy(self):
        fixture = MatchContextTests()
        fixture.setUp()
        fixture.context['fetched_at'] = '2026-10-22T12:00:06+09:00'
        fixture.context['active_usages'] = []
        context = self.root / 'no_entry_context.json'
        write_json_atomic(context, fixture.context)
        occupied = np.zeros((140, 240, 3), dtype=np.uint8)
        occupied[10:120, 10:95] = 255
        self.capture.get.side_effect = [2.0, 11.0]
        self.capture.read.side_effect = [(True, occupied)] * 11 + [(False, None)]
        with patch('cv2.VideoCapture', return_value=self.capture):
            report = run(self.source, self.config, self.root / 'no_entry', tracker=self.tracker,
                         plate_reader=self.reader, reference_path=self.reference_image(),
                         boot_context=context, recording_started_at='2026-10-22T12:00:00+09:00')
        self.assertEqual(report['analysis_outcome'], 'LOCAL_MATCH_WITH_OCCUPANCY')
        self.assertEqual(report['context_review']['decision'], 'HELD')
        self.assertEqual(report['context_review']['items'][0]['reason'], 'ACTIVE_USAGE_MISSING_OR_AMBIGUOUS')
        self.assertFalse(report['entry_checked'])
        self.assertFalse(report['reservation_checked'])

    def test_local_occupancy_and_entry_context_are_reviewed_without_reservation_claim(self):
        fixture = MatchContextTests()
        fixture.setUp()
        fixture.context['fetched_at'] = '2026-10-22T12:00:06+09:00'
        context = self.root / 'entry_context.json'
        write_json_atomic(context, fixture.context)
        occupied = np.zeros((140, 240, 3), dtype=np.uint8)
        occupied[10:120, 10:95] = 255
        self.capture.get.side_effect = [2.0, 11.0]
        self.capture.read.side_effect = [(True, occupied)] * 11 + [(False, None)]
        with patch('cv2.VideoCapture', return_value=self.capture):
            report = run(self.source, self.config, self.root / 'with_entry', tracker=self.tracker,
                         plate_reader=self.reader, reference_path=self.reference_image(),
                         boot_context=context, recording_started_at='2026-10-22T12:00:00+09:00')
        self.assertEqual(report['analysis_outcome'], 'LOCAL_MATCH_WITH_OCCUPANCY')
        self.assertEqual(report['context_review']['decision'], 'CONTEXT_MATCHED_LOCAL_ONLY')
        self.assertFalse(report['context_review']['reservation_checked'])
        self.assertFalse(report['http_enabled'])


class PlatePositionTrackingTests(unittest.TestCase):
    def test_plate_observer_uses_real_detection_confidence_and_withdraws_on_occupancy_loss(self):
        row = {'track_id': 1, 'box': [25, 25, 75, 90], 'plate_detection_confidence': .61}
        reader = Mock(return_value={'plate_number': '91소6408', 'plate_type': 'KOREAN_VALID',
                                     'plate_detection_confidence': .99})
        observer = VehicleSpaceObserver(CONFIG, tracker=lambda frame: [row], plate_reader=reader, tracking_target='plate')
        self.addCleanup(observer.close)
        observer.prepare()
        events = []
        frame = np.zeros((140, 240, 3), dtype=np.uint8)
        for index in range(7):
            if observer._pending is not None:
                observer._pending.result(timeout=3)
            events.extend(observer.process(index, index * .5, frame, eligible_spaces={'A-01'})['events'])
        matches = [event for event in events if event['kind'] == 'LOCAL_SPACE_MATCH']
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['plate_detection_confidence'], .61)
        self.assertEqual(matches[0]['space_id'], 'A-01')
        if observer._pending is not None:
            observer._pending.result(timeout=3)
        result = observer.process(7, 3.5, frame, eligible_spaces=set())
        self.assertTrue(any(event['kind'] == 'MATCH_REVIEW' for event in result['events']))
        self.assertIsNone(observer.tracker.states[1]['matched'])

    def test_plate_target_prepares_direct_ocr_without_second_plate_detector(self):
        from ai_vision.parking.vehicle_space_tracker import read_tracked_plate
        observer = VehicleSpaceObserver(CONFIG, tracker=Mock(return_value=[]), tracking_target='plate', ocr_execution='thread')
        self.addCleanup(observer.close)
        with patch('ai_vision.recognition.recognizer._models') as models:
            observer.prepare()
            models.plate.assert_not_called()
            models.ocr.assert_called_once()
        self.assertIs(observer._reader, read_tracked_plate)
        crop = np.zeros((20, 80, 3), dtype=np.uint8)
        with patch('ai_vision.recognition.recognizer.recognize_plate', return_value={'plate_number': '91소6408'}) as read:
            self.assertEqual(observer._reader(crop)['plate_number'], '91소6408')
        self.assertIs(read.call_args.args[0], crop)

    def test_missing_actual_plate_confidence_fails_before_ocr(self):
        reader = Mock()
        observer = VehicleSpaceObserver(CONFIG, tracker=lambda frame: [{'track_id': 1, 'box': [25,25,75,90]}],
            plate_reader=reader, tracking_target='plate')
        self.addCleanup(observer.close)
        observer.prepare()
        with self.assertRaises(ValueError):
            observer.process(0, 0, np.zeros((140,240,3), dtype=np.uint8))
        reader.assert_not_called()

    def test_unknown_tracking_target_is_rejected_before_model_loading(self):
        from ai_vision.parking.vehicle_space_tracker import create_vehicle_tracker
        with self.assertRaises(ValueError):
            create_vehicle_tracker('automatic-paper')
        with self.assertRaises(ValueError):
            VehicleSpaceObserver(CONFIG, tracking_target=True)


class PlatePositionVideoTests(unittest.TestCase):
    setUp = RunVehicleSpaceTrackingTests.setUp

    def test_saved_video_uses_plate_confidence_and_existing_consensus(self):
        self.tracker.return_value[0]['plate_detection_confidence'] = .62
        self.reader.return_value = {'plate_number': '91소6408', 'plate_type': 'KOREAN_VALID'}
        output = self.root / 'plate_target'
        with patch('cv2.VideoCapture', return_value=self.capture):
            report = run(self.source, self.config, output, tracker=self.tracker,
                         plate_reader=self.reader, tracking_target='plate')
        events = [json.loads(line) for line in (output / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        match = next(event for event in events if event['kind'] == 'LOCAL_SPACE_MATCH')
        self.assertEqual(match['plate_detection_confidence'], .62)
        self.assertEqual(report['tracking_target'], 'plate')
        self.assertFalse(report['http_enabled'])

    def test_plate_target_rejects_remote_vehicle_crop_reader_before_capture(self):
        with patch('cv2.VideoCapture') as capture:
            with self.assertRaises(ValueError):
                run(self.source, self.config, self.root / 'remote_plate', tracking_target='plate',
                    vision_api_url='http://example.invalid')
            capture.assert_not_called()


class ProcessSpaceOCRTests(unittest.TestCase):
    def observer(self, pool):
        row = {'track_id': 1, 'box': [25,25,75,90], 'plate_detection_confidence': .63}
        observer = VehicleSpaceObserver(CONFIG, tracker=lambda frame: [dict(row)], tracking_target='plate')
        self.addCleanup(observer.close)
        ready = Mock()
        ready.result.return_value = 12345
        pending = Mock()
        pending.done.return_value = False
        pending.result.return_value = None
        pool.submit.side_effect = [ready, pending, pending]
        with patch('concurrent.futures.ProcessPoolExecutor', return_value=pool), \
                patch('ai_vision.recognition.recognizer._models') as models:
            observer.prepare()
            models.ocr.assert_not_called()
            models.plate.assert_not_called()
        return observer, row, pending

    def test_default_local_plate_ocr_uses_spawn_worker_and_only_one_pending_crop(self):
        from ai_vision.parking.vehicle_space_tracker import prepare_space_ocr_process, recognize_space_ocr_process
        pool = Mock()
        observer, row, pending = self.observer(pool)
        frame = np.zeros((140,240,3), dtype=np.uint8)
        observer.process(0,0,frame)
        observer.process(1,.5,frame)
        self.assertEqual(pool.submit.call_count,2)
        self.assertIs(pool.submit.call_args_list[0].args[0],prepare_space_ocr_process)
        self.assertIs(pool.submit.call_args_list[1].args[0],recognize_space_ocr_process)
        self.assertEqual(pool.submit.call_args_list[1].args[1]['plate_detection_confidence'],.63)
        self.assertEqual(observer.summary()['ocr_execution'],'process')
        self.assertEqual(observer.summary()['ocr_worker_pid'],12345)
        observer.close()
        pool.shutdown.assert_called_once_with(wait=True,cancel_futures=True)

    def test_process_result_retains_original_frame_and_cannot_attach_after_movement(self):
        from ai_vision.parking.vehicle_space_tracker import pack_space_ocr_result
        pool = Mock()
        observer,row,pending = self.observer(pool)
        frame = np.zeros((140,240,3),dtype=np.uint8)
        observer.process(0,0,frame)
        job = pool.submit.call_args.args[1]
        packed = pack_space_ocr_result(job,{'plate_number':'91소6408','plate_type':'KOREAN_VALID'},'plate')
        self.assertEqual(packed['sample']['frame_index'],0)
        self.assertEqual(packed['sample']['video_seconds'],0)
        row['box'] = [140,25,190,90]
        pending.done.return_value = True
        pending.result.return_value = packed
        result = observer.process(1,.5,frame)
        self.assertEqual(observer.tracker.states[1]['space'],'A-02')
        self.assertEqual(observer.tracker.states[1]['samples'],[])
        self.assertFalse(any(e['kind']=='LOCAL_SPACE_MATCH' for e in result['events']))

    def test_worker_failure_propagates_and_cleanup_still_runs(self):
        from concurrent.futures.process import BrokenProcessPool
        pool = Mock()
        observer,row,pending = self.observer(pool)
        frame = np.zeros((140,240,3),dtype=np.uint8)
        observer.process(0,0,frame)
        pending.done.return_value = True
        pending.result.side_effect = BrokenProcessPool('worker ended')
        with self.assertRaises(BrokenProcessPool):
            observer.process(1,.5,frame)
        observer.close()
        pool.shutdown.assert_called_once()

    def test_process_execution_cannot_silently_serialize_injected_reader(self):
        with self.assertRaises(ValueError):
            VehicleSpaceObserver(CONFIG,plate_reader=Mock(),ocr_execution='process')

    def test_process_result_is_picklable_without_camera_or_bound_observer(self):
        from concurrent.futures import ProcessPoolExecutor
        from multiprocessing import get_context
        from ai_vision.parking.vehicle_space_tracker import pack_space_ocr_result
        job = {'track_id':1,'space_id':'A-01','since':0,'frame_index':3,
               'video_seconds':1.5,'plate_detection_confidence':.63}
        with ProcessPoolExecutor(max_workers=1,mp_context=get_context('spawn')) as pool:
            result = pool.submit(pack_space_ocr_result,job,
                {'plate_number':'91소6408','plate_type':'KOREAN_VALID'},'plate').result(timeout=30)
        self.assertEqual(result['sample']['plate_detection_confidence'],.63)
        self.assertEqual(result['sample']['video_seconds'],1.5)


class ConnectionWithdrawalReasonTests(unittest.TestCase):
    def matched(self):
        tracker = VehicleSpaceTracker(CONFIG)
        for index in range(5):
            tracker.process(index,index*.5,[observation(index)],eligible_spaces={'A-01','A-02'})
        self.assertEqual(tracker.states[1]['matched'],'A-01')
        return tracker

    def test_position_space_boundary_and_missing_observation_have_distinct_reasons(self):
        for box,reason in [((40,25,90,90),'POSITION_MOVED'),((145,25,195,90),'SPACE_CHANGED'),
                           ((95,25,125,90),'OUTSIDE_SPACE')]:
            with self.subTest(reason=reason):
                tracker = self.matched()
                events = tracker.process(5,2.5,[observation(5,box=box)])
                event = next(e for e in events if e['kind']=='MATCH_REVIEW')
                self.assertEqual(event['reason'],reason)
                self.assertEqual(event['plate_number'],'91소6408')
                self.assertGreater(event['evidence']['distance_pixels'],0)
        tracker = self.matched()
        event = next(e for e in tracker.process(5,2.5,[]) if e['kind']=='MATCH_REVIEW')
        self.assertEqual(event['reason'],'TRACK_NOT_OBSERVED')
        self.assertEqual(event['evidence']['elapsed_seconds'],.5)

    def test_gap_is_not_reported_as_physical_departure(self):
        tracker = self.matched()
        row = observation(5)
        row['plate_sample']['video_seconds'] = 4
        event = next(e for e in tracker.process(5,4,[row]) if e['kind']=='TRACK_LOST')
        self.assertEqual(event['reason'],'OBSERVATION_GAP')
        self.assertEqual(event['evidence']['elapsed_seconds'],2)
        self.assertEqual(event['plate_number'],'91소6408')
        self.assertIsNone(tracker.states[1]['matched'])

    def test_occupancy_and_multiple_tracks_have_distinct_reasons(self):
        tracker = self.matched()
        events = tracker.process(5,2.5,[observation(5)],eligible_spaces=set())
        event = next(e for e in events if e['kind']=='MATCH_REVIEW')
        self.assertEqual(event['reason'],'OCCUPANCY_NOT_CONTINUOUS')
        self.assertFalse(event['evidence']['occupancy_eligible'])
        tracker = self.matched()
        events = tracker.process(5,2.5,[observation(5),observation(5,track=2)])
        event = next(e for e in events if e['kind']=='MATCH_REVIEW')
        self.assertEqual(event['reason'],'MULTIPLE_TRACKS_IN_SPACE')
        self.assertEqual(event['evidence']['observed_tracks_in_space'],2)

    def test_plate_conflict_also_emits_explicit_withdrawal_once(self):
        tracker = self.matched()
        events = tracker.process(5,2.5,[observation(5,plate='30고5957')])
        reviews = [e for e in events if e['kind']=='MATCH_REVIEW']
        self.assertEqual(len(reviews),1)
        self.assertEqual(reviews[0]['reason'],'PLATE_CONFLICT')
        self.assertEqual(reviews[0]['plate_number'],'91소6408')
        self.assertIsNone(tracker.states[1]['matched'])
        events = tracker.process(6,3,[observation(6,plate='30고5957')])
        self.assertFalse(any(e['kind']=='MATCH_REVIEW' for e in events))

    def test_duplicate_plate_reason_identifies_competing_track(self):
        tracker = self.matched()
        events = []
        for index in range(5,10):
            events.extend(tracker.process(index,index*.5,[observation(index),
                observation(index,track=2,box=(145,25,195,90))]))
        event = next(e for e in events if e.get('reason')=='DUPLICATE_PLATE')
        self.assertEqual(event['evidence']['conflicting_track_id'],2)
        self.assertTrue(all(state['matched'] is None for state in tracker.states.values()))


class WithdrawalSummaryVideoTests(unittest.TestCase):
    setUp = RunVehicleSpaceTrackingTests.setUp

    def test_saved_video_summary_and_jsonl_agree_on_withdrawal_reason(self):
        self.tracker.side_effect = [[{'track_id':1,'box':[25,25,75,90]}]]*5 + [
            [{'track_id':1,'box':[145,25,195,90]}]]*2
        output = self.root/'withdrawal_summary'
        with patch('cv2.VideoCapture',return_value=self.capture):
            report = run(self.source,self.config,output,tracker=self.tracker,plate_reader=self.reader)
        self.assertEqual(report['connection_withdrawal_counts'],{'SPACE_CHANGED':1})
        events = [json.loads(line) for line in (output/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(sum(e.get('reason')=='SPACE_CHANGED' for e in events),1)


if __name__ == '__main__':
    unittest.main()

"""실제 DB·카메라 없이 통합 시험의 단계 검증을 확인합니다."""
import copy
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
from ai_vision.parking.demo_tools.deployed_sequence import active_usage, decision, exited, empty_ready, acknowledged_fire


class DeployedSequenceTests(unittest.TestCase):
    def test_both_demo_modes_allow_all_four_mapped_spaces(self):
        from ai_vision.parking.demo_tools.deployed_sequence import trial_config
        from ai_vision.parking.parking_delivery import delivery_settings
        from ai_vision.parking.parking_event_sender import scoped_space_mapping
        mapping={f'A-{i:02d}':f'3F-A{i:02d}' for i in range(1,5)}
        original={'gate_config':'gate.json','spaces_config':'spaces.json','reference':'reference.png',
                  'space_code_map':mapping,'allowed_codes':['3F-A01','3F-A02']}
        profile=trial_config(original,Path('profile/runtime.json'),Path('run'))
        self.assertEqual(profile['allowed_codes'],['3F-A01','3F-A02','3F-A03','3F-A04'])
        self.assertEqual(original['allowed_codes'],['3F-A01','3F-A02'])
        with scoped_space_mapping(mapping):
            settings=delivery_settings({'spaces':[{'id':key} for key in mapping]},True,profile['allowed_codes'],
                {'AI_OCCUPANCY_API_KEY':'test-key','PARKING_AI_BASE_URL':'http://localhost:81'})
        self.assertIn('3F-A03',settings['allowed_codes'])
        self.assertIn('3F-A04',settings['allowed_codes'])

    def setUp(self):
        self.row={'payload':{'event_id':'event','event_type':'VEHICLE_SPACE_MATCH','plate_number':'91소6408',
            'space_code':'3F-A02','expected_parking_usage_id':33},'receipt':{'event_id':'event',
            'parking_usage_id':33,'parking_decision':'WRONG_SPACE','receipt_verified':True,'request_attempted':True}}

    def test_verified_wrong_space_receipt(self):
        self.assertTrue(decision([self.row],33,'3F-A02','WRONG_SPACE'))

    def test_unreserved_decision_is_never_claimed_as_matched(self):
        self.row['receipt']['parking_decision']='NO_VALID_RESERVATION'
        self.assertTrue(decision([self.row],33,'3F-A02','NO_VALID_RESERVATION'))
        self.assertFalse(decision([self.row],33,'3F-A02','MATCHED'))

    def test_fixture_modes_are_explicit_and_separate(self):
        from ai_vision.parking.demo_tools.deployed_fixture import DeployedFixture
        # 설정 준비만 검증하며 JVM·DB는 호출하지 않습니다.
        helper=Path('ai_vision/results/parking_demo/aws_20261028/.demo_helper/classpath.txt')
        with patch.object(Path,'read_text',return_value='test-classpath'):
            required=DeployedFixture(Path('unused'))
            unreserved=DeployedFixture(Path('unused'),reservation_required=False)
        self.assertEqual(required.env['DEPLOYED_DEMO_NO_RESERVATION'],'0')
        self.assertEqual(unreserved.env['DEPLOYED_DEMO_NO_RESERVATION'],'1')

    def test_wrong_usage_or_code_or_decision_cannot_advance(self):
        for usage,code,verdict in ((34,'3F-A02','WRONG_SPACE'),(33,'3F-A01','WRONG_SPACE'),(33,'3F-A02','MATCHED')):
            self.assertFalse(decision([self.row],usage,code,verdict))

    def test_unverified_or_unattempted_receipt_cannot_advance(self):
        for key in ('receipt_verified','request_attempted'):
            row=copy.deepcopy(self.row);row['receipt'][key]=False
            self.assertFalse(decision([row],33,'3F-A02','WRONG_SPACE'))

    def test_unrelated_event_receipt_is_rejected(self):
        self.row['receipt']['event_id']='other'
        self.assertFalse(decision([self.row],33,'3F-A02','WRONG_SPACE'))

    def test_active_usage_requires_expected_plate(self):
        state={'status':'ACTIVE','active':{'plate_number':'91소6408','parking_usage_id':33}}
        self.assertEqual(active_usage(state),33)
        state['active']['plate_number']='12가3456';self.assertIsNone(active_usage(state))

    def test_exit_must_match_entry_usage(self):
        state={'status':'EMPTY','last_exit':{'plate_number':'91소6408','parking_usage_id':33}}
        self.assertTrue(exited(state,33));self.assertFalse(exited(state,34))

    def test_empty_scene_requires_all_four_confirmed(self):
        self.assertFalse(empty_ready({}))
        rows=[{'status':'EMPTY'} for _ in range(4)]
        self.assertTrue(empty_ready({'occupancy':{'spaces':rows}}))
        rows[1]['status']='OCCUPIED'
        self.assertFalse(empty_ready({'occupancy':{'spaces':rows}}))

    def test_fire_stage_requires_matching_success_checkpoint(self):
        payload={'hazard_type':'FIRE','status':'SUSPECTED','transition_id':'fire'}
        with patch('ai_vision.recognition.local_io.read_json',return_value={'acknowledged_transition_ids':['fire']}),patch('ai_vision.safety.fire_alert_live.load_live_payloads',return_value=[payload]):
            self.assertTrue(acknowledged_fire(Path('unused')))
            self.assertFalse(acknowledged_fire(Path('unused'),['fire']))
            payload['hazard_type']='SMOKE';self.assertFalse(acknowledged_fire(Path('unused')))


class TrialOutcomeTests(unittest.TestCase):
    def test_nonzero_worker_exit_and_delivery_stop_cannot_be_success(self):
        from ai_vision.parking.demo_tools.deployed_sequence import final_completion_checks
        workers=[{'alive':False,'exit_code':0},{'alive':False,'exit_code':0}]
        report={'sequence_complete':True,'camera_continuity_verified':True,'parking_delivery_paused':True,
            'gate_fire_ack':True,'parking_fire_ack':True,'exit_db':{'USAGE_ROWS':'1','EXITED_ROWS':'1'},
            'runtime_final':{'state':'STOPPED','processes':copy.deepcopy(workers)},
            'fire_final':{'state':'STOPPED','processes':copy.deepcopy(workers)}}
        parking={'status':'STOPPED','error_type':None};gate={'status':'STOPPED','cleanup_errors':0}
        self.assertTrue(all(final_completion_checks(report,parking,gate).values()))
        report['runtime_final']['processes'][1]['exit_code']=1
        parking['status']='DELIVERY_STOPPED'
        checks=final_completion_checks(report,parking,gate)
        self.assertFalse(checks['camera_workers_exit_zero'])
        self.assertFalse(checks['parking_report_clean'])
        self.assertFalse(all(checks.values()))
    def test_known_backend_policy_mismatch_is_blocked_not_success(self):
        from ai_vision.parking.demo_tools.deployed_sequence import result_exit_code,FixtureFailure
        error=FixtureFailure('BACKEND_POLICY_CHANGED')
        report={'success':False,'error_code':error.code}
        self.assertEqual(result_exit_code(report),2)
        self.assertEqual(report['status'],'BLOCKED')

    def test_active_usage_message_is_safe_and_specific(self):
        from ai_vision.parking.demo_tools.deployed_sequence import fixture_failure
        error=fixture_failure('java.lang.IllegalStateException: Active usage exists; private-token')
        self.assertEqual(error.code,'ACTIVE_USAGE_EXISTS')
        self.assertIn('미출차',str(error));self.assertNotIn('private-token',str(error))

    def test_active_usage_ids_are_reported_without_raw_error(self):
        from ai_vision.parking.demo_tools.deployed_sequence import fixture_failure
        error=fixture_failure('ACTIVE_USAGE_IDS=37,38\nActive usage exists; password=hidden')
        self.assertIn('37,38',str(error));self.assertNotIn('hidden',str(error))

    def test_unknown_db_error_does_not_expose_stderr(self):
        from ai_vision.parking.demo_tools.deployed_sequence import fixture_failure
        error=fixture_failure('password=do-not-print')
        self.assertEqual(error.code,'DB_OPERATION_FAILED')
        self.assertNotIn('do-not-print',str(error))

    def test_user_cancel_is_incomplete_but_not_execution_failure(self):
        from ai_vision.parking.demo_tools.deployed_sequence import result_exit_code
        report={'success':False,'cancelled':True,'runtime_final':{'state':'STOPPED'}}
        self.assertEqual(result_exit_code(report),130)
        self.assertEqual(report['status'],'CANCELLED');self.assertFalse(report['success'])

    def test_cancel_with_cleanup_failure_remains_failure(self):
        from ai_vision.parking.demo_tools.deployed_sequence import result_exit_code
        for extra in ({'reservation_cleanup_error':'RuntimeError'},{'runtime_final':{'state':'FAILED'}},
                      {'fire_final':{'state':'FAILED'}}):
            report={'success':False,'cancelled':True,**extra}
            self.assertEqual(result_exit_code(report),1)
            self.assertEqual(report['status'],'CANCELLED_WITH_CLEANUP_ERROR')

    def test_incomplete_execution_cannot_report_success(self):
        from ai_vision.parking.demo_tools.deployed_sequence import result_exit_code
        report={'success':False,'error_code':'ACTIVE_USAGE_EXISTS'}
        self.assertEqual(result_exit_code(report),2)
        self.assertEqual(report['status'],'BLOCKED')


class ContinuousDeliveryGateTests(unittest.TestCase):
    def test_paused_events_do_not_leave_queue_that_fails_shutdown(self):
        from ai_vision.parking.demo_tools.deployed_delivery_gate import parking_delivery_gate
        from ai_vision.parking.parking_delivery import ParkingDelivery,ParkingDeliveryWorker
        client=ParkingDelivery({'allowed_codes':{'3F-A01'}});self.addCleanup(client.close)
        worker=ParkingDeliveryWorker(client)
        with parking_delivery_gate(self.root),patch.object(client.session,'post') as post:
            (self.root/'parking_delivery_paused.flag').touch()
            receipts=[]
            for index in range(20):
                event={'event_id':str(index),'space_code':'3F-A01'};receipt={'event_id':str(index),'status':'QUEUED'}
                self.assertTrue(worker.enqueue(event,receipt));receipts.append(receipt)
            self.assertEqual(worker.pending,0)
            worker.close()
            self.assertFalse(worker.blocked)
            self.assertTrue(all(row['reason']=='PARKING_PHASE_COMPLETE' for row in receipts))
            post.assert_not_called()

    def test_legacy_match_marker_does_not_disable_current_position_tracking(self):
        from ai_vision.parking.demo_tools.deployed_delivery_gate import parking_delivery_gate
        from ai_vision.recognition.vehicle_http import VehicleHTTPClient,SpaceMatchHTTPClient
        from ai_vision.tests.recognition.test_vehicle_response import sample_space_event
        factory=unittest.mock.Mock()
        gate=VehicleHTTPClient(context_url='http://localhost:81',api_key='test',enabled=True,session_factory=factory)
        match=SpaceMatchHTTPClient(context_url='http://localhost:81',api_key='test',enabled=True,session_factory=factory)
        with parking_delivery_gate(self.root):
            (self.root/'parking_match_complete.flag').touch()
            self.assertTrue(gate.enabled)
            self.assertTrue(match.enabled)
        self.assertTrue(match.enabled);factory.assert_not_called()

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)

    def test_pause_blocks_vehicle_and_match_network_and_restores(self):
        from ai_vision.parking.demo_tools.deployed_delivery_gate import parking_delivery_gate
        from ai_vision.recognition.vehicle_http import VehicleHTTPClient, SpaceMatchHTTPClient
        from ai_vision.tests.recognition.test_vehicle_response import sample_event, sample_space_event
        factory=unittest.mock.Mock()
        gate=VehicleHTTPClient(context_url='http://localhost:81',api_key='test',enabled=True,session_factory=factory)
        match=SpaceMatchHTTPClient(context_url='http://localhost:81',api_key='test',enabled=True,session_factory=factory)
        with parking_delivery_gate(self.root) as ack:
            self.assertTrue(gate.enabled)
            (self.root/'parking_delivery_paused.flag').touch()
            self.assertFalse(gate.enabled);self.assertFalse(match.enabled)
            self.assertFalse(gate.send(sample_event())['request_attempted'])
            self.assertFalse(match.send(sample_space_event())['request_attempted'])
            ack();self.assertTrue((self.root/'parking_delivery_paused.gate.ack').exists())
        self.assertTrue(gate.enabled);factory.assert_not_called()

    def test_pause_skips_occupancy_without_claiming_server_success(self):
        from ai_vision.parking.demo_tools.deployed_delivery_gate import parking_delivery_gate
        from ai_vision.parking.parking_delivery import ParkingDelivery
        client=ParkingDelivery({'allowed_codes':{'3F-A01'}});self.addCleanup(client.close)
        with patch.object(client.session,'post') as post, parking_delivery_gate(self.root):
            (self.root/'parking_delivery_paused.flag').touch()
            result=client.send({'event_id':'one','space_code':'3F-A01'})
        self.assertEqual(result['status'],'CANCELLED_BEFORE_SEND')
        self.assertEqual(client.attempts,0);post.assert_not_called()

    def test_parking_ack_waits_for_pending_request(self):
        from ai_vision.parking.demo_tools.deployed_delivery_gate import parking_delivery_gate
        from ai_vision.parking.parking_delivery import ParkingDeliveryWorker
        worker=unittest.mock.Mock(pending=1,blocked=False)
        with patch.object(ParkingDeliveryWorker,'poll',return_value=True),parking_delivery_gate(self.root):
            (self.root/'parking_delivery_paused.flag').touch()
            self.assertTrue(ParkingDeliveryWorker.poll(worker,lambda:None))
            self.assertFalse((self.root/'parking_delivery_paused.parking.ack').exists())
            worker.pending=0
            ParkingDeliveryWorker.poll(worker,lambda:None)
            self.assertTrue((self.root/'parking_delivery_paused.parking.ack').exists())

    def test_gate_patch_restores_after_exception(self):
        from ai_vision.parking.demo_tools.deployed_delivery_gate import parking_delivery_gate
        from ai_vision.recognition.vehicle_http import VehicleHTTPClient
        original=VehicleHTTPClient.enabled
        with self.assertRaises(RuntimeError):
            with parking_delivery_gate(self.root):raise RuntimeError('중단')
        self.assertIs(VehicleHTTPClient.enabled,original)


if __name__=='__main__':unittest.main()

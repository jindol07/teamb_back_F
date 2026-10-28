"""소유 파일이 있는 시험만 복구하고 타인의 기록은 건드리지 않습니다."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from ai_vision.parking.demo_tools.deployed_recovery import verified_active, cleanup_owned_run, recover_pending_runs


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.run=Path(self.folder.name)/('a'*32);self.run.mkdir()
        (self.run/'reservation.properties').write_text('committed=true\nmarker=AI_SITE_TEST_1234abcd\n',encoding='ascii')
        self.gate=self.run/'parking_runs'/('b'*32)/'gate';self.gate.mkdir(parents=True)
        self.state={'record_type':'SINGLE_VEHICLE_HANDOFF','owner_session_id':'test-session','status':'ACTIVE',
            'active':{'plate_number':'91소6408','parking_usage_id':37,'detected_at':'2026-10-28T07:18:23+00:00'}}

    def save(self):
        (self.gate/'single_vehicle_handoff.json').write_text(json.dumps(self.state),encoding='utf-8')

    def test_active_usage_requires_session_plate_and_aware_timestamp(self):
        self.assertEqual(verified_active(self.state)[0],37)
        for field,value in (('plate_number','12가3456'),('detected_at','2026-10-28T16:18:23'),('parking_usage_id',True)):
            state=json.loads(json.dumps(self.state));state['active'][field]=value
            self.assertIsNone(verified_active(state))

    def test_own_interrupted_usage_closes_and_reservation_cancels(self):
        self.save();fixture=Mock();fixture.call.return_value={'ok':'1'}
        result=cleanup_owned_run(self.run,fixture=fixture)
        self.assertEqual(result['status'],'CLEANED')
        self.assertEqual(fixture.call.call_args_list,[unittest.mock.call('close-usage',37,entry_at='2026-10-28T07:18:23+00:00'),unittest.mock.call('cancel')])
        self.assertTrue((self.run/'automatic_cleanup.json').exists())

    def test_already_exited_usage_does_not_generate_another_exit(self):
        self.state.update(status='EMPTY',active=None);self.save();fixture=Mock();fixture.call.return_value={}
        cleanup_owned_run(self.run,fixture=fixture)
        fixture.call.assert_called_once_with('cancel')

    def test_unknown_marker_never_calls_database(self):
        (self.run/'reservation.properties').write_text('committed=true\nmarker=OTHER\n',encoding='ascii')
        fixture=Mock()
        with self.assertRaises(ValueError):cleanup_owned_run(self.run,fixture=fixture)
        fixture.call.assert_not_called()

    def test_cleanup_failure_is_not_marked_recovered(self):
        self.save();fixture=Mock();fixture.call.side_effect=RuntimeError('DB 중단')
        with self.assertRaises(RuntimeError):cleanup_owned_run(self.run,fixture=fixture)
        self.assertFalse((self.run/'automatic_cleanup.json').exists())

    def test_successful_previous_run_is_not_changed(self):
        (self.run/'result.json').write_text(json.dumps({'success':True}),encoding='utf-8')
        with patch('ai_vision.parking.demo_tools.deployed_recovery.DeployedFixture') as fixture:
            self.assertEqual(recover_pending_runs(self.run.parent,self.run.parent/'new'),[])
        fixture.assert_not_called()

    def test_corrupt_previous_file_does_not_abort_new_startup(self):
        (self.run/'reservation.properties').write_text('broken',encoding='ascii')
        results=recover_pending_runs(self.run.parent,self.run.parent/'new')
        self.assertEqual(results[0]['cleanup']['status'],'REVIEW_REQUIRED')

    def test_unverified_active_usage_never_calls_database(self):
        self.state['active']['plate_number']='12가3456';self.save();fixture=Mock()
        with self.assertRaises(ValueError):cleanup_owned_run(self.run,fixture=fixture)
        fixture.call.assert_not_called()


if __name__=='__main__':unittest.main()

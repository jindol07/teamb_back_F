"""자유 순서의 점유 관찰과 예약 연결 유지 정책을 검증합니다."""
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace
from ai_vision.parking.demo_tools.free_parking import update_free_observation


def matched_row(code='3F-A01',usage=83,verified=True):
    return {'payload':{'event_id':'one','event_type':'VEHICLE_SPACE_MATCH','space_code':code,
            'plate_number':'91소6408','expected_parking_usage_id':usage},
            'receipt':{'event_id':'one','event_type':'VEHICLE_SPACE_MATCH','parking_usage_id':usage,
            'receipt_verified':verified,'request_attempted':True,'parking_decision':'MATCHED','state':'APPLIED'}}


class FreeParkingTests(unittest.TestCase):
    def test_any_order_and_revisit_do_not_require_all_four(self):
        state={}
        for space in ('A-04','A-02','A-04'):
            update_free_observation(state,{'occupancy':{'spaces':[{'space_id':space,'status':'OCCUPIED'}]}},83)
        self.assertEqual(state['observed_occupied_codes'],['3F-A04','3F-A02'])
        self.assertFalse(state['a01_link_confirmed'])

    def test_occupancy_is_not_reported_as_vehicle_link(self):
        state=update_free_observation({}, {'occupancy':{'spaces':[{'space_id':'A-01','status':'OCCUPIED'}]}},83)
        self.assertFalse(state['a01_link_confirmed'])

    def test_historical_a01_match_is_separate_from_current_position(self):
        state=update_free_observation({}, {'vehicle_space':{'deliveries':[matched_row()]}},83)
        update_free_observation(state,{'occupancy':{'spaces':[{'space_id':'A-03','status':'OCCUPIED'}]}},83)
        self.assertTrue(state['a01_link_confirmed'])
        self.assertIsNone(state['current_linked_space'])
        self.assertEqual(state['observed_occupied_codes'],['3F-A03'])

    def test_other_space_server_link_is_failure(self):
        with self.assertRaises(RuntimeError):
            update_free_observation({}, {'vehicle_space':{'deliveries':[matched_row('3F-A03')]}},83)

    def test_unverified_or_other_usage_receipt_cannot_lock_a01(self):
        for row in (matched_row(usage=84),matched_row(verified=False)):
            state=update_free_observation({}, {'vehicle_space':{'deliveries':[row]}},83)
            self.assertFalse(state['a01_link_confirmed'])

    def test_fixed_reserved_and_unreserved_sequences_are_preserved(self):
        from ai_vision.parking.demo_tools import run_deployed_integration as runner
        from ai_vision.parking.demo_tools.deployed_sequence import PLATE
        for no_reservation in (False,True):
            rows=[]
            for code,verdict in (('3F-A02','NO_VALID_RESERVATION' if no_reservation else 'WRONG_SPACE'),
                                 ('3F-A01','NO_VALID_RESERVATION' if no_reservation else 'MATCHED')):
                row=matched_row(code);row['receipt']['parking_decision']=verdict
                rows.append(row)
            fixture=Mock();fixture.call.side_effect=[{'LINKED_SPACE_ID':'47','LINKED_RESERVATION_ID':'0'},
                {'LINKED_SPACE_ID':'46','LINKED_RESERVATION_ID':'0'} if no_reservation else {'MATCHED_ROWS':'1'}]
            handoff={'status':'EMPTY','last_exit':{'parking_usage_id':83,'plate_number':PLATE}}
            with patch.object(runner,'phase'),patch.object(runner,'snapshot',return_value=handoff),patch.object(runner,'wait_for',side_effect=lambda callback,*args: self.assertTrue(callback())):
                runner.run_fixed_parking(SimpleNamespace(no_reservation=no_reservation),Path('run'),Mock(),fixture,83,{},lambda:rows)
            self.assertEqual(fixture.call_count,0)
            self.assertEqual(fixture.call.call_count,2)

    def test_wrong_space_is_a_real_position_link_not_a_normal_reservation(self):
        row=matched_row('3F-A04');row['receipt']['parking_decision']='WRONG_SPACE'
        state=update_free_observation({}, {'vehicle_space':{'deliveries':[row]}},83)
        self.assertEqual(state['current_linked_space'],'3F-A04')
        self.assertEqual(state['current_parking_decision'],'WRONG_SPACE')
        self.assertFalse(state['a01_link_confirmed'])

    def test_verified_release_then_new_position_replaces_old_link(self):
        first=matched_row()
        release={'payload':{'event_id':'release','event_type':'VEHICLE_SPACE_RELEASE','space_code':'3F-A01',
            'plate_number':'91소6408','parking_usage_id':83,'link_version':4},
            'receipt':{'event_id':'release','event_type':'VEHICLE_SPACE_RELEASE','parking_usage_id':83,
                      'receipt_verified':True,'request_attempted':True,'state':'APPLIED','link_version':5}}
        new=matched_row('3F-A03');new['payload']['event_id']='next';new['receipt']['event_id']='next'
        new['receipt']['parking_decision']='WRONG_SPACE'
        state=update_free_observation({}, {'vehicle_space':{'deliveries':[first,release]}},83)
        self.assertIsNone(state['current_linked_space'])
        state=update_free_observation(state,{'vehicle_space':{'deliveries':[first,release,new]}},83)
        self.assertEqual(state['current_linked_space'],'3F-A03')


if __name__=='__main__':unittest.main()

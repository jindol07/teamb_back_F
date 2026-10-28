"""해제 활성화 사전검사는 실제 해제 가능한 이벤트를 보내지 않습니다."""
import unittest
from unittest.mock import Mock
from ai_vision.parking.demo_tools.release_capability import require_release_enabled
from ai_vision.parking.demo_tools.deployed_sequence import FixtureFailure


class ReleaseCapabilityTests(unittest.TestCase):
    def probe(self,status):
        response=Mock(status_code=status);session=Mock();session.post.return_value=response
        return session,response

    def test_validation_reached_without_vehicle_uuid_or_usage(self):
        session,response=self.probe(400)
        result=require_release_enabled('http://localhost:81/admin',{'AI_OCCUPANCY_API_KEY':'test'},session_factory=lambda:session)
        self.assertFalse(result['db_mutation'])
        payload=session.post.call_args.kwargs['json']
        self.assertEqual(set(payload),{'event_type'})
        self.assertNotEqual(payload['event_type'],'VEHICLE_SPACE_RELEASE')
        session.close.assert_called_once();response.close.assert_called_once()

    def test_disabled_release_stops_before_demo(self):
        session,_=self.probe(503)
        with self.assertRaises(FixtureFailure) as caught:
            require_release_enabled('http://localhost:81',{'AI_OCCUPANCY_API_KEY':'test'},session_factory=lambda:session)
        self.assertEqual(caught.exception.code,'SPACE_RELEASE_DISABLED')

    def test_auth_or_unknown_response_is_not_treated_as_enabled(self):
        for status in (200,401,403,404,500):
            session,_=self.probe(status)
            with self.subTest(status=status),self.assertRaises(FixtureFailure):
                require_release_enabled('http://localhost:81',{'AI_OCCUPANCY_API_KEY':'test'},session_factory=lambda:session)

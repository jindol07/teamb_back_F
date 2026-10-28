import unittest
from ai_vision.safety.shared_delivery_config import load_shared_delivery


class SharedDeliveryConfigTests(unittest.TestCase):
    def test_default_ignores_existing_direct_camera_send_settings(self):
        self.assertIsNone(load_shared_delivery({'SAFETY_CAMERA_SEND_ENABLED':'true','FIRE_ALERT_TOKEN':'secret'}))

    def test_enabled_requires_test_approval_endpoint_and_token(self):
        valid={'SAFETY_SHARED_SEND_ENABLED':'true','SAFETY_SHARED_ALLOW_TEST':'true',
               'SAFETY_SHARED_ALERT_URL':'https://example.test/fire','FIRE_ALERT_TOKEN':'secret'}
        self.assertEqual(load_shared_delivery(valid)['role'],'gate')
        for key in ('SAFETY_SHARED_ALLOW_TEST','SAFETY_SHARED_ALERT_URL','FIRE_ALERT_TOKEN'):
            env=dict(valid);env.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):load_shared_delivery(env)
        with self.assertRaises(ValueError):load_shared_delivery(dict(valid,SAFETY_SHARED_SEND_ROLE='unknown'))

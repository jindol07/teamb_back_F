import unittest
from unittest.mock import patch
from ai_vision.safety.shared_monitor_preflight import check_monitor


class SharedMonitorPreflightTests(unittest.TestCase):
    def config(self):return dict(frame_export_dir='shared',delivery_enabled=False,gate_camera=1,parking_camera=0,preview=True)
    def test_valid_check_never_loads_model_or_opens_camera(self):
        with patch('ai_vision.safety.shared_monitor_preflight.load_runtime_config',return_value=self.config()),patch('ai_vision.safety.shared_monitor_preflight.require_model_file') as file_check:
            result=check_monitor({})
        self.assertFalse(result['http_enabled']);self.assertEqual(file_check.call_count,3)
    def test_real_delivery_flags_are_rejected(self):
        config=self.config()
        with patch('ai_vision.safety.shared_monitor_preflight.load_runtime_config',return_value=config):
            with self.assertRaises(ValueError):check_monitor({'SAFETY_SHARED_SEND_ENABLED':'true'})
            config['delivery_enabled']=True
            with self.assertRaises(ValueError):check_monitor({})
    def test_missing_model_is_not_hidden(self):
        with patch('ai_vision.safety.shared_monitor_preflight.load_runtime_config',return_value=self.config()),patch('ai_vision.safety.shared_monitor_preflight.require_model_file',side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):check_monitor({})
class DeployedMonitorPreflightTests(unittest.TestCase):
    def config(self):
        return dict(delivery_enabled=True,enable_space_release_http=True,preview=True,
                    frame_export_dir='shared',gate_camera=1,parking_camera=0,
                    boot_context_url='https://example.test/admin-api',
                    space_code_map={'A-01':'3F-A01','A-02':'3F-A02'},
                    allowed_codes=['3F-A01','3F-A02'])

    def environment(self):
        return {'SAFETY_SHARED_AUTOSTART':'true','SAFETY_CAMERA_AUTOSTART':'false'}

    def test_sender_alone_does_not_prove_shared_worker_autostart(self):
        from ai_vision.safety.shared_monitor_preflight import check_deployed_monitor
        for env in ({},dict(self.environment(),SAFETY_SHARED_AUTOSTART='false'),
                    dict(self.environment(),SAFETY_CAMERA_AUTOSTART='true')):
            with self.subTest(environment=env),self.assertRaises(ValueError):
                check_deployed_monitor(env)

    def test_all_channels_enabled_and_no_secret_in_report(self):
        from unittest.mock import patch
        from ai_vision.safety.shared_monitor_preflight import check_deployed_monitor
        cfg=self.config()
        delivery=dict(role='both',url=cfg['boot_context_url']+'/api/parking/ai/fire-alerts',token='private-key')
        with patch('ai_vision.safety.shared_monitor_preflight.load_runtime_config',return_value=cfg), \
             patch('ai_vision.safety.shared_delivery_config.load_shared_delivery',return_value=delivery), \
             patch('ai_vision.safety.shared_monitor_preflight.require_model_file'):
            result=check_deployed_monitor(self.environment())
        self.assertTrue(result['parking_http_enabled'] and result['fire_http_enabled'])
        self.assertEqual(result['fire_send_role'],'both')
        self.assertNotIn('private-key',str(result))
        self.assertEqual(result['scope'],'SETTINGS_ONLY_NOT_DELIVERY_ACK')

    def test_disabled_parking_release_fire_or_different_target_is_blocked(self):
        from unittest.mock import patch
        from ai_vision.safety.shared_monitor_preflight import check_deployed_monitor
        base=self.config()
        delivery=dict(role='both',url=base['boot_context_url']+'/api/parking/ai/fire-alerts',token='private-key')
        cases=[(dict(base,delivery_enabled=False),delivery),
               (dict(base,enable_space_release_http=False),delivery),
               (dict(base,frame_export_dir=''),delivery),
               (dict(base,allowed_codes=['3F-A01']),delivery),
               (base,None),(base,dict(delivery,role='gate')),
               (base,dict(delivery,url='https://other.test/api/parking/ai/fire-alerts'))]
        for cfg,send in cases:
            with self.subTest(cfg=cfg,send=send), \
                 patch('ai_vision.safety.shared_monitor_preflight.load_runtime_config',return_value=cfg), \
                 patch('ai_vision.safety.shared_delivery_config.load_shared_delivery',return_value=send), \
                 self.assertRaises(ValueError):
                check_deployed_monitor(self.environment())

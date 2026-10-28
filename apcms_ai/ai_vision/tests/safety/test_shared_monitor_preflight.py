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

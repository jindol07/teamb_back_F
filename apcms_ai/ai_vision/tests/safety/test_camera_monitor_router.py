"""통합 FastAPI 안전감시/HTTP 전송 옵션 (실제 웹캠·외부 네트워크 없이 검증)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai_vision.safety import camera_monitor_router as mod


class CameraMonitorRouterTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(mod.router)

        @self.app.get('/existing')
        def existing():
            return {"ok": True}

    def test_disabled_does_not_start_camera(self):
        with patch.dict(os.environ, {"SAFETY_CAMERA_AUTOSTART": "0", "SAFETY_CAMERA_SEND_ENABLED": "0"}), patch.object(mod.subprocess, "Popen") as launch:
            with TestClient(self.app) as client:
                self.assertEqual(client.get('/existing').json(), {"ok": True})
                status = client.get('/safety/camera/status').json()
                self.assertFalse(status['configured'])
                self.assertFalse(status['running'])
                self.assertEqual(status['delivery'], 'DRY_RUN_NO_HTTP')
            launch.assert_not_called()

    def test_enabled_starts_one_dry_run_and_stops_on_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_dir = Path(tmp) / 'models'
            model_dir.mkdir()
            (model_dir / 'fire_smoke.pt').write_bytes(b'fake-model')
            result_dir = Path(tmp) / 'results'

            class FakeProcess:
                pid = 5511
                def poll(self):
                    return None

            with patch.dict(os.environ, {
                'SAFETY_CAMERA_AUTOSTART': '1', 'SAFETY_CAMERA_INDEX': '0',
                'SAFETY_CAMERA_SHOW': '0', 'SAFETY_CAMERA_SEND_ENABLED': '0',
            }), patch.object(mod, 'MODEL_DIR', model_dir), patch.object(mod, 'RESULT_DIR', result_dir), \
                 patch.object(mod.subprocess, 'Popen', return_value=FakeProcess()) as spawn, \
                 patch.object(mod, '_stop_tree') as stop:
                with TestClient(self.app) as client:
                    status = client.get('/safety/camera/status').json()
                    self.assertTrue(status['configured'])
                    self.assertTrue(status['running'])
                    self.assertEqual(status['delivery'], 'DRY_RUN_NO_HTTP')
                    self.assertEqual(client.get('/existing').status_code, 200)
                    args = spawn.call_args.args[0]
                    self.assertIn('ai_vision.safety.fire_alert_live', args)
                    self.assertIn('--camera', args)
                    self.assertNotIn('--send', args)
                    self.assertNotIn('--show', args)
                spawn.assert_called_once()
                stop.assert_called_once()

    def test_enabled_missing_model_keeps_fastapi_alive(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'SAFETY_CAMERA_AUTOSTART': '1'}), \
                 patch.object(mod, 'MODEL_DIR', Path(tmp)), \
                 patch.object(mod.subprocess, 'Popen') as launch:
                with TestClient(self.app) as client:
                    self.assertEqual(client.get('/existing').status_code, 200)
                    status = client.get('/safety/camera/status').json()
                    self.assertTrue(status['configured'])
                    self.assertFalse(status['running'])
                    self.assertIn('모델 파일 없음', status['error'])
                launch.assert_not_called()


    def _prepared_environment(self, root: Path):
        model_dir = root / 'models'
        model_dir.mkdir()
        (model_dir / 'fire_smoke.pt').write_bytes(b'fake-model')
        return model_dir, root / 'results'

    def test_test_send_local_mock_adds_send_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_dir, result_dir = self._prepared_environment(Path(tmp))
            class FakeProcess:
                pid = 12345
                def poll(self): return None
            with patch.dict(os.environ, {
                'SAFETY_CAMERA_AUTOSTART': '1', 'SAFETY_CAMERA_SEND_ENABLED': '1',
                'SAFETY_CAMERA_SEND_MODE': 'test',
                'SAFETY_CAMERA_ALERT_URL': 'http://127.0.0.1:8765/api/mock/fire-alerts',
                'SAFETY_CAMERA_SHOW': '0', 'FIRE_ALERT_TOKEN': ''
            }), patch.object(mod, 'MODEL_DIR', model_dir), patch.object(mod, 'RESULT_DIR', result_dir), \
                 patch.object(mod.subprocess, 'Popen', return_value=FakeProcess()) as spawn, \
                 patch.object(mod, '_stop_tree'):
                with TestClient(self.app) as client:
                    self.assertEqual(client.get('/safety/camera/status').json()['delivery'], 'TEST_HTTP')
                argv = spawn.call_args.args[0]
                self.assertIn('--send', argv)
                self.assertIn('--allow-test-records', argv)
                self.assertIn('http://127.0.0.1:8765/api/mock/fire-alerts', argv)
                self.assertNotIn('--production-camera', argv)

    def test_test_send_bad_external_http_rejected_before_camera(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_dir, result_dir = self._prepared_environment(Path(tmp))
            with patch.dict(os.environ, {
                'SAFETY_CAMERA_AUTOSTART': '1', 'SAFETY_CAMERA_SEND_ENABLED': '1',
                'SAFETY_CAMERA_SEND_MODE': 'test',
                'SAFETY_CAMERA_ALERT_URL': 'http://example.com/alerts',
                'SAFETY_CAMERA_SHOW': '0'
            }), patch.object(mod, 'MODEL_DIR', model_dir), patch.object(mod, 'RESULT_DIR', result_dir), \
                 patch.object(mod.subprocess, 'Popen') as launch:
                with TestClient(self.app) as client:
                    status = client.get('/safety/camera/status').json()
                    self.assertFalse(status['running'])
                    self.assertEqual(status['delivery'], 'CONFIGURATION_ERROR')
                    self.assertIn('HTTPS', status['error'])
                launch.assert_not_called()

    def test_send_missing_url_rejected_without_camera(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_dir, result_dir = self._prepared_environment(Path(tmp))
            with patch.dict(os.environ, {
                'SAFETY_CAMERA_AUTOSTART': '1', 'SAFETY_CAMERA_SEND_ENABLED': '1',
                'SAFETY_CAMERA_ALERT_URL': '', 'SAFETY_CAMERA_SHOW': '0'
            }), patch.object(mod, 'MODEL_DIR', model_dir), patch.object(mod, 'RESULT_DIR', result_dir), \
                 patch.object(mod.subprocess, 'Popen') as launch:
                with TestClient(self.app) as client:
                    self.assertFalse(client.get('/safety/camera/status').json()['running'])
                launch.assert_not_called()

    def test_production_requires_approval_even_if_https(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_dir, result_dir = self._prepared_environment(Path(tmp))
            with patch.dict(os.environ, {
                'SAFETY_CAMERA_AUTOSTART': '1', 'SAFETY_CAMERA_SEND_ENABLED': '1',
                'SAFETY_CAMERA_SEND_MODE': 'production',
                'SAFETY_CAMERA_ALERT_URL': 'https://example.com/api/parking/ai/fire-alerts',
                'SAFETY_CAMERA_ALLOW_PRODUCTION': '0',
                'FIRE_ALERT_TOKEN': 'dummy-do-not-send', 'SAFETY_CAMERA_SHOW': '0'
            }), patch.object(mod, 'MODEL_DIR', model_dir), patch.object(mod, 'RESULT_DIR', result_dir), \
                 patch.object(mod.subprocess, 'Popen') as launch:
                with TestClient(self.app) as client:
                    status = client.get('/safety/camera/status').json()
                    self.assertFalse(status['running'])
                    self.assertIn('SAFETY_CAMERA_ALLOW_PRODUCTION', status['error'])
                launch.assert_not_called()

    def test_production_explicit_approval_uses_production_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_dir, result_dir = self._prepared_environment(Path(tmp))
            class FakeProcess:
                pid = 5511
                def poll(self): return None
            with patch.dict(os.environ, {
                'SAFETY_CAMERA_AUTOSTART': '1', 'SAFETY_CAMERA_SEND_ENABLED': '1',
                'SAFETY_CAMERA_SEND_MODE': 'production',
                'SAFETY_CAMERA_ALERT_URL': 'https://example.com/api/parking/ai/fire-alerts',
                'SAFETY_CAMERA_ALLOW_PRODUCTION': '1',
                'FIRE_ALERT_TOKEN': 'dummy-do-not-send', 'SAFETY_CAMERA_SHOW': '0'
            }), patch.object(mod, 'MODEL_DIR', model_dir), patch.object(mod, 'RESULT_DIR', result_dir), \
                 patch.object(mod.subprocess, 'Popen', return_value=FakeProcess()) as launch, \
                 patch.object(mod, '_stop_tree'):
                with TestClient(self.app) as client:
                    status = client.get('/safety/camera/status').json()
                    self.assertTrue(status['running'])
                    self.assertEqual(status['delivery'], 'PRODUCTION_HTTPS')
                argv = launch.call_args.args[0]
                self.assertIn('--send', argv)
                self.assertIn('--production-camera', argv)
                self.assertIn('--allow-production-records', argv)
                self.assertNotIn('dummy-do-not-send', argv)


if __name__ == '__main__':
    unittest.main()

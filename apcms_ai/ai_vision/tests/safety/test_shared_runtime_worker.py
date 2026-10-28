import tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from ai_vision.safety.shared_runtime_worker import run_shared_worker
from ai_vision.safety.live_fire_smoke import LiveConfig,run_live
from ai_vision.tests.safety.test_live_fire_smoke import FakeModel


class SharedWorkerTests(unittest.TestCase):
    def test_worker_only_uses_shared_input_and_dry_run_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('ai_vision.parking.parking_process_scope.isolate_worker'),patch('ai_vision.safety.live_fire_smoke.run_live',return_value={'status':'STOP_REQUESTED'}) as run,patch('ai_vision.safety.fire_alert_live.delivery_cycle') as cycle:
                run_shared_worker('gate','GATE_A',folder,str(Path(folder)/'out'),False,threading.Event())
            config=run.call_args.args[0]
            self.assertEqual(config.shared_role,'gate');self.assertEqual(config.max_seconds,0)
            self.assertTrue(config.publish_alert_session)
            self.assertFalse(config.show)
            self.assertTrue(callable(run.call_args.kwargs['on_detections']))
            for call in cycle.call_args_list:self.assertNotIn('send',call.kwargs)

    def test_stop_event_exits_live_without_physical_camera_or_frame_read(self):
        with tempfile.TemporaryDirectory() as folder:
            event=threading.Event();event.set();capture=Mock();capture.isOpened.return_value=True
            config=LiveConfig(shared_run_dir=Path(folder),shared_role='gate',shared_camera_id='GATE_A',output_dir=Path(folder)/'out',warmup=False)
            with patch('ai_vision.safety.shared_frame_source.SharedFrameCapture',return_value=capture),patch('ai_vision.safety.live_fire_smoke.cv2.VideoCapture') as physical:
                result=run_live(config,model=FakeModel(),stop_event=event)
            self.assertEqual(result['status'],'STOP_REQUESTED');physical.assert_not_called();capture.read.assert_not_called()

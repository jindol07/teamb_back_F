import os,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from ai_vision.safety.shared_runtime import SharedSafetyRuntime


def simulated_shared_worker(role,camera_id,shared_dir,output_dir,show,stop_event,delivery=None):
    if not stop_event.wait(10):raise RuntimeError('종료 신호 없음')


class SharedRuntimeTests(unittest.TestCase):
    def test_nonzero_child_exit_is_not_hidden_by_normal_shutdown(self):
        self.runtime.state='RUNNING'
        child=Mock();child.is_alive.return_value=False;child.exitcode=1
        self.runtime.processes=[child]
        self.runtime.stop()
        self.assertEqual(self.runtime.state,'FAILED')
        self.assertEqual(self.runtime.reason,'SHARED_SAFETY_CHILD_EXITED')

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.config=dict(frame_export_dir=self.tmp.name,gate_id='GATE_A',parking_id='PARKING_B',preview=False)
        self.parking=SimpleNamespace(load_config=lambda:self.config,run_dir=Path(self.tmp.name)/'current',snapshot=lambda:{'state':'RUNNING'})
        self.environment=patch.dict(os.environ,{'SAFETY_SHARED_AUTOSTART':'true','SAFETY_CAMERA_AUTOSTART':'false','SAFETY_SHARED_SEND_ENABLED':'false'});self.environment.start();self.addCleanup(self.environment.stop)
        self.context=Mock();self.context.Event.return_value=threading.Event()
        def process(**kwargs):
            p=Mock(name=kwargs['name']);p.name=kwargs['name'];p.exitcode=0;p.is_alive.return_value=True
            p.join.side_effect=lambda **kw:setattr(p.is_alive,'return_value',False)
            return p
        self.context.Process.side_effect=process
        self.runtime=SharedSafetyRuntime(self.parking,context=self.context)

    def reader(self,path):
        role=path.stem
        return dict(run_id='current',role=role,camera_id=self.config[role+'_id']),object()

    def test_default_disabled_starts_nothing(self):
        with patch.dict(os.environ,{'SAFETY_SHARED_AUTOSTART':'false'}):
            self.runtime.prepare();self.runtime.start()
        self.assertEqual(self.runtime.state,'DISABLED');self.context.Process.assert_not_called()

    def test_waits_for_parking_and_fresh_frames(self):
        self.runtime.prepare()
        self.parking.snapshot=lambda:{'state':'STARTING'}
        self.runtime.tick();self.context.Process.assert_not_called()
        self.parking.snapshot=lambda:{'state':'RUNNING'}
        with patch('ai_vision.safety.shared_runtime.read_latest',return_value=None):self.runtime.tick()
        self.context.Process.assert_not_called()

    def test_current_run_only_starts_two_and_stops_both(self):
        self.runtime.prepare()
        with patch('ai_vision.safety.shared_runtime.read_latest',side_effect=self.reader):self.runtime.tick();self.runtime.tick()
        self.assertEqual(self.context.Process.call_count,2)
        self.assertEqual(self.runtime.snapshot()['shared_run_id'],'current')
        self.runtime.stop()
        self.assertTrue(self.context.Event.return_value.is_set())
        self.assertEqual(self.runtime.state,'STOPPED')
        self.assertEqual(self.runtime.snapshot()['delivery'],'DRY_RUN_NO_HTTP')

    def test_wrong_run_identity_is_rejected_before_spawn(self):
        self.runtime.prepare()
        with patch('ai_vision.safety.shared_runtime.read_latest',return_value=({'run_id':'old','role':'gate','camera_id':'GATE_A'},object())):
            with self.assertRaises(RuntimeError):self.runtime.tick()
        self.context.Process.assert_not_called()

    def test_direct_camera_or_missing_export_is_rejected(self):
        with patch.dict(os.environ,{'SAFETY_CAMERA_AUTOSTART':'true'}):
            with self.assertRaises(ValueError):self.runtime.prepare()
        self.config.pop('frame_export_dir')
        with self.assertRaises(ValueError):self.runtime.prepare()

    def test_transient_permission_error_does_not_start_or_fail(self):
        self.runtime.prepare()
        with patch('ai_vision.safety.shared_runtime.read_latest',side_effect=PermissionError):self.runtime.tick()
        self.assertEqual(self.runtime.state,'WAITING_FOR_PARKING')

    def test_input_shutdown_and_child_exit_are_not_reported_running(self):
        self.runtime.prepare();self.parking.snapshot=lambda:{'state':'STOPPED'}
        with self.assertRaises(RuntimeError):self.runtime.tick()

    def test_real_spawn_processes_stop_with_owned_event(self):
        runtime=SharedSafetyRuntime(self.parking,worker=simulated_shared_worker)
        runtime.prepare()
        try:
            with patch('ai_vision.safety.shared_runtime.read_latest',side_effect=self.reader):runtime.tick()
            self.assertEqual(len(runtime.processes),2)
        finally:
            runtime.stop()
        self.assertEqual(runtime.state,'STOPPED')
        self.assertTrue(all(not p.is_alive() and p.exitcode==0 for p in runtime.processes))

    def test_sending_is_limited_to_selected_role_and_status_hides_secret(self):
        with patch.dict(os.environ,{'SAFETY_SHARED_SEND_ENABLED':'true','SAFETY_SHARED_ALLOW_TEST':'true',
                                   'SAFETY_SHARED_ALERT_URL':'https://example.test/fire','FIRE_ALERT_TOKEN':'hidden-secret',
                                   'SAFETY_SHARED_SEND_ROLE':'gate'}):
            self.runtime.prepare()
        try:
            with patch('ai_vision.safety.shared_runtime.read_latest',side_effect=self.reader):self.runtime.tick()
            args=[call.kwargs['args'] for call in self.context.Process.call_args_list]
            self.assertEqual(args[0][0],'gate');self.assertIsNotNone(args[0][-1])
            self.assertEqual(args[1][0],'parking');self.assertIsNone(args[1][-1])
            self.assertNotIn('hidden-secret',str(self.runtime.snapshot()))
            self.assertEqual(self.runtime.snapshot()['send_role'],'gate')
        finally:self.runtime.stop()

import asyncio
import importlib.util
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from ai_vision.parking.demo_tools import server_trial
from ai_vision.parking.demo_session import demo_guidance


class ServerTrialTests(unittest.TestCase):
    def controller(self, root):
        helper=root/".demo_helper";helper.mkdir();(helper/"classpath.txt").write_text("unused")
        profile=dict(root=root,scenario="normal",cycles=1,plate_number="91소6408",camera_backend="dshow",gate_camera=1,parking_camera=0)
        path=Path(__file__).resolve().parents[2]/"parking/demo_tools/controller.py"
        spec=importlib.util.spec_from_file_location("isolated_fixture_controller",path)
        module=importlib.util.module_from_spec(spec)
        with patch.dict(os.environ,{"PARKING_DEMO_PROFILE_DIR":str(root),"PARKING_DEMO_RUN_DIR":str(root)}),patch("ai_vision.parking.demo_session.load_demo_profile",return_value=profile):
            spec.loader.exec_module(module)
        module.original_db=module.db
        module.db=Mock(return_value="FIXTURE_COMMITTED=4")
        return module

    def test_fixture_connection_uses_profile_target_instead_of_inherited_db(self):
        with tempfile.TemporaryDirectory() as folder:
            controller=self.controller(Path(folder))
            controller.PROFILE['expected_db_url']='jdbc:oracle:thin:@example.test:1521:xe'
            response=SimpleNamespace(returncode=0, stdout='OK', stderr='')
            with patch.dict(os.environ, {'DB_URL':'jdbc:oracle:thin:@old.test:1521:xe'}), patch.object(controller.subprocess,'run',return_value=response) as run:
                self.assertEqual(controller.original_db('inspect'),'OK')
            env=run.call_args.kwargs['env']
            self.assertEqual(env['DB_URL'],controller.PROFILE['expected_db_url'])
            self.assertEqual(env['DB_URL'],env['CAMERA_E2E_DB_URL'])
            self.assertEqual(env['CAMERA_E2E_CREATE_VEHICLE'],'false')

    def test_auto_start_still_requires_both_cameras_and_empty_check(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);controller=self.controller(root)
            report=controller.report.copy()
            for name in ("gate_started.flag","parking_started.flag"):(root/name).write_text("AUTO")
            prepared,started,phase=controller.update_trial(report,False,None,automatic=True)
            self.assertFalse(prepared);self.assertTrue(phase.startswith("AUTO:"));controller.db.assert_not_called()
            (root/"parking_ready.flag").write_text("EMPTY")
            prepared,started,phase=controller.update_trial(report,False,None,automatic=True)
            self.assertTrue(prepared);controller.db.assert_called_once_with("prepare")
            self.assertTrue((root/"fixture_ready.flag").exists())

    def test_abort_before_ready_never_creates_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);controller=self.controller(root)
            for name in ("gate_started.flag","parking_started.flag","parking_ready.flag","stop_requested.flag"):(root/name).write_text("STOP")
            prepared,_,phase=controller.update_trial(controller.report.copy(),False,None,automatic=True)
            self.assertFalse(prepared);self.assertTrue(phase.startswith("STOP:"));controller.db.assert_not_called()

    def test_server_trial_requires_contained_execution_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);helper=root/".demo_helper";helper.mkdir();(helper/"classpath.txt").write_text("unused")
            with patch.object(server_trial,"load_demo_profile",return_value={"root":root}):
                env={"PARKING_DEMO_PROFILE_DIR":str(root),"PARKING_DEMO_RUN_DIR":str(root/"e2e_manual_aabbccdd")}
                self.assertTrue(server_trial.load_trial_config(env)["delivery_enabled"])
                env["PARKING_DEMO_RUN_DIR"]=str(root.parent/"e2e_manual_aabbccdd")
                with self.assertRaises(ValueError):server_trial.load_trial_config(env)

    def test_trial_app_does_not_start_workers_or_include_fire_on_import(self):
        app=server_trial.create_trial_app()
        self.assertEqual(app.state.parking_runtime.processes,[])
        paths={route.path for route in app.routes}
        self.assertIn("/vision/parking/runtime",paths)
        self.assertFalse(any(path.startswith("/safety") for path in paths))

    def test_trial_worker_uses_same_stop_signal_and_auto_start(self):
        runner=Mock();stop=threading.Event();heartbeat=SimpleNamespace(value=0)
        with patch("ai_vision.parking.parking_process_scope.isolate_worker"),patch.object(server_trial.importlib,"import_module",return_value=runner),patch.dict(os.environ,{},clear=True):
            server_trial.trial_worker("gate",{"profile_dir":"profile"},"run",stop,heartbeat)
        self.assertIs(runner.main.call_args.kwargs["stop_event"],stop)
        self.assertTrue(runner.main.call_args.kwargs["autostart"])
        runner.main.call_args.kwargs["on_frame"]()
        self.assertGreater(heartbeat.value,0)

    def test_server_guidance_never_asks_for_space_or_q(self):
        auto=demo_guidance("AUTO: EMPTY CHECK / KEEP EMPTY",auto_stop=True)
        done=demo_guidance("4 DONE",auto_stop=True)
        self.assertIn("누르지",auto[1][0])
        self.assertIn("자동 종료",done[1][0])
        self.assertIn("Q를 누르지",done[2][0])
        self.assertIn("Q를 누르세요",demo_guidance("4 DONE")[1][0])

    def test_done_requests_server_shutdown_after_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=SimpleNamespace(run_dir=Path(folder),state="RUNNING")
            server=SimpleNamespace(should_exit=False)
            controller=SimpleNamespace(report={},update_trial=lambda *a,**kw:(True,1,"4 DONE"))
            clock=[1.0]
            async def pause(*args):clock[0]+=1
            async def call(function,*args,**kwargs):return function(*args,**kwargs)
            report={}
            with patch.object(server_trial.importlib,"import_module",return_value=controller),patch.object(server_trial.time,"monotonic",side_effect=lambda:clock[0]),patch.object(server_trial.asyncio,"sleep",side_effect=pause),patch.object(server_trial.asyncio,"to_thread",side_effect=call):
                result=asyncio.run(server_trial.monitor_trial(runtime,server,report))
            self.assertIs(result[0],controller);self.assertTrue(result[1])
            self.assertTrue(server.should_exit)
            self.assertTrue(report["automatic_shutdown_after_done"])

    def test_monitor_failure_requests_shutdown_and_preserves_cleanup_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=SimpleNamespace(run_dir=Path(folder),state="FAILED",reason="CHILD_EXITED")
            server=SimpleNamespace(should_exit=False);report={}
            controller=SimpleNamespace(report={})
            with patch.object(server_trial.importlib,"import_module",return_value=controller),patch.dict(os.environ,{},clear=True):
                asyncio.run(server_trial.monitor_trial(runtime,server,report))
            self.assertTrue(server.should_exit)
            self.assertEqual(report["controller_error_type"],"RuntimeError")
            self.assertTrue((Path(folder)/"stop_requested.flag").exists())

    def test_auto_gate_checks_camera_and_first_frame_before_ready(self):
        from ai_vision.parking.demo_tools.gate_runner import automatic_gate_ready
        view=Mock();capture=Mock();capture.isOpened.return_value=False
        with self.assertRaises(RuntimeError):automatic_gate_ready(view,capture)
        capture.read.assert_not_called();view.assert_not_called()
        capture.isOpened.return_value=True;capture.read.return_value=(False,None)
        with self.assertRaises(RuntimeError):automatic_gate_ready(view,capture)
        view.assert_not_called()

    def test_auto_gate_cancellation_is_not_start_confirmation(self):
        from ai_vision.parking.demo_tools.gate_runner import automatic_gate_ready
        frame=object();capture=Mock();capture.isOpened.return_value=True;capture.read.return_value=(True,frame)
        view=Mock(return_value=False)
        self.assertFalse(automatic_gate_ready(view,capture))
        view.assert_called_once_with(frame)

    def test_success_requires_fixture_and_automatic_server_shutdown(self):
        report=dict(success=True,completion_checks={"fixture_cleaned":True},automatic_shutdown_after_done=True,runtime_final_state={"state":"STOPPED","reason":None})
        self.assertTrue(server_trial.complete_server_result(report)["success"])
        for change in ({"success":False},{"automatic_shutdown_after_done":False},{"runtime_final_state":{"state":"FAILED","reason":"FORCED_STOP_REQUIRES_REVIEW"}},{"server_error_type":"TimeoutError"}):
            result=server_trial.complete_server_result(dict(success=True,completion_checks={"fixture_cleaned":True},automatic_shutdown_after_done=True,runtime_final_state={"state":"STOPPED","reason":None})|change)
            self.assertFalse(result["success"])
            self.assertTrue(result["incomplete_reasons"])

    def test_incomplete_fixture_cannot_be_reclassified_as_server_success(self):
        report=dict(success=False,automatic_shutdown_after_done=True,runtime_final_state={"state":"STOPPED","reason":None})
        result=server_trial.complete_server_result(report)
        self.assertFalse(result["success"])
        self.assertIn("fixture_result_verified",result["incomplete_reasons"])

    def test_cleanup_waits_for_in_progress_fixture_preparation(self):
        lock=threading.RLock();started=threading.Event();release=threading.Event();cleaned=threading.Event();order=[]
        def prepare():
            order.append("prepare_started");started.set();release.wait(3);order.append("prepare_finished")
        def cleanup():order.append("cleanup");cleaned.set()
        first=threading.Thread(target=server_trial.run_locked,args=(lock,prepare))
        second=threading.Thread(target=server_trial.run_locked,args=(lock,cleanup))
        first.start()
        try:
            self.assertTrue(started.wait(1));second.start()
            self.assertFalse(cleaned.wait(.05))
        finally:
            release.set();first.join(3)
            if second.ident is not None:second.join(3)
        self.assertEqual(order,["prepare_started","prepare_finished","cleanup"])

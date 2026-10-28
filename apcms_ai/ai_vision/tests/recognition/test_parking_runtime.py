import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai_vision.parking.parking_runtime import ParkingRuntime, install_parking_runtime
from ai_vision.parking.parking_runtime_config import load_runtime_config
from ai_vision.recognition.run_live_gate import execute
from ai_vision.recognition.live_gate_session import LiveGateSession
from ai_vision.tests.recognition.test_run_live_gate import FakeCapture


def _fake_camera_worker(role, config, run_dir, stop_event, heartbeat):
    import time
    while not stop_event.wait(.05):
        heartbeat.value=time.monotonic()


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        # 단위 검사는 현재 테스트 프로세스의 세션을 바꾸지 않습니다.
        isolation=patch("ai_vision.parking.parking_process_scope.isolate_worker")
        isolation.start();self.addCleanup(isolation.stop)

    def test_disabled_does_not_read_config_or_spawn(self):
        with patch.dict("os.environ", {}, clear=True), patch("pathlib.Path.read_text") as read:
            runtime = ParkingRuntime()
            runtime.start()
            self.assertEqual(runtime.snapshot()["state"], "DISABLED")
            read.assert_not_called()
            runtime.stop()

    def test_invalid_flag_and_missing_config(self):
        for env in ({"PARKING_RUNTIME_ENABLED":"yes"}, {"PARKING_RUNTIME_ENABLED":"true"}):
            with self.assertRaises(ValueError): load_runtime_config(env)

    def test_status_route_has_no_secret_or_path(self):
        app = FastAPI()
        with patch.dict("os.environ", {}, clear=True):
            install_parking_runtime(app)
            with TestClient(app) as client:
                data = client.get("/vision/parking/runtime").json()
        self.assertEqual(data["state"], "DISABLED")
        self.assertFalse(data["inference_ready_verified"])
        self.assertNotIn("config", data)

    def test_duplicate_start_rejected(self):
        runtime = ParkingRuntime(); runtime.state = "STARTING"
        with self.assertRaises(RuntimeError): runtime.start()

    def test_graceful_stop_sets_signal_before_join(self):
        runtime = ParkingRuntime(); runtime.state="RUNNING"
        runtime.stop_event=threading.Event()
        child=Mock(); child.is_alive.return_value=False
        child.join.side_effect=lambda **kw:self.assertTrue(runtime.stop_event.is_set())
        runtime.processes=[child]; runtime.lease=Mock()
        runtime.stop()
        self.assertEqual(runtime.state,"STOPPED")
        child.terminate.assert_not_called()
        self.assertIsNone(runtime.lease)

    def test_forced_stop_requires_review(self):
        runtime=ParkingRuntime(); runtime.state="RUNNING"
        child=Mock(); child.is_alive.return_value=True
        runtime.processes=[child]
        with patch("ai_vision.parking.parking_runtime.terminate_worker_tree",return_value=False) as terminate:
            runtime.stop()
        self.assertEqual(runtime.reason,"PROCESS_STILL_ALIVE")
        terminate.assert_called_once_with(child)

    def test_child_exit_stops_peer(self):
        runtime=ParkingRuntime();runtime.state="RUNNING"
        child=Mock();child.is_alive.return_value=False;runtime.processes=[child]
        runtime._watch()
        self.assertEqual(runtime.reason,"CHILD_EXITED")
        self.assertTrue(runtime.closing.is_set())

    def test_runtime_loop_obeys_shutdown_without_deadline(self):
        capture=FakeCapture([]);stop=threading.Event();stop.set()
        report=execute(capture, Mock(), LiveGateSession("TEST","ENTRY"),
                       runtime_mode=True,stop_event=stop)
        self.assertEqual(report["stop_reason"],"SERVER_SHUTDOWN")
        self.assertEqual(capture.reads,0)
        self.assertTrue(capture.released)

    def test_partial_process_start_failure_cleans_up(self):
        runtime=ParkingRuntime()
        with tempfile.TemporaryDirectory() as folder, patch("ai_vision.parking.parking_runtime.load_runtime_config",return_value={"output_dir":folder}), patch("ai_vision.parking.parking_runtime.socket.socket") as socket, patch("ai_vision.parking.parking_runtime.multiprocessing.get_context") as context:
            child=Mock(); child.is_alive.return_value=False
            context.return_value.Process.return_value=child
            child.start.side_effect=[None,RuntimeError("failure")]
            with self.assertRaises(RuntimeError): runtime.start()
            self.assertEqual(runtime.state,"FAILED")
            socket.return_value.close.assert_called_once()

    def test_no_progress_is_failed(self):
        runtime=ParkingRuntime();runtime.started_at=0
        runtime.heartbeats=[SimpleNamespace(value=0)]
        child=Mock();child.is_alive.return_value=True;runtime.processes=[child]
        with patch("ai_vision.parking.parking_runtime.time.monotonic",return_value=181),patch.object(runtime,"stop") as stop:
            runtime._watch()
        self.assertEqual(runtime.reason,"FRAME_PROGRESS_TIMEOUT")
        stop.assert_called_once()

    def test_existing_lifespan_is_preserved(self):
        from contextlib import asynccontextmanager
        events=[]
        @asynccontextmanager
        async def original(app):
            events.append("existing_start")
            yield
            events.append("existing_stop")
        app=FastAPI(lifespan=original)
        with patch.dict("os.environ",{},clear=True):
            install_parking_runtime(app)
            with TestClient(app):
                self.assertEqual(events,["existing_start"])
        self.assertEqual(events,["existing_start","existing_stop"])

    def test_shared_fire_camera_rejected_before_models(self):
        import json
        config=dict(gate_camera=1,parking_camera=0,gate_id="GATE",parking_id="PARK",down_direction="ENTRY",
                    gate_config="gate.json",spaces_config="spaces.json",reference="empty.png",
                    allowed_codes=["1F-A01"],boot_context_url="http://localhost:81/alpharking/admin",output_dir="out")
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"config.json";path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,"겹칩니다"):
                load_runtime_config({"PARKING_RUNTIME_ENABLED":"true","PARKING_RUNTIME_CONFIG":str(path),"SAFETY_CAMERA_AUTOSTART":"true"})

    def test_runtime_keeps_processing_after_demo_time_limit(self):
        from datetime import datetime, timezone
        from ai_vision.recognition.live_gate_clock import LiveGateClock
        capture=FakeCapture([object(),object()]); stop=threading.Event()
        clock=LiveGateClock(datetime(2026,1,1,tzinfo=timezone.utc),0)
        session=LiveGateSession("TEST","ENTRY",clock=clock)
        processor=Mock();processor.process.return_value=[]
        report=execute(capture,processor,session,seconds=20,monotonic_reader=iter([1,301]).__next__,
                       stop_event=stop,runtime_mode=True,on_frame=lambda: stop.set() if processor.process.call_count==2 else None)
        self.assertEqual(report["stop_reason"],"SERVER_SHUTDOWN")
        self.assertEqual(processor.process.call_count,2)

    def test_worker_gate_uses_runtime_and_same_handoff_root(self):
        from ai_vision.parking.parking_runtime_worker import run_worker
        config=dict(delivery_enabled=True,gate_camera=1,gate_id="GATE",down_direction="ENTRY",gate_config="gate.json",boot_context_url="http://localhost:81/alpharking/admin")
        with patch.dict("os.environ",{"AI_OCCUPANCY_API_KEY":"test-key"},clear=True),patch("ai_vision.recognition.run_live_gate.main") as gate:
            run_worker("gate",config,"run",threading.Event(),SimpleNamespace(value=0))
        args=gate.call_args.args[0]
        self.assertNotIn("--preview",args)
        self.assertTrue(gate.call_args.kwargs["runtime_mode"])
        self.assertIn("--single-vehicle-handoff",args)

    def test_worker_parking_has_no_preview_or_fixture_db(self):
        from ai_vision.parking.parking_runtime_worker import run_worker
        config=dict(delivery_enabled=True,parking_camera=0,parking_id="PARK",reference="empty.png",spaces_config="spaces.json",allowed_codes=["1F-A01"],boot_context_url="http://localhost:81/alpharking/admin")
        with patch.dict("os.environ",{"AI_OCCUPANCY_API_KEY":"test-key"},clear=True),patch("ai_vision.parking.run_parking_camera.run_camera",return_value={"status":"STOPPED"}) as parking:
            run_worker("parking",config,"run",threading.Event(),SimpleNamespace(value=0))
        kw=parking.call_args.kwargs
        self.assertFalse(kw["preview"])
        self.assertTrue(kw["runtime_mode"])
        self.assertEqual(kw["handoff_path"],Path("run/gate/single_vehicle_handoff.json"))
        self.assertNotIn("enable_space_release_http",kw)

    def test_valid_config_checks_assets_without_http_or_camera(self):
        import json
        import cv2
        import numpy as np
        from ai_vision.tests.recognition.test_live_gate_processor import CONFIG
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"gate.json").write_text(json.dumps(CONFIG))
            (root/"spaces.json").write_text(json.dumps({"image_width":80,"image_height":80,"spaces":[{"id":"A-01","points":[[5,5],[35,5],[35,70],[5,70]]}]}))
            cv2.imwrite(str(root/"empty.png"),np.zeros((80,80,3),dtype=np.uint8))
            config=dict(gate_camera=1,parking_camera=0,gate_id="GATE",parking_id="PARK",down_direction="ENTRY",gate_config="gate.json",spaces_config="spaces.json",reference="empty.png",allowed_codes=["1F-A01"],boot_context_url="http://localhost:81/alpharking/admin",output_dir="out")
            path=root/"runtime.json";path.write_text(json.dumps(config))
            env={"PARKING_RUNTIME_ENABLED":"true","PARKING_RUNTIME_CONFIG":str(path),"SAFETY_CAMERA_AUTOSTART":"false","AI_OCCUPANCY_API_KEY":"test-key"}
            with patch("cv2.VideoCapture") as camera,patch("requests.Session") as http:
                checked=load_runtime_config(env)
                self.assertEqual(checked["reference"],str(root/"empty.png"))
                self.assertFalse((root/"out").exists())
                camera.assert_not_called();http.assert_not_called()
            config["frame_export_dir"]="shared_frames"
            path.write_text(json.dumps(config))
            exported=load_runtime_config(env)
            self.assertEqual(exported["frame_export_fps"],2)
            self.assertEqual(exported["frame_export_dir"],str(root/"shared_frames"))
            self.assertFalse((root/"shared_frames").exists())
            (root/"not_a_folder").write_text("file")
            config["frame_export_dir"]="not_a_folder";path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,"폴더"):
                load_runtime_config(env)
            config["frame_export_dir"]="shared_frames"
            for fps in (True,0,11,float("nan")):
                config["frame_export_fps"]=fps;path.write_text(json.dumps(config))
                with self.assertRaises(ValueError):load_runtime_config(env)
            config.pop("frame_export_fps")
            path.write_text(json.dumps(config))
            self.assertFalse(checked["delivery_enabled"])
            env.pop("AI_OCCUPANCY_API_KEY")
            self.assertFalse(load_runtime_config(env)["delivery_enabled"])
            config["delivery_enabled"]=True;path.write_text(json.dumps(config))
            with self.assertRaises(ValueError): load_runtime_config(env)
            config["delivery_enabled"]="false";path.write_text(json.dumps(config))
            with self.assertRaises(ValueError): load_runtime_config(env)
            config["delivery_enabled"]=False
            config["allowed_codes"]=["999F-Z01"];path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,"임시"):
                load_runtime_config(env)

    def test_real_spawn_lifecycle_and_duplicate_host_lock(self):
        import time
        runtime=ParkingRuntime();duplicate=ParkingRuntime()
        with tempfile.TemporaryDirectory() as folder,patch("ai_vision.parking.parking_runtime.load_runtime_config",return_value={"output_dir":folder}),patch("ai_vision.parking.parking_runtime.run_worker",_fake_camera_worker):
            try:
                runtime.start()
                deadline=time.monotonic()+10
                while runtime.state=="STARTING" and time.monotonic()<deadline:
                    time.sleep(.05)
                self.assertEqual(runtime.state,"RUNNING")
                with self.assertRaises(RuntimeError): duplicate.start()
                self.assertEqual(duplicate.reason,"START_FAILED")
            finally:
                runtime.stop();duplicate.stop()
            self.assertTrue(all(not p.is_alive() for p in runtime.processes))
            self.assertEqual(runtime.state,"STOPPED")

    def test_parking_runtime_has_no_demo_deadline_and_releases_camera(self):
        import json
        import itertools
        import cv2
        import numpy as np
        from ai_vision.parking.run_parking_camera import run_camera
        frame=np.zeros((80,80,3),dtype=np.uint8)
        config={"image_width":80,"image_height":80,"spaces":[{"id":"A-01","points":[[5,5],[35,5],[35,70],[5,70]]}]}
        stop=threading.Event()
        camera=Mock();camera.isOpened.return_value=True;camera.read.return_value=(True,frame)
        ticks=itertools.count(0,100)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);cv2.imwrite(str(root/"empty.png"),frame)
            (root/"spaces.json").write_text(json.dumps(config))
            with patch("ai_vision.parking.run_parking_camera.open_camera",return_value=camera),patch("ai_vision.parking.run_parking_camera.time.monotonic",side_effect=lambda:next(ticks)):
                report=run_camera(root/"empty.png",root/"spaces.json",root/"run",seconds=1,preview=False,runtime_mode=True,stop_event=stop,on_frame=stop.set)
        self.assertEqual(report["status"],"STOPPED")
        self.assertEqual(report["read_frames"],1)
        camera.release.assert_called_once()

    def test_config_checker_never_starts_runtime_or_camera(self):
        import io
        import contextlib
        from ai_vision.parking.parking_runtime_config import main
        with patch("ai_vision.parking.parking_runtime_config.load_runtime_config",return_value={"gate_camera":1,"parking_camera":0,"allowed_codes":["1F-A01"]}),patch("ai_vision.parking.parking_runtime.ParkingRuntime.start") as start,patch("cv2.VideoCapture") as camera,contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--config","unused.json"]),0)
        self.assertIn("PRECHECK_OK",output.getvalue())
        start.assert_not_called();camera.assert_not_called()

    def test_config_checker_reports_conflict_without_starting(self):
        import io
        import contextlib
        from ai_vision.parking.parking_runtime_config import main
        with patch("ai_vision.parking.parking_runtime_config.load_runtime_config",side_effect=ValueError("카메라 충돌")),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--config","unused.json"]),1)
        self.assertIn("PRECHECK_BLOCKED",output.getvalue())

    def test_observe_only_gate_never_enables_delivery_or_handoff(self):
        from ai_vision.parking.parking_runtime_worker import run_worker
        config=dict(gate_camera=1,gate_id="GATE",down_direction="ENTRY",gate_config="gate.json",boot_context_url="http://localhost:81/alpharking/admin")
        with patch.dict("os.environ",{"AI_OCCUPANCY_API_KEY":"unused-key"}),patch("ai_vision.recognition.run_live_gate.main") as gate:
            run_worker("gate",config,"run",threading.Event(),SimpleNamespace(value=0))
        args=gate.call_args.args[0]
        self.assertNotIn("--enable-http",args)
        self.assertNotIn("--single-vehicle-handoff",args)
        self.assertNotIn("--boot-context-url",args)

    def test_observe_only_parking_never_uses_boot_or_entry_identity(self):
        from ai_vision.parking.parking_runtime_worker import run_worker
        config=dict(parking_camera=0,parking_id="PARK",reference="empty.png",spaces_config="spaces.json",allowed_codes=["1F-A01"],boot_context_url="http://localhost:81/alpharking/admin")
        with patch.dict("os.environ",{"AI_OCCUPANCY_API_KEY":"unused-key"}),patch("ai_vision.parking.run_parking_camera.run_camera",return_value={"status":"STOPPED"}) as parking:
            run_worker("parking",config,"run",threading.Event(),SimpleNamespace(value=0))
        kw=parking.call_args.kwargs
        self.assertFalse(kw["enable_http"])
        self.assertFalse(kw["enable_space_http"])
        self.assertEqual(kw["allowed_codes"],())
        self.assertIsNone(kw["handoff_path"])

    def test_vision_only_app_has_same_disabled_runtime_lifecycle(self):
        from ai_vision.app import create_app
        with patch.dict("os.environ",{},clear=True):
            app=create_app()
            with TestClient(app) as client:
                reply=client.get("/vision/parking/runtime")
        self.assertEqual(reply.json()["delivery"],"OBSERVE_ONLY")
        self.assertEqual(reply.json()["state"],"DISABLED")

    def test_runtime_preview_is_opt_in_and_does_not_enable_http(self):
        from ai_vision.parking.parking_runtime_worker import run_worker
        config=dict(gate_camera=1,gate_id="GATE",down_direction="ENTRY",gate_config="gate.json",boot_context_url="http://localhost:81/alpharking/admin",preview=True)
        with patch("ai_vision.recognition.run_live_gate.main") as gate:
            run_worker("gate",config,"run",threading.Event(),SimpleNamespace(value=0))
        args=gate.call_args.args[0]
        self.assertIn("--preview",args)
        self.assertNotIn("--enable-http",args)

    def test_gate_runtime_preview_skips_space_wait(self):
        import json,io,contextlib
        from ai_vision.recognition.run_live_gate import main
        from ai_vision.tests.recognition.test_live_gate_processor import CONFIG
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/"gate.json").write_text(json.dumps(CONFIG))
            with patch("ai_vision.recognition.run_live_gate.LiveGateProcessor"),patch("ai_vision.camera_runtime.open_camera"),patch("ai_vision.recognition.preview_gate_config.LiveGatePreview") as preview,patch("ai_vision.recognition.run_live_gate.execute",return_value={"status":"STOPPED","http_enabled":False,"captured_frames":0,"processed_passages":0,"request_attempts":0}),contextlib.redirect_stdout(io.StringIO()):
                main(["--preview","--camera-id","GATE","--down-direction","ENTRY","--config",str(root/"gate.json"),"--output-dir",str(root/"run")],runtime_mode=True,stop_event=threading.Event())
            preview.return_value.wait_until_ready.assert_not_called()

    def test_terminal_state_is_persisted_without_secrets(self):
        import json
        runtime=ParkingRuntime();runtime.state="RUNNING"
        with tempfile.TemporaryDirectory() as folder:
            runtime.run_dir=Path(folder)
            runtime.stop()
            saved=json.loads((Path(folder)/"runtime_state.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["state"],"STOPPED")
        self.assertNotIn("api_key",saved)
        self.assertNotIn("config",saved)
        self.assertNotIn("plate_number",saved)

    def test_journal_failure_stops_start_before_camera_processes(self):
        runtime=ParkingRuntime()
        with tempfile.TemporaryDirectory() as folder,patch("ai_vision.parking.parking_runtime.load_runtime_config",return_value={"output_dir":folder}),patch("ai_vision.parking.parking_runtime.socket.socket"),patch("ai_vision.parking.parking_runtime.write_json_atomic",side_effect=PermissionError),patch("ai_vision.parking.parking_runtime.multiprocessing.get_context") as context:
            with self.assertRaises(RuntimeError):runtime.start()
        context.return_value.Process.assert_not_called()
        self.assertTrue(runtime.snapshot()["state_record_failed"])
        self.assertEqual(runtime.reason,"STATE_RECORD_FAILED")

    def test_unconfirmed_tree_cleanup_remains_failure(self):
        runtime=ParkingRuntime();runtime.state="RUNNING"
        child=Mock();child.is_alive.side_effect=[True,False];runtime.processes=[child]
        with patch("ai_vision.parking.parking_runtime.terminate_worker_tree",return_value=False):runtime.stop()
        self.assertEqual(runtime.reason,"TREE_CLEANUP_UNCONFIRMED")

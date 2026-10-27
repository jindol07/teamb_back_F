import multiprocessing
from pathlib import Path
import tempfile
import time
import unittest
import numpy as np
from ai_vision.parking.frame_exchange import FramePublisher, read_latest


def consume(path, result):
    value=read_latest(path,max_age=30)
    result.put((value[0]["camera_id"],value[1].tolist()) if value else None)


class FrameExchangeTests(unittest.TestCase):
    def wait_frame(self,path):
        until=time.monotonic()+3
        while time.monotonic()<until:
            value=read_latest(path)
            if value is not None:return value
            time.sleep(.01)
        self.fail("프레임 전달 시간 초과")

    def test_copy_cross_process_close(self):
        with tempfile.TemporaryDirectory() as directory:
            pub=FramePublisher(directory,"gate","A_GATE","run-one")
            try:
                image=np.arange(36,dtype=np.uint8).reshape(3,4,3)
                expected=image.copy()
                pub.submit(image,time.monotonic());image[:]=0
                meta,frame=self.wait_frame(pub.path)
                np.testing.assert_array_equal(frame,expected)
                self.assertEqual(meta["run_id"],"run-one")
                ctx=multiprocessing.get_context("spawn");result=ctx.Queue()
                process=ctx.Process(target=consume,args=(str(pub.path),result));process.start()
                try:answer=result.get(timeout=15)
                finally:
                    process.join(timeout=3)
                    if process.is_alive():process.terminate();process.join()
                self.assertEqual(answer,("A_GATE",expected.tolist()))
                result.close()
            finally:pub.close()
            self.assertIsNone(read_latest(pub.path))

    def test_missing_stale_rate_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(read_latest(Path(directory)/"missing"))
            pub=FramePublisher(directory,"parking","B","run",fps=2)
            try:
                frame=np.ones((2,2,3),dtype=np.uint8)
                pub.submit(frame,time.monotonic()-20)
                until=time.monotonic()+2
                while not pub.path.exists() and time.monotonic()<until:time.sleep(.01)
                self.assertIsNone(read_latest(pub.path))
                pub.submit(frame,time.monotonic());self.assertEqual(pub.sequence,1)
            finally:pub.close()

    def test_two_cameras(self):
        with tempfile.TemporaryDirectory() as directory:
            pubs=[FramePublisher(directory,role,role,"run") for role in ("gate","parking")]
            try:
                for i,pub in enumerate(pubs):pub.submit(np.full((2,2,3),i,dtype=np.uint8),time.monotonic())
                for i,pub in enumerate(pubs):
                    meta,frame=self.wait_frame(pub.path)
                    self.assertEqual(meta["role"],pub.base["role"])
                    self.assertEqual(int(frame[0,0,0]),i)
            finally:
                for pub in pubs:pub.close()

    def test_invalid_corrupt(self):
        with tempfile.TemporaryDirectory() as directory:
            for fps in (0,11,True,float("nan")):
                with self.assertRaises(ValueError):FramePublisher(directory,"gate","A","run",fps)
            path=Path(directory)/"bad";path.write_bytes(b"bad")
            with self.assertRaises(ValueError):read_latest(path)

    def test_worker_wires_export_and_closes_on_failure(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import threading
        from ai_vision.parking.parking_runtime_worker import run_worker
        config=dict(frame_export_dir="frames",gate_id="A",delivery_enabled=False,
            gate_camera=1,down_direction="ENTRY",gate_config="gate.json")
        with patch("ai_vision.parking.parking_process_scope.isolate_worker"), patch("ai_vision.parking.frame_exchange.FramePublisher") as factory, patch("ai_vision.recognition.run_live_gate.main",side_effect=RuntimeError("test")) as main:
            with self.assertRaises(RuntimeError):
                run_worker("gate",config,"run-one",threading.Event(),SimpleNamespace(value=0))
            self.assertIs(main.call_args.kwargs["on_raw_frame"],factory.return_value.submit)
            factory.return_value.close.assert_called_once()

    def test_malformed_metadata_never_reaches_consumer(self):
        import json, struct
        from ai_vision.parking.frame_exchange import MAGIC
        metadata=dict(version=1, role="gate", camera_id="A", run_id="run", sequence=1,
            status="FRAME", published_at_utc="2026-10-27T00:00:00+00:00",
            shape=[1,1,3], dtype="uint8", color="BGR", captured_monotonic=time.monotonic())
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"gate.frame"
            for field,value in [("version",True),("camera_id",""),("run_id",None),
                ("sequence",True),("sequence",-1),("role","other"),("shape",{}),
                ("published_at_utc","2026-10-27T00:00:00"),("captured_monotonic",True)]:
                with self.subTest(field=field,value=value):
                    header=json.dumps(dict(metadata,**{field:value})).encode()
                    path.write_bytes(MAGIC+struct.pack("!I",len(header))+header+b"123")
                    with self.assertRaises(ValueError):read_latest(path)
            for value in ([],None,1):
                header=json.dumps(value).encode();path.write_bytes(MAGIC+struct.pack("!I",len(header))+header)
                with self.assertRaises(ValueError):read_latest(path)

    def test_invalid_capture_and_identity_rejected_before_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):FramePublisher(directory,"gate","","run")
            pub=FramePublisher(directory,"gate","A","run")
            try:
                for frame,stamp in [(np.zeros((0,1,3),dtype=np.uint8),time.monotonic()),
                    (np.zeros((1,1,3),dtype=np.uint8),float("nan"))]:
                    with self.assertRaises(ValueError):pub.submit(frame,stamp)
                self.assertEqual(pub.sequence,0)
            finally:pub.close()

    def test_worker_isolates_before_publisher_thread(self):
        from unittest.mock import patch, Mock
        from types import SimpleNamespace
        import threading
        from ai_vision.parking.parking_runtime_worker import run_worker
        order=Mock()
        with patch("ai_vision.parking.parking_process_scope.isolate_worker",side_effect=lambda:order("isolate")), patch("ai_vision.parking.frame_exchange.FramePublisher",side_effect=lambda *a:order("publisher")), patch("ai_vision.parking.parking_runtime_worker._run_worker"):
            run_worker("gate",dict(frame_export_dir="frames",gate_id="A"),"run",threading.Event(),SimpleNamespace(value=0))
        self.assertEqual([c.args[0] for c in order.call_args_list],["isolate","publisher"])

    def test_real_safety_receiver_separates_and_deduplicates(self):
        from ai_vision.safety.shared_frame_source import SharedFrameCapture
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory)/"shared-run";run.mkdir()
            publishers=[FramePublisher(run,role,camera,"shared-run") for role,camera in [("gate","A_GATE"),("parking","B_PARK")]]
            ticks=[0.0]
            def sleep(seconds):ticks[0]+=seconds
            try:
                receivers=[]
                for i,pub in enumerate(publishers):
                    pub.submit(np.full((3,4,3),i+1,dtype=np.uint8),time.monotonic())
                    self.wait_frame(pub.path)
                    receiver=SharedFrameCapture(run,pub.base["role"],pub.base["camera_id"],max_age=3,max_silence=4,reader=lambda path,max_age:read_latest(path,max_age=30),clock=lambda:ticks[0],sleeper=sleep)
                    receivers.append(receiver)
                    ok,frame=receiver.read();self.assertTrue(ok)
                    self.assertEqual(int(frame[0,0,0]),i+1)
                    self.assertEqual(receiver.read(),(False,None))
                    self.assertEqual(receiver.last_reason,"INPUT_STALE")
                wrong=SharedFrameCapture(run,"gate","B_PARK",max_age=3,max_silence=4,reader=lambda path,max_age:read_latest(path,max_age=30),clock=lambda:ticks[0],sleeper=sleep)
                self.assertEqual(wrong.read(),(False,None))
                self.assertEqual(wrong.last_reason,"IDENTITY_MISMATCH")
                publishers[0].close()
                self.assertEqual(receivers[0].read(),(False,None))
                receivers[1].release()
                self.assertFalse(receivers[1].isOpened())
            finally:
                for pub in publishers:pub.close()

    def test_real_safety_pipeline_uses_published_pixels_without_camera(self):
        from unittest.mock import patch
        from ai_vision.safety.live_fire_smoke import LiveConfig, run_live
        from ai_vision.tests.safety.test_live_fire_smoke import FakeModel
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);run=root/"pipeline-run";run.mkdir()
            pub=FramePublisher(run,"parking","B_PARK","pipeline-run",fps=10)
            image=np.full((32,40,3),7,dtype=np.uint8)
            owner=self
            class Model(FakeModel):
                def predict(self,**kwargs):
                    np.testing.assert_array_equal(kwargs["source"],image)
                    result=super().predict(**kwargs)
                    if len(self.calls)<3:
                        pub.last=-float("inf")
                        pub.submit(image,time.monotonic())
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            sample=read_latest(pub.path)
                            if sample is not None and sample[0]["sequence"]==pub.sequence:break
                            time.sleep(.01)
                        else:owner.fail("다음 공유 표본 대기 초과")
                    return result
            try:
                pub.submit(image,time.monotonic());self.wait_frame(pub.path)
                model=Model()
                config=LiveConfig(shared_run_dir=run,shared_role="parking",shared_camera_id="B_PARK",interval=.001,max_frames=3,max_seconds=10,output_dir=root/"fire-results")
                with patch("cv2.VideoCapture",side_effect=AssertionError("공유 모드에서 장치를 열면 안 됩니다")) as camera:
                    report=run_live(config,model=model)
                    camera.assert_not_called()
                self.assertEqual(report["status"],"MAX_FRAMES")
                self.assertEqual(report["captured_frames"],3)
                self.assertEqual(report["inference_samples"],3)
                self.assertEqual(report["suspected_events"],1)
                self.assertEqual(report["source_name"],"parking.B_PARK")
                self.assertEqual(report["camera_open_attempts"],0)
                self.assertEqual(report["camera_reconnect_attempts"],0)
            finally:pub.close()

    def test_windows_read_lock_retries_atomic_replace(self):
        from unittest.mock import patch
        import os
        with tempfile.TemporaryDirectory() as directory:
            pub=FramePublisher(directory,"gate","A","run")
            try:
                replace=os.replace;attempts=[]
                def locked_then_replace(source,target):
                    attempts.append(1)
                    if len(attempts)<=2:raise PermissionError("reader lock")
                    return replace(source,target)
                with patch("ai_vision.parking.frame_exchange.os.replace",side_effect=locked_then_replace):
                    pub.submit(np.ones((2,2,3),dtype=np.uint8),time.monotonic())
                    meta,frame=self.wait_frame(pub.path)
                    self.assertEqual(meta["sequence"],1)
                    self.assertEqual(len(attempts),3)
                self.assertFalse(pub.path.with_suffix(".tmp").exists())
            finally:pub.close()

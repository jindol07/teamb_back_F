"""A/B 파일 공유 입력 계약. 카메라·웹·모델 접속 없이 실행."""
import tempfile
import unittest
from pathlib import Path
from ai_vision.safety.shared_frame_source import SharedFrameCapture


class FakeFrame:
    size = 9


class SharedFrameSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "session-one"
        self.folder.mkdir()
        self.t = [100.0]

    def sleep(self, seconds):
        self.t[0] += seconds

    def clock(self):
        return self.t[0]

    def meta(self, seq=1, role="gate", camera_id="A_GATE", run_id="session-one"):
        return dict(role=role, camera_id=camera_id, run_id=run_id, sequence=seq, status="FRAME")

    def make(self, reader, role="gate", camera_id="A_GATE", **kwargs):
        return SharedFrameCapture(self.folder, role, camera_id, reader=reader,
                                 clock=self.clock, sleeper=self.sleep, max_age=1,
                                 max_silence=2, poll=0.1, **kwargs)

    def test_frame_accepted_only_once(self):
        frames = [(self.meta(), FakeFrame()), (self.meta(), FakeFrame()),
                  (self.meta(seq=2), FakeFrame())]
        sample = lambda path, max_age: frames.pop(0) if frames else None
        adapter = self.make(sample)
        ok, frame = adapter.read()
        self.assertTrue(ok)
        self.assertEqual(frame.size, 9)
        ok, frame = adapter.read()
        self.assertTrue(ok)
        self.assertEqual(adapter._last_token, ("session-one", "gate", 2))
        self.assertEqual(adapter.last_reason, None)

    def test_input_missing_not_inferred(self):
        adapter = self.make(lambda path, max_age: None)
        self.assertEqual(adapter.read(), (False, None))
        self.assertEqual(adapter.last_reason, "NO_FIRST_FRAME")
        self.assertGreaterEqual(self.t[0], 102)

    def test_stale_after_first_valid_frame(self):
        samples = [(self.meta(), FakeFrame())]
        adapter = self.make(lambda path, max_age: samples.pop(0) if samples else None)
        self.assertTrue(adapter.read()[0])
        self.assertEqual(adapter.read(), (False, None))
        self.assertEqual(adapter.last_reason, "INPUT_STALE")

    def test_other_role_never_accepted(self):
        adapter = self.make(lambda path, max_age: (self.meta(role="parking"), FakeFrame()))
        self.assertEqual(adapter.read(), (False, None))
        self.assertEqual(adapter.last_reason, "IDENTITY_MISMATCH")

    def test_other_camera_never_accepted(self):
        adapter = self.make(lambda path, max_age: (self.meta(camera_id="B_PARK"), FakeFrame()))
        self.assertEqual(adapter.read(), (False, None))
        self.assertEqual(adapter.last_reason, "IDENTITY_MISMATCH")

    def test_other_run_never_accepted(self):
        adapter = self.make(lambda path, max_age: (self.meta(run_id="old-run"), FakeFrame()))
        self.assertEqual(adapter.read(), (False, None))
        self.assertEqual(adapter.last_reason, "IDENTITY_MISMATCH")

    def test_invalid_sequence_rejected(self):
        adapter = self.make(lambda path, max_age: (self.meta(seq=True), FakeFrame()))
        self.assertEqual(adapter.read(), (False, None))
        self.assertEqual(adapter.last_reason, "INVALID_SEQUENCE")

    def test_read_error_retries_and_recovers(self):
        calls = [0]
        def flaky(_path, max_age):
            calls[0] += 1
            if calls[0] < 3:
                raise OSError("temporary reader error")
            return self.meta(), FakeFrame()
        adapter = self.make(flaky)
        self.assertTrue(adapter.read()[0])
        self.assertEqual(adapter.last_reason, None)
        self.assertEqual(calls[0], 3)

    def test_release_prevents_future_read(self):
        adapter = self.make(lambda path, max_age: (self.meta(), FakeFrame()))
        adapter.release()
        self.assertFalse(adapter.isOpened())
        self.assertEqual(adapter.read(), (False, None))

    def test_gate_and_parking_separate(self):
        gate = self.make(lambda path, max_age: (self.meta(), FakeFrame()))
        parking = self.make(lambda path, max_age: (self.meta(role="parking", camera_id="B_PARK"), FakeFrame()),
                            role="parking", camera_id="B_PARK")
        self.assertTrue(gate.read()[0])
        self.assertTrue(parking.read()[0])
        self.assertNotEqual(gate._last_token, parking._last_token)

    def test_invalid_config_rejected(self):
        for role, camera in (("abc", "A"), ("gate", "")):
            with self.subTest(role=role, camera=camera), self.assertRaises(ValueError):
                self.make(lambda path, max_age: None, role=role, camera_id=camera)
        with self.assertRaises(ValueError):
            SharedFrameCapture(self.folder, "gate", "A", reader=lambda path, max_age: None,
                               max_age=3, max_silence=3)


if __name__ == "__main__":
    unittest.main()

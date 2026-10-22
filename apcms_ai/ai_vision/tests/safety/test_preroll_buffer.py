"""화재 의심 이벤트 *직전* 샘플 저장의 메모리 상한·시간 창·호환성 테스트.

실제 USB 카메라/YOLO 모델 없이 실행합니다.
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from ai_vision.safety.preroll_buffer import PreEventFrameBuffer
from ai_vision.safety.live_fire_smoke import LiveConfig, main, run_live
from ai_vision.tests.safety.test_live_fire_smoke import FakeBox, FakeCapture, FakeModel


def frame(width=80, height=50):
    return np.full((height, width, 3), 60, dtype=np.uint8)


class BufferUnitTests(unittest.TestCase):
    def test_reject_invalid_parameters(self):
        cases = [
            {"seconds": 0}, {"seconds": float("nan")}, {"seconds": True},
            {"max_frames": 0}, {"max_frames": 121}, {"max_frames": 1.2},
            {"max_bytes": 999}, {"max_width": 31}, {"jpeg_quality": 0},
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                PreEventFrameBuffer(**kwargs)

    def test_invalid_sample(self):
        b = PreEventFrameBuffer()
        with self.assertRaises(ValueError):
            b.add(None, 0.0, 1)
        with self.assertRaises(ValueError):
            b.add(frame(), -1, 1)
        with self.assertRaises(ValueError):
            b.add(frame(), 0, 0)
        b.add(frame(), .4, 1)
        with self.assertRaises(ValueError):
            b.add(frame(), .3, 2)

    def test_no_disk_write_until_event(self):
        with tempfile.TemporaryDirectory() as root:
            b = PreEventFrameBuffer()
            b.add(frame(), 0, 1)
            b.add(frame(), .5, 2)
            self.assertEqual(list(Path(root).iterdir()), [])
            self.assertEqual(b.frames, 2)

    def test_no_current_or_future_frames_in_saved_preroll(self):
        with tempfile.TemporaryDirectory() as root:
            b = PreEventFrameBuffer(seconds=3)
            for n in range(6):
                b.add(frame(), n * .5, n + 1)
            name, count = b.save_before(root, "preroll_fire_01", 1.5)
            self.assertEqual((name, count), ("preroll_fire_01", 3))
            rows = json.loads((Path(root) / name / "manifest.json").read_text(encoding="utf-8"))["frames"]
            self.assertEqual([x["frame_index"] for x in rows], [1, 2, 3])
            self.assertTrue(all(x["source_seconds"] < 1.5 for x in rows))
            self.assertEqual(len(list((Path(root) / name).glob("*.jpg"))), 3)

    def test_time_window_expires_old_frames(self):
        b = PreEventFrameBuffer(seconds=1)
        for t in (0, .5, 1, 1.5, 2):
            b.add(frame(), t, int(t * 2) + 1)
        self.assertEqual([p.source_seconds for p in b._frames], [1, 1.5, 2])

    def test_count_bound(self):
        b = PreEventFrameBuffer(seconds=30, max_frames=2)
        for i in range(8):
            b.add(frame(), i, i + 1)
        self.assertEqual([p.frame_index for p in b._frames], [7, 8])

    def test_byte_bound(self):
        f = frame(100, 100)
        b = PreEventFrameBuffer(seconds=30, max_bytes=1800)
        for i in range(20):
            b.add(f, i, i + 1)
        self.assertLessEqual(b.bytes_used, 1800)
        self.assertLessEqual(b.frames, 20)

    def test_oversize_sample_does_not_accumulate(self):
        b = PreEventFrameBuffer(max_bytes=1024)
        noise = np.random.default_rng(12).integers(0, 255, (250, 250, 3), dtype=np.uint8)
        b.add(noise, .1, 1)
        self.assertEqual(b.frames, 0)
        self.assertEqual(b.skipped_oversize, 1)

    def test_width_is_downscaled(self):
        b = PreEventFrameBuffer(max_width=100)
        b.add(frame(500, 300), .1, 1)
        self.assertEqual((b._frames[0].width, b._frames[0].height), (100, 60))

    def test_reject_unsafe_folder(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                PreEventFrameBuffer().save_before(root, "../escape", 1.0)

    def test_save_with_empty_history_has_zero_samples(self):
        with tempfile.TemporaryDirectory() as root:
            folder, saved = PreEventFrameBuffer().save_before(root, "preroll_empty", 0.0)
            self.assertEqual(saved, 0)
            manifest = json.loads((Path(root) / folder / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["frames"], [])


class SequenceModel(FakeModel):
    """호출 시점별로 FIRE가 나타나거나 사라지는 모의 YOLO."""
    def __init__(self, states):
        super().__init__(boxes=[])
        self.states = states

    def predict(self, **kwargs):
        i = len(self.calls)
        self.calls.append(kwargs)
        return [SimpleNamespace(boxes=[FakeBox(1, .8)] if i < len(self.states) and self.states[i] else [])]


class IntegrationTests(unittest.TestCase):
    def _run(self, root, model, *, samples=8, **options):
        video = Path(root) / "source.mp4"
        video.write_bytes(b"mock")
        output = Path(root) / "out"
        config = LiveConfig(video_path=str(video), interval=.1, max_seconds=0, output_dir=output,
                            window=3, min_hits=2, clear_after=2, cooldown=30,
                            **options)
        result = run_live(config, model=model, capture=FakeCapture(frames=samples, fps=10))
        return result, output

    def test_off_by_default_and_legacy_results_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            result, path = self._run(root, SequenceModel([True] * 8))
            self.assertEqual(result["suspected_events"], 1)
            self.assertFalse(result["saved_preroll"])
            self.assertFalse(list(path.glob("preroll_*")))
            self.assertNotIn("preroll_folder", json.loads((path / "events.json").read_text())["events"][0])

    def test_suspected_stores_only_previous_samples(self):
        with tempfile.TemporaryDirectory() as root:
            result, path = self._run(root, SequenceModel([True] * 8), save_preroll=True, save_evidence=True)
            self.assertEqual(result["suspected_events"], 1)
            self.assertEqual(result["preroll_event_folders"], 1)
            event = json.loads((path / "events.json").read_text(encoding="utf-8"))["events"][0]
            self.assertEqual(event["preroll_samples"], 1)
            self.assertTrue((path / event["preroll_folder"] / "frame_001.jpg").exists())
            self.assertTrue((path / event["evidence_image"]).exists())
            manifest = json.loads((path / event["preroll_folder"] / "manifest.json").read_text())
            self.assertEqual(manifest["frames"][0]["frame_index"], 1)
            self.assertEqual(manifest["frames"][0]["seconds_before_event"], 0.1)
            self.assertEqual(result["preroll_saved_images"], 1)

    def test_reopened_creates_separate_preroll_folder(self):
        with tempfile.TemporaryDirectory() as root:
            # 0/1 -> SUSPECTED, 2/3 -> CLEARED, 4/5 -> REOPENED
            result, path = self._run(root, SequenceModel([True, True, False, False, True, True, True, True]),
                                     save_preroll=True)
            self.assertEqual(result["suspected_events"], 1)
            self.assertEqual(result["incident_transition_counts"]["REOPENED"], 1)
            self.assertEqual(result["preroll_event_folders"], 2)
            history = json.loads((path / "incident_history.json").read_text())["transitions"]
            bookmarks = [row["preroll_folder"] for row in history if row["status"] in ("SUSPECTED", "REOPENED")]
            self.assertEqual(len(set(bookmarks)), 2)
            for item in bookmarks:
                self.assertTrue((path / item / "manifest.json").exists())

    def test_no_events_means_no_preroll_folders(self):
        with tempfile.TemporaryDirectory() as root:
            result, path = self._run(root, SequenceModel([False] * 8), save_preroll=True)
            self.assertEqual(result["preroll_event_folders"], 0)
            self.assertFalse(list(path.glob("preroll_*")))

    def test_config_validation(self):
        bad = [dict(save_preroll="true"), dict(preroll_seconds=0),
               dict(preroll_seconds=float("inf")), dict(preroll_max_frames=121),
               dict(preroll_max_frames=0)]
        for kwargs in bad:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                LiveConfig(**kwargs)

    def test_cli_accepts_preroll_arguments(self):
        with tempfile.TemporaryDirectory() as root:
            video = Path(root) / "source.mp4"
            video.write_bytes(b"mock")
            from unittest.mock import patch
            with patch("ai_vision.safety.live_fire_smoke.run_live", return_value={
                "status": "VIDEO_END", "captured_frames": 5, "inference_samples": 2, "suspected_events": 0,
            }) as run:
                self.assertEqual(main(["--video", str(video), "--save-preroll",
                                       "--preroll-seconds", "4", "--preroll-max-frames", "12"]), 0)
                self.assertTrue(run.call_args.args[0].save_preroll)
                self.assertEqual(run.call_args.args[0].preroll_seconds, 4.0)
                self.assertEqual(run.call_args.args[0].preroll_max_frames, 12)


if __name__ == "__main__":
    unittest.main()

"""FIRE/SMOKE별 신뢰도, 저신뢰도 후보 기록 및 이전 이벤트 형식 호환성 검사.

실제 모델·웹캠 없이 가짜 YOLO 모델과 카메라로 실행합니다.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import cv2

from ai_vision.safety.live_fire_smoke import LiveConfig, detect_frame, main, run_live
from ai_vision.tests.safety.test_live_fire_smoke import FakeBox, FakeCapture, FakeModel


class ConfigTests(unittest.TestCase):
    def test_legacy_conf_still_applies_to_both(self):
        self.assertEqual(LiveConfig().thresholds, {"FIRE": .20, "SMOKE": .20})
        self.assertEqual(LiveConfig(conf=.30).thresholds, {"FIRE": .30, "SMOKE": .30})

    def test_independent_class_thresholds(self):
        config = LiveConfig(conf=.30, fire_conf=.40, smoke_conf=.35, save_candidates=True)
        self.assertEqual(config.thresholds, {"FIRE": .40, "SMOKE": .35})
        self.assertEqual(config.candidate_conf, .20)

    def test_invalid_thresholds_and_candidate_relation(self):
        bad = [
            {"fire_conf": 0}, {"smoke_conf": 1.0}, {"candidate_conf": -0.2},
            {"candidate_conf": float("inf")}, {"fire_conf": True},
            {"save_candidates": True, "candidate_conf": .40, "conf": .30},
            {"save_candidates": True, "candidate_conf": .21, "fire_conf": .20, "smoke_conf": .30},
            {"save_candidates": "yes"},
        ]
        for kwargs in bad:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                LiveConfig(**kwargs)


class FilteringTests(unittest.TestCase):
    frame = np.zeros((32, 40, 3), dtype=np.uint8)

    def test_low_scoring_smoke_is_recorded_but_not_accepted(self):
        model = FakeModel([FakeBox(0, .23), FakeBox(1, .82)])
        candidates = []
        found, _ = detect_frame(model, self.frame, conf=.30, fire_conf=.30, smoke_conf=.30,
                                candidate_conf=.20, candidates_out=candidates)
        self.assertEqual([item["class_name"] for item in found], ["FIRE"])
        self.assertEqual(model.calls[0]["conf"], .20)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["reason"], "BELOW_CLASS_THRESHOLD")
        self.assertEqual(candidates[0]["accepted"], False)
        self.assertEqual(candidates[1]["reason"], "ACCEPTED")
        self.assertTrue(candidates[1]["accepted"])

    def test_different_thresholds_without_candidate_recording(self):
        model = FakeModel([FakeBox(0, .32), FakeBox(1, .34)])
        found, _ = detect_frame(model, self.frame, conf=.20, fire_conf=.40, smoke_conf=.30)
        self.assertEqual(model.calls[0]["conf"], .30)
        self.assertEqual([i["class_name"] for i in found], ["SMOKE"])

    def test_candidate_floor_is_actually_enforced_even_with_fake_model(self):
        model = FakeModel([FakeBox(0, .15), FakeBox(0, .24)])
        candidates = []
        found, _ = detect_frame(model, self.frame, conf=.30, candidate_conf=.20,
                                candidates_out=candidates)
        self.assertEqual(found, [])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["confidence"], .24)

    def test_legacy_prediction_conf_preserved(self):
        model = FakeModel([FakeBox(1, .70)])
        found, _ = detect_frame(model, self.frame)
        self.assertEqual(model.calls[0]["conf"], .20)
        self.assertEqual(len(found), 1)

    def test_invalid_candidate_input_prevents_predict(self):
        model = FakeModel()
        with self.assertRaises(ValueError):
            detect_frame(model, self.frame, conf=.30, candidate_conf=.31, candidates_out=[])
        with self.assertRaises(TypeError):
            detect_frame(model, self.frame, candidate_conf=.20, candidates_out={})
        self.assertEqual(model.calls, [])


class CandidateLogTests(unittest.TestCase):
    def _run(self, tmp, model, *, save=True):
        video = Path(tmp) / "fake.mp4"
        video.write_bytes(b"test")
        out = Path(tmp) / "results"
        config = LiveConfig(video_path=str(video), max_seconds=0, interval=.1,
                            conf=.30, fire_conf=.30, smoke_conf=.30,
                            save_candidates=save, candidate_conf=.20, output_dir=out)
        result = run_live(config, model=model, capture=FakeCapture(frames=4, fps=10))
        return result, out

    def test_rejected_candidates_do_not_create_incidents(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = FakeModel([FakeBox(0, .23)])
            result, output = self._run(tmp, model)
            self.assertEqual(result["status"], "VIDEO_END")
            self.assertEqual(result["suspected_events"], 0)
            self.assertEqual(result["candidate_samples"], 4)
            self.assertEqual(result["candidate_counts_by_type"]["SMOKE"],
                             {"total": 4, "accepted": 0, "rejected": 4})
            self.assertEqual(result["incident_transition_counts"]["SUSPECTED"], 0)
            self.assertEqual(json.loads((output / "events.json").read_text())["events"], [])
            lines = (output / "detection_candidates.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 4)
            self.assertEqual(json.loads(lines[0])["candidates"][0]["reason"], "BELOW_CLASS_THRESHOLD")
            self.assertEqual(json.loads(lines[0])["source_seconds"], 0.0)
            self.assertEqual(model.calls[0]["conf"], .20)

    def test_fire_event_and_smoke_candidate_coexist(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = FakeModel([FakeBox(1, .80), FakeBox(0, .24)])
            result, output = self._run(tmp, model)
            self.assertEqual(result["suspected_events"], 1)
            self.assertEqual(result["candidate_counts_by_type"]["FIRE"],
                             {"total": 4, "accepted": 4, "rejected": 0})
            self.assertEqual(result["candidate_counts_by_type"]["SMOKE"],
                             {"total": 4, "accepted": 0, "rejected": 4})
            self.assertEqual(json.loads((output / "events.json").read_text())["events"][0]["type"], "FIRE")
            self.assertEqual(len((output / "detection_candidates.jsonl").read_text().splitlines()), 4)

    def test_empty_frames_still_leave_a_sample_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, output = self._run(tmp, FakeModel(boxes=[]))
            self.assertEqual(result["candidate_samples"], 4)
            for line in (output / "detection_candidates.jsonl").read_text(encoding="utf-8").splitlines():
                self.assertEqual(json.loads(line)["candidates"], [])

    def test_no_candidate_log_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, output = self._run(tmp, FakeModel([FakeBox(1, .8)]), save=False)
            self.assertFalse((output / "detection_candidates.jsonl").exists())
            self.assertIsNone(result["candidate_samples"])
            self.assertFalse(result["saved_candidates"])
            self.assertEqual(result["suspected_events"], 1)
            self.assertEqual(result["candidate_log"], None)
            self.assertEqual(FakeModel().names[1], "fire")

    def test_log_closes_and_persists_on_inference_failure(self):
        class FailsOnSecond(FakeModel):
            def predict(self, **kwargs):
                if len(self.calls) == 1:
                    raise RuntimeError("intentional test error")
                return super().predict(**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "intentional test error"):
                self._run(tmp, FailsOnSecond([FakeBox(0, .23)]))
            output = Path(tmp) / "results"
            rows = (output / "detection_candidates.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 1)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "ERROR")
            self.assertEqual(summary["candidate_samples"], 1)

    def test_real_mp4_io_and_jsonl_candidates(self):
        """OpenCV가 만든 실제 MP4를 읽어 후보와 의심 사건을 디스크에 저장합니다."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "real_video.mp4"
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"),
                                     10.0, (64, 48))
            if not writer.isOpened():
                self.skipTest("OpenCV mp4v 코덱이 없는 실행 환경")
            try:
                for _ in range(10):
                    writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
            finally:
                writer.release()
            output = Path(tmp) / "results"
            config = LiveConfig(video_path=str(source), interval=.1, max_seconds=0,
                                conf=.30, fire_conf=.30, smoke_conf=.30,
                                candidate_conf=.20, save_candidates=True, output_dir=output)
            result = run_live(config, model=FakeModel([FakeBox(1, .80), FakeBox(0, .23)]))
            self.assertEqual(result["status"], "VIDEO_END")
            self.assertEqual(result["suspected_events"], 1)
            self.assertEqual(result["inference_samples"], result["candidate_samples"])
            self.assertEqual(len((output / "detection_candidates.jsonl").read_text().splitlines()),
                             result["candidate_samples"])
            self.assertEqual(result["candidate_counts_by_type"]["SMOKE"]["accepted"], 0)
            self.assertTrue((output / "incident_history.json").exists())

    def test_cli_new_arguments_are_forwarded(self):
        report = {"status": "VIDEO_END", "captured_frames": 0, "inference_samples": 0,
                  "suspected_events": 0}
        with patch("ai_vision.safety.live_fire_smoke.run_live", return_value=report) as runner:
            result = main(["--conf", "0.30", "--fire-conf", "0.35", "--smoke-conf", "0.32",
                           "--save-candidates", "--candidate-conf", "0.20"])
        self.assertEqual(result, 0)
        config = runner.call_args.args[0]
        self.assertEqual(config.thresholds, {"FIRE": .35, "SMOKE": .32})
        self.assertTrue(config.save_candidates)
        self.assertEqual(config.candidate_conf, .20)


if __name__ == "__main__":
    unittest.main()

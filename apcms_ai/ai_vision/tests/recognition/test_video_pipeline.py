# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_video_pipeline.py

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.run_video_pipeline import combine_results, run
from ai_vision.paths import RESULT_DIR


class VideoPipelineTests(unittest.TestCase):
    def arguments(self, name, reuse_tracking=None, reuse_ocr=None):
        return SimpleNamespace(output_dir=self.root / name, source=self.source,
                               reuse_tracking=reuse_tracking, reuse_ocr=reuse_ocr, tracker="bytetrack",
                               line_y=.6, line_x=(.15, .9), roi=(.1, 1, .36, .24, .64, .24, .92, 1),
                               max_seconds=1, max_tracks=1)

    def test_missing_reused_observations_stops_before_ocr(self):
        (self.tracking / "observations.jsonl").unlink()
        args = self.arguments("missing_observation", reuse_tracking=self.tracking)
        with patch("ai_vision.recognition.run_video_pipeline.subprocess.run") as child:
            with self.assertRaisesRegex(ValueError, "observations"):
                run(args)
        child.assert_not_called()
        manifest = json.loads((args.output_dir / "pipeline.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["stage"], "preflight")
        self.assertEqual(manifest["status"], "FAILED")

    def test_new_run_config_snapshot_preserved_even_after_failure(self):
        args = self.arguments("config_snapshot")
        with patch("ai_vision.recognition.run_video_pipeline.subprocess.run",
                   side_effect=subprocess.CalledProcessError(1, "tracking")):
            with self.assertRaises(subprocess.CalledProcessError):
                run(args)
        config = json.loads((args.output_dir / "tracking_config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["tracker"], "bytetrack")
        self.assertEqual(config["line_y"], .6)

    def setUp(self):
        # 1. 실제 모델 없이 차량 하나의 추적·OCR 결과 파일을 준비
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        assert Path(self.temp.name).resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input.mp4"
        self.source.touch()
        self.tracking, self.ocr = self.root / "tracking", self.root / "ocr"
        self.tracking.mkdir()
        self.ocr.mkdir()
        samples = [{"frame_index": frame, "video_seconds": time,
                    "plate_number": "91소6408", "plate_type": "KOREAN_VALID"}
                   for frame, time in [(60, 1), (78, 1.3)]]
        self.passage = {"track_id": 1, "screen_direction": "DOWN", "crossing_video_seconds": 1.2,
                        "plate_consensus": summarize_plate_samples(samples), "samples": samples,
                        "http_enabled": False, "record_type": "LOCAL_TRACKED_PASSAGE"}
        self.write(self.tracking / "summary.json", {"source": str(self.source),
                   "counts": {"DOWN": 2, "UP": 0}, "http_enabled": False})
        self.write(self.ocr / "summary.json", {"source_video": str(self.source),
                   "source_run": str(self.tracking), "crossings_in_run": 2,
                   "processed_tracks": 1, "confirmed_plates": 1, "http_enabled": False})
        self.rows(self.tracking / "crossings.jsonl", [
            {"track_id": 1, "direction": "DOWN", "video_seconds": 1.2},
            {"track_id": 2, "direction": "DOWN", "video_seconds": 3}])
        self.rows(self.tracking / "observations.jsonl", [dict(sample, track_id=1) for sample in samples])
        self.rows(self.ocr / "passages.jsonl", [self.passage])

    def write(self, path, data):
        path.write_text(json.dumps(data), encoding="utf-8")

    def rows(self, path, data):
        path.write_text("\n".join(json.dumps(row) for row in data), encoding="utf-8")

    def combine(self):
        return combine_results(self.source, self.tracking, self.ocr)

    def test_partial_ocr_is_explicit(self):
        # 2. 일부 차량만 OCR했는데 전체 검증 완료처럼 보고하지 않는지 확인
        result = self.combine()
        self.assertEqual(result["ocr_coverage"], "PARTIAL")
        self.assertEqual(result["ocr_not_processed"], 1)
        self.assertEqual(result["plate_status_counts"]["CONFIRMED"], 1)

    def test_repeated_observation_rejected(self):
        path = self.tracking / "observations.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.rows(path, rows + rows[:1])
        with self.assertRaisesRegex(ValueError, "중복"):
            self.combine()

    def test_other_vehicle_frames_rejected(self):
        # 3. 다른 차량의 프레임을 번호판 증거로 가져오면 거부
        self.passage["samples"][0]["frame_index"] = 999
        self.rows(self.ocr / "passages.jsonl", [self.passage])
        with self.assertRaisesRegex(ValueError, "표본"):
            self.combine()

    def test_forged_consensus_rejected(self):
        self.passage["plate_consensus"]["plate_number"] = "12가3456"
        self.rows(self.ocr / "passages.jsonl", [self.passage])
        with self.assertRaisesRegex(ValueError, "확정 결과"):
            self.combine()

    def test_mixed_source_rejected(self):
        self.write(self.tracking / "summary.json", {"source": str(self.root / "other.mp4")})
        with self.assertRaisesRegex(ValueError, "서로 다른"):
            self.combine()

    def test_failed_tracking_stops_ocr_and_records_stage(self):
        # 4. 추적 실행이 실패하면 OCR을 호출하지 않고 실패한 단계 보존
        args = SimpleNamespace(output_dir=self.root / "failed_run", source=self.source,
                               reuse_tracking=None, reuse_ocr=None, tracker="bytetrack",
                               line_y=.6, line_x=(.15, .9), roi=(.1, 1, .36, .24, .64, .24, .92, 1),
                               max_seconds=1, max_tracks=1)
        with patch("ai_vision.recognition.run_video_pipeline.subprocess.run",
                   side_effect=subprocess.CalledProcessError(1, "tracking")) as child:
            with self.assertRaises(subprocess.CalledProcessError):
                run(args)
        self.assertEqual(child.call_count, 1)
        manifest = json.loads((args.output_dir / "pipeline.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "FAILED")
        self.assertEqual(manifest["stage"], "tracking")
        self.assertNotIn("ocr", manifest["stages"])


if __name__ == "__main__":
    unittest.main()

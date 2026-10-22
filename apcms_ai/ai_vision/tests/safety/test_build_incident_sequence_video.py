"""영상 합성 도구 자체의 파일 입출력과 구간 생성에 대한 단위 테스트입니다."""

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from ai_vision.tests.safety.build_incident_sequence_video import build_sequence


class BuildIncidentSequenceVideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fire = self.root / "fire.mp4"
        self.normal = self.root / "normal.mp4"
        self._make_video(self.fire, 200)
        self._make_video(self.normal, 50)

    @staticmethod
    def _make_video(path, intensity):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 36))
        if not writer.isOpened():
            raise unittest.SkipTest("실행 환경에서 MP4 코덱을 사용할 수 없습니다.")
        try:
            for _ in range(20):
                writer.write(np.full((36, 64, 3), intensity, dtype=np.uint8))
        finally:
            writer.release()

    def test_builds_video_with_expected_total_frames(self):
        result = build_sequence(self.fire, self.normal, self.root / "output.mp4", fps=10,
                                width=64, height=36, segments=(("FIRE", 1), ("NORMAL", 1), ("FIRE", 1)))
        self.assertEqual(result["total_frames"], 30)
        self.assertEqual([s["scene"] for s in result["segments"]], ["FIRE", "NORMAL", "FIRE"])
        self.assertTrue((self.root / "output.segments.json").is_file())
        cap = cv2.VideoCapture(str(self.root / "output.mp4"))
        try:
            self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 30)
            self.assertTrue(cap.read()[0])
        finally:
            cap.release()

    def test_repeated_source_loops(self):
        result = build_sequence(self.fire, self.normal, self.root / "loop.mp4", fps=10,
                                width=64, height=36, segments=(("NORMAL", 5),))
        self.assertEqual(result["total_frames"], 50)

    def test_existing_output_does_not_get_overwritten(self):
        path = self.root / "existing.mp4"
        path.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            build_sequence(self.fire, self.normal, path)
        self.assertEqual(path.read_bytes(), b"keep")

    def test_bad_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            build_sequence(self.fire, self.normal, self.root / "bad.mp4", width=63)

    def test_input_must_exist(self):
        with self.assertRaises(FileNotFoundError):
            build_sequence(self.root / "missing.mp4", self.normal, self.root / "missing_output.mp4")

    def test_output_cannot_replace_input(self):
        with self.assertRaises(ValueError):
            build_sequence(self.fire, self.normal, self.fire, overwrite=True)


if __name__ == "__main__":
    unittest.main()

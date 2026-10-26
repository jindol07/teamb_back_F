"""두 불꽃 합성 영상과 사건 자동 검증 도구의 단위/통합 테스트.

실제 YOLO .pt는 사용하지 않습니다. 테스트용 검출 박스로 독립 사건을 재현합니다.
"""

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from ai_vision.safety.fire_event_state import FireEventStateManager
from ai_vision.tests.safety.build_dual_fire_sequence_video import (
    DEFAULT_SEGMENTS, build_dual_fire_sequence, compose_frame, panel_boxes,
)
from ai_vision.tests.safety.check_dual_fire_results import analyze_dual_fire_results


class DualFireVideoBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = self.root / "source.mp4"
        writer = cv2.VideoWriter(str(self.src), cv2.VideoWriter_fourcc(*"mp4v"), 8, (96, 54))
        if not writer.isOpened():
            self.skipTest("이 실행 환경의 OpenCV에서 MP4를 인코딩할 수 없습니다.")
        try:
            for i in range(16):
                frame = np.zeros((54, 96, 3), dtype=np.uint8)
                frame[:, :, 2] = 160 + i
                writer.write(frame)
        finally:
            writer.release()

    def _build(self, path=None, **opts):
        settings = {"fps": 8, "width": 320, "height": 180}
        settings.update(opts)
        return build_dual_fire_sequence(self.src, path or self.root / "dual.mp4", **settings)

    def test_default_sequence_has_expected_six_stages(self):
        self.assertEqual(len(DEFAULT_SEGMENTS), 6)
        self.assertEqual([v[0] for v in DEFAULT_SEGMENTS],
                         ["BOTH", "RIGHT_ONLY", "BOTH", "LEFT_ONLY", "BOTH", "NONE"])

    def test_panel_areas_are_separated(self):
        boxes = panel_boxes(1280, 720)
        self.assertLess(boxes["LEFT"][2] + 150, boxes["RIGHT"][0])

    def test_output_duration_and_manifest(self):
        manifest = self._build(segments=(("BOTH", 1), ("NONE", 1)))
        self.assertEqual(manifest["total_frames"], 16)
        self.assertEqual(manifest["total_seconds"], 2)
        self.assertEqual([s["scene"] for s in manifest["segments"]], ["BOTH", "NONE"])
        self.assertTrue((self.root / "dual.segments.json").is_file())
        self.assertEqual(json.loads((self.root / "dual.segments.json").read_text(encoding="utf-8"))["total_frames"], 16)
        cap = cv2.VideoCapture(str(self.root / "dual.mp4"))
        try:
            self.assertTrue(cap.isOpened())
            self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 16)
        finally:
            cap.release()

    def test_left_right_independently_visible(self):
        frame = np.full((54, 96, 3), (0, 0, 180), np.uint8)
        for left_on, right_on in ((True, True), (False, True), (True, False), (False, False)):
            composite = compose_frame(frame if left_on else None, frame if right_on else None,
                                      width=320, height=180)
            boxes = panel_boxes(320, 180)
            vals = []
            for x1, y1, x2, y2 in boxes.values():
                vals.append(int(composite[(y1 + y2) // 2, (x1 + x2) // 2, 2]))
            self.assertEqual(vals[0] > 120, left_on)
            self.assertEqual(vals[1] > 120, right_on)

    def test_every_scene_writes_correct_visual_regions(self):
        self._build(segments=(("BOTH", 1), ("RIGHT_ONLY", 1), ("LEFT_ONLY", 1), ("NONE", 1)))
        cap = cv2.VideoCapture(str(self.root / "dual.mp4"))
        try:
            for target_sec, expected in ((0, (True, True)), (1, (False, True)),
                                         (2, (True, False)), (3, (False, False))):
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_sec * 8 + 2)
                ok, frame = cap.read()
                self.assertTrue(ok)
                for (x1, y1, x2, y2), present in zip(panel_boxes(320, 180).values(), expected):
                    red = int(frame[(y1 + y2) // 2, (x1 + x2) // 2, 2])
                    self.assertEqual(red > 110, present)
        finally:
            cap.release()

    def test_reject_existing_file_without_overwrite(self):
        target = self.root / "dual.mp4"
        target.write_bytes(b"KEEP")
        with self.assertRaises(FileExistsError):
            self._build()
        self.assertEqual(target.read_bytes(), b"KEEP")

    def test_preexisting_partial_file_is_preserved(self):
        partial = self.root / "dual.partial.mp4"
        partial.write_bytes(b"DO-NOT-DELETE")
        with self.assertRaises(FileExistsError):
            self._build()
        self.assertEqual(partial.read_bytes(), b"DO-NOT-DELETE")

    def test_reject_overwriting_source(self):
        with self.assertRaises(ValueError):
            self._build(self.src, overwrite=True)

    def test_reject_missing_input(self):
        with self.assertRaises(FileNotFoundError):
            build_dual_fire_sequence(self.root / "missing.mp4", self.root / "out.mp4")

    def test_reject_invalid_scene(self):
        with self.assertRaises(ValueError):
            self._build(segments=(("FIRE", 2),))

    def test_reject_invalid_dimensions(self):
        with self.assertRaises(ValueError):
            self._build(width=319)

    def test_reject_invalid_fps(self):
        with self.assertRaises(ValueError):
            self._build(fps=0)

    def test_overwrite_existing_valid_file(self):
        self._build(segments=(("BOTH", 1),))
        result = self._build(overwrite=True, segments=(("NONE", 2),))
        self.assertEqual(result["total_frames"], 16)


class DualFireIncidentValidationTests(unittest.TestCase):
    # 2. 진짜 상태 관리자에 두 화재의 검출 박스를 주고 결과 판정기까지 연결합니다.
    @staticmethod
    def _make_history():
        manager = FireEventStateManager(window=5, min_hits=3, clear_after=3,
                                        cooldown=30, heartbeat_seconds=10)
        history = []
        events = []
        left_id = [90, 160, 490, 580]
        right_id = [790, 160, 1190, 580]
        for n in range(96):
            second = n * .5
            scene = DEFAULT_SEGMENTS[int(second // 8)][0]
            detections = []
            if scene in ("BOTH", "LEFT_ONLY"):
                detections.append({"class_name": "FIRE", "confidence": .8, "bbox": left_id})
            if scene in ("BOTH", "RIGHT_ONLY"):
                detections.append({"class_name": "FIRE", "confidence": .8, "bbox": right_id})
            transitions = manager.update(second, n + 1, detections)
            history.extend(transitions)
            events.extend(t for t in transitions if t["status"] == "SUSPECTED")
        history.extend(manager.finish(48., 97, "VIDEO_END"))
        manifest = {"purpose": "TWO_SEPARATE_FIRE_REGIONS_TEST_ONLY",
                    "output_video": "dual_fire_sequence.mp4", "width": 1280,
                    "segments": [{"scene": scene, "start_seconds": n * 8,
                                  "end_seconds": (n + 1) * 8} for n, (scene, _) in enumerate(DEFAULT_SEGMENTS)]}
        summary = {"status": "VIDEO_END", "source_name": "dual_fire_sequence.mp4"}
        return manifest, summary, events, history

    def test_two_separate_id_flow_passes(self):
        m, s, e, h = self._make_history()
        r = analyze_dual_fire_results(m, s, e, h)
        self.assertTrue(r["passed"], [c for c in r["checks"] if not c["passed"]])
        self.assertEqual(r["fire_transitions"]["SUSPECTED"], 2)
        self.assertEqual(r["fire_transitions"]["CLEARED"], 4)
        self.assertEqual(r["fire_transitions"]["REOPENED"], 2)
        self.assertEqual(len({row["event_id"] for row in e}), 2)

    def test_missing_reopen_is_reported(self):
        m, s, e, h = self._make_history()
        h = [v for v in h if not (v["status"] == "REOPENED" and v["source_seconds"] < 24)]
        r = analyze_dual_fire_results(m, s, e, h)
        self.assertFalse(r["passed"])
        self.assertTrue(any(not v["passed"] and "REOPENED" in v["name"] for v in r["checks"]))

    def test_merged_fire_box_is_reported(self):
        m, s, e, h = self._make_history()
        h[0] = {**h[0], "bbox": [200, 50, 1080, 640]}
        r = analyze_dual_fire_results(m, s, e, h)
        self.assertFalse(r["passed"])
        self.assertEqual(len(r["unassigned_fire_records"]), 1)

    def test_unexpected_smoke_is_warning(self):
        m, s, e, h = self._make_history()
        e.append({"type": "SMOKE", "status": "SUSPECTED"})
        r = analyze_dual_fire_results(m, s, e, h)
        self.assertTrue(r["warnings"])
        self.assertEqual(r["smoke_suspected_events"], 1)

    def test_same_event_id_shared_across_panels_rejected(self):
        m, s, e, h = self._make_history()
        first_id = e[0]["event_id"]
        second_id = e[1]["event_id"]
        for row in e + h:
            if row.get("event_id") == second_id:
                row["event_id"] = first_id
        report = analyze_dual_fire_results(m, s, e, h)
        self.assertFalse(report["passed"])
        self.assertTrue(any(not c["passed"] and "서로 다른" in c["name"] for c in report["checks"]))

    def test_wrong_manifest_rejected(self):
        m, s, e, h = self._make_history()
        m["purpose"] = "BAD"
        with self.assertRaises(ValueError):
            analyze_dual_fire_results(m, s, e, h)


if __name__ == "__main__":
    unittest.main()

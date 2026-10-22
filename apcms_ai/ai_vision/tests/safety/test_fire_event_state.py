# D:/finalProjectB/back/apcms_ai/ai_vision/tests/safety/test_fire_event_state.py
"""의심 사건의 발생·유지·해제·재발생과 영역 매칭을 모델 없이 검사합니다."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.safety.fire_event_state import FireEventStateManager, box_iou
from ai_vision.safety.live_fire_smoke import LiveConfig, run_live
from ai_vision.tests.safety.test_live_fire_smoke import FakeBox, FakeCapture, FakeModel


def obj(kind="FIRE", box=(1, 1, 21, 21), confidence=.8):
    return {"class_name": kind, "confidence": confidence, "bbox": list(box)}


def advance(manager, frames, start=0, step=.5):
    outputs = []
    for index, found in enumerate(frames):
        outputs.extend(manager.update(start + index * step, index, found))
    return outputs


class EventStateTests(unittest.TestCase):
    def test_box_iou_and_non_overlapping(self):
        self.assertEqual(box_iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0)
        self.assertEqual(box_iou((0, 0, 10, 10), (20, 20, 30, 30)), 0.0)
        self.assertAlmostEqual(box_iou((0, 0, 10, 10), (5, 0, 15, 10)), 1 / 3)

    def test_three_hits_open_and_ongoing_only_after_interval(self):
        manager = FireEventStateManager(heartbeat_seconds=1)
        changes = advance(manager, [[obj()], [obj()], [obj()], [obj()], [obj()]])
        self.assertEqual([c["status"] for c in changes], ["SUSPECTED", "ONGOING"])
        self.assertEqual(changes[0]["event_id"], changes[1]["event_id"])
        self.assertEqual(manager.snapshot()["active"], 1)

    def test_dedup_multiple_boxes_once_per_sample(self):
        manager = FireEventStateManager()
        rows = [[obj(), obj(confidence=.7)], [obj()], [obj()]]
        changes = advance(manager, rows)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["hits_in_window"], 3)
        self.assertEqual(manager.snapshot()["active"], 1)

    def test_sparse_hits_do_not_open(self):
        manager = FireEventStateManager()
        self.assertEqual(advance(manager, [[obj()], [], [], [obj()], [], [], [obj()]]), [])

    def test_clears_once_and_not_invented_by_session_finish(self):
        manager = FireEventStateManager()
        changes = advance(manager, [[obj()]] * 4 + [[]] * 6)
        self.assertEqual([c["status"] for c in changes], ["SUSPECTED", "CLEARED"])
        self.assertEqual(manager.snapshot()["active"], 0)
        self.assertEqual(manager.finish(5, 10, "VIDEO_END"), [])

    def test_reopened_within_cooldown_uses_same_event_id(self):
        manager = FireEventStateManager(cooldown=30)
        rows = [[obj()]] * 3 + [[]] * 3 + [[obj()]] * 3
        changes = advance(manager, rows)
        self.assertEqual([c["status"] for c in changes], ["SUSPECTED", "CLEARED", "REOPENED"])
        self.assertEqual(changes[0]["event_id"], changes[2]["event_id"])
        # 해제 직후 첫 1~2회의 재검출로 곧바로 REOPENED가 발생하면 안 됩니다.
        self.assertEqual(changes[2]["source_seconds"], 4.0)

    def test_new_incident_after_cooldown_has_new_id(self):
        manager = FireEventStateManager(cooldown=1)
        opens = advance(manager, [[obj()]] * 3 + [[]] * 3 + [[obj()]] * 3)
        self.assertEqual([c["status"] for c in opens], ["SUSPECTED", "CLEARED", "SUSPECTED"])
        self.assertNotEqual(opens[0]["event_id"], opens[2]["event_id"])

    def test_same_type_in_two_spatial_regions(self):
        manager = FireEventStateManager()
        left = obj(box=(1, 1, 20, 20))
        right = obj(box=(101, 101, 120, 120))
        changes = advance(manager, [[left, right]] * 3)
        self.assertEqual([x["status"] for x in changes], ["SUSPECTED", "SUSPECTED"])
        self.assertNotEqual(changes[0]["event_id"], changes[1]["event_id"])
        self.assertEqual(manager.snapshot()["active"], 2)

    def test_smoke_and_fire_are_independent(self):
        manager = FireEventStateManager()
        changes = advance(manager, [[obj(), obj("SMOKE")]] * 3)
        self.assertEqual({c["type"] for c in changes}, {"FIRE", "SMOKE"})
        self.assertEqual(len({c["event_id"] for c in changes}), 2)

    def test_slight_bbox_move_matches_same_incident(self):
        manager = FireEventStateManager()
        changes = advance(manager, [[obj(box=(i, i, 20 + i, 20 + i))] for i in range(6)])
        self.assertEqual([c["status"] for c in changes], ["SUSPECTED"])
        self.assertEqual(len(manager.regions), 1)

    def test_session_end_is_not_clear(self):
        manager = FireEventStateManager()
        rows = advance(manager, [[obj()]] * 3)
        self.assertEqual(rows[0]["status"], "SUSPECTED")
        final = manager.finish(2, 3, "VIDEO_END")
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0]["status"], "SESSION_ENDED")
        self.assertEqual(final[0]["event_id"], rows[0]["event_id"])
        self.assertEqual(manager.snapshot()["active"], 1)
        self.assertEqual(manager.finish(3, 4, "VIDEO_END"), [])
        with self.assertRaises(RuntimeError):
            manager.update(3, 5, [])

    def test_invalid_data_does_not_advance_clock(self):
        manager = FireEventStateManager()
        with self.assertRaises(ValueError):
            manager.update(1, 0, [obj(confidence=float("nan"))])
        self.assertIsNone(manager.last_time)
        self.assertFalse(manager.regions)
        manager.update(1, 0, [obj()])
        for args in [(0.5, 1, []), (2, 0, []), (3, 2, [obj(box=(0, 0, 0, 2))])]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                manager.update(*args)

    def test_regions_bounded_while_incidents_preserved(self):
        manager = FireEventStateManager(window=1, min_hits=1, max_regions=1)
        changes = manager.update(0, 0, [obj(box=(0, 0, 10, 10)), obj(box=(100, 100, 110, 110))])
        self.assertEqual(len(changes), 1)
        self.assertEqual(manager.snapshot()["active"], 1)
        self.assertEqual(manager.ignored_regions, 1)

    def test_invalid_config(self):
        for kwargs in ({"region_iou": 0}, {"heartbeat_seconds": 0}, {"max_regions": 0},
                       {"cooldown": float("nan")}, {"window": 2, "min_hits": 3}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                FireEventStateManager(**kwargs)


class IntegrationTests(unittest.TestCase):
    def test_live_video_legacy_events_and_new_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "input.mp4"
            video.write_bytes(b"mock data")
            output = Path(tmp) / "out"
            config = LiveConfig(video_path=str(video), interval=.1, max_seconds=0,
                                output_dir=output, heartbeat=.1)
            result = run_live(config, model=FakeModel(), capture=FakeCapture(frames=7, fps=10))
            self.assertEqual(result["suspected_events"], 1)
            self.assertEqual(result["incident_transition_counts"]["SUSPECTED"], 1)
            self.assertEqual(result["incident_transition_counts"]["SESSION_ENDED"], 1)
            self.assertEqual(result["active_incidents_at_end"], 1)
            events = json.loads((output / "events.json").read_text(encoding="utf-8"))["events"]
            history = json.loads((output / "incident_history.json").read_text(encoding="utf-8"))["transitions"]
            states = json.loads((output / "incident_states.json").read_text(encoding="utf-8"))
            self.assertEqual(events[0]["event_id"], history[0]["event_id"])
            self.assertEqual(states["active"], 1)
            self.assertIn("SESSION_ENDED", [e["status"] for e in history])

    def test_zero_detections_has_empty_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            video = Path(tmp) / "video.mp4"
            video.write_bytes(b"stub")
            result = run_live(LiveConfig(video_path=str(video), max_seconds=0, output_dir=output),
                              model=FakeModel(boxes=[]), capture=FakeCapture(frames=10, fps=10))
            self.assertEqual(result["suspected_events"], 0)
            self.assertEqual(json.loads((output / "incident_history.json").read_text(encoding="utf-8"))["transitions"], [])
            self.assertEqual(json.loads((output / "incident_states.json").read_text(encoding="utf-8"))["active"], 0)

    def test_missed_detections_cleared_in_saved_history(self):
        class IntermittentModel(FakeModel):
            def predict(self, **kwargs):
                self.calls.append(kwargs)
                boxes = [FakeBox()] if len(self.calls) <= 3 else []
                return [__import__('types').SimpleNamespace(boxes=boxes)]
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "video.mp4"
            video.write_bytes(b"stub")
            output = Path(tmp) / "out"
            report = run_live(LiveConfig(video_path=str(video), interval=.1, max_seconds=0,
                                         output_dir=output), model=IntermittentModel(),
                              capture=FakeCapture(frames=8, fps=10))
            self.assertEqual(report["incident_transition_counts"]["CLEARED"], 1)
            statuses = [r["status"] for r in json.loads((output / "incident_history.json").read_text(encoding="utf-8"))["transitions"]]
            self.assertEqual(statuses, ["SUSPECTED", "CLEARED"])


if __name__ == "__main__":
    unittest.main()

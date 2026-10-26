"""중첩 박스·흔들림·영역 분리·이벤트 ID 보존 회귀 테스트.

모델·영상·네트워크 없이 영역 추적 상태 관리자를 직접 검증합니다.
"""

import unittest

from ai_vision.safety.fire_event_state import (
    FireEventStateManager,
    _overlap_features,
    _same_visual_region,
)


def detection(box, kind="FIRE", conf=.8):
    return {"bbox": list(box), "class_name": kind, "confidence": conf}


def run(manager, frames, offset=0):
    events = []
    for index, boxes in enumerate(frames):
        events.extend(manager.update((index + offset) * .5, index + offset,
                                     [detection(box) if isinstance(box, tuple) else box
                                      for box in boxes]))
    return events


class BoxGeometryTests(unittest.TestCase):
    # 1. 단순 근접이나 작은 교집합만으로 다른 불꽃을 합치지 않도록 검사합니다.
    def test_duplicate_contained_box(self):
        self.assertTrue(_same_visual_region((0, 0, 100, 100), (25, 25, 75, 75)))

    def test_distant_boxes_remain_different(self):
        self.assertFalse(_same_visual_region((0, 0, 20, 20), (100, 0, 120, 20)))

    def test_partially_overlapping_boxes_remain_different(self):
        self.assertFalse(_same_visual_region((0, 0, 100, 100), (75, 0, 175, 100)))

    def test_small_corner_inside_large_is_not_forced_same(self):
        self.assertFalse(_same_visual_region((0, 0, 100, 100), (1, 1, 20, 20)))

    def test_large_scale_changes_coverage_and_area_ratio(self):
        iou, coverage, ratio, distance = _overlap_features((0, 0, 100, 100), (30, 30, 70, 70))
        self.assertAlmostEqual(iou, .16)
        self.assertEqual(coverage, 1.)
        self.assertAlmostEqual(ratio, .16)
        self.assertEqual(distance, 0.)


class TrackingTests(unittest.TestCase):
    # 2. 한 프레임의 중복 박스는 연속 감지 횟수를 두 번 올리면 안 됩니다.
    def test_nested_boxes_have_one_incident_and_region(self):
        big, nested = (0, 0, 100, 100), (25, 25, 75, 75)
        manager = FireEventStateManager()
        events = run(manager, [[big, nested]] * 4)
        self.assertEqual([event["status"] for event in events], ["SUSPECTED"])
        self.assertEqual(manager.snapshot()["active"], 1)
        self.assertEqual(len(manager.regions), 1)
        self.assertEqual(events[0]["hits_in_window"], 3)

    def test_duplicate_order_is_irrelevant(self):
        big, nested = detection((0, 0, 100, 100), conf=.7), detection((25, 25, 75, 75), conf=.9)
        manager = FireEventStateManager()
        events = run(manager, [[big, nested], [nested, big], [big, nested]])
        self.assertEqual(len(events), 1)
        self.assertEqual(manager.snapshot()["active"], 1)
        self.assertEqual(len(manager.regions), 1)

    # 3. 별개 화재는 가까이 있어도 박스가 충분히 구분되면 별도 사건이어야 합니다.
    def test_partially_overlapping_different_fires_remain_two(self):
        a, b = (0, 0, 100, 100), (75, 0, 175, 100)
        manager = FireEventStateManager()
        events = run(manager, [[a, b]] * 3)
        self.assertEqual(len([e for e in events if e["status"] == "SUSPECTED"]), 2)
        self.assertEqual(len({e["event_id"] for e in events}), 2)

    def test_independent_fire_and_smoke_even_when_nested(self):
        manager = FireEventStateManager()
        frames = [[detection((0, 0, 100, 100), "FIRE"),
                   detection((25, 25, 75, 75), "SMOKE")]] * 3
        events = run(manager, frames)
        self.assertEqual({e["type"] for e in events}, {"FIRE", "SMOKE"})
        self.assertEqual(manager.snapshot()["active"], 2)

    # 4. 박스 크기 변화와 중심 이동에서도 사건 ID를 유지합니다.
    def test_expanding_box_keeps_one_event(self):
        manager = FireEventStateManager()
        small, large = (40, 40, 60, 60), (20, 20, 80, 80)
        events = run(manager, [[small], [large], [small], [large], [small]])
        self.assertEqual([e["status"] for e in events], ["SUSPECTED"])
        self.assertEqual(len(manager.regions), 1)

    def test_jittering_box_keeps_event_id(self):
        manager = FireEventStateManager()
        frames = [[(x, 0, x + 100, 100)] for x in (0, 25, 50, 25, 0, 20)]
        events = run(manager, frames)
        self.assertEqual([e["status"] for e in events], ["SUSPECTED"])
        self.assertEqual(manager.snapshot()["active"], 1)
        self.assertEqual(len(manager.regions), 1)

    def test_detection_reordered_does_not_swap_two_events(self):
        manager = FireEventStateManager()
        a, b = (0, 0, 50, 50), (200, 0, 250, 50)
        events = run(manager, [[a, b], [b, a], [a, b], [b, a]])
        ids = {tuple(e["bbox"]): e["event_id"] for e in events if e["status"] == "SUSPECTED"}
        self.assertEqual(len(ids), 2)
        self.assertNotEqual(ids[a], ids[b])
        self.assertEqual(manager.snapshot()["active"], 2)

    # 5. 충분히 다른 위치는 같은 종류라도 이전 사건을 재개하면 안 됩니다.
    def test_new_distant_fire_after_clear_has_new_id(self):
        manager = FireEventStateManager()
        a, b = (0, 0, 30, 30), (200, 0, 230, 30)
        events = run(manager, [[a]] * 3 + [[]] * 3 + [[b]] * 3)
        self.assertEqual([e["status"] for e in events], ["SUSPECTED", "CLEARED", "SUSPECTED"])
        self.assertNotEqual(events[0]["event_id"], events[2]["event_id"])

    def test_reopened_same_box_keeps_old_id(self):
        manager = FireEventStateManager()
        a = (0, 0, 100, 100)
        events = run(manager, [[a]] * 3 + [[]] * 3 + [[a]] * 3)
        self.assertEqual([e["status"] for e in events], ["SUSPECTED", "CLEARED", "REOPENED"])
        self.assertEqual(events[0]["event_id"], events[-1]["event_id"])

    def test_new_event_after_cooldown_is_different(self):
        manager = FireEventStateManager(cooldown=1)
        a = (0, 0, 100, 100)
        events = run(manager, [[a]] * 3 + [[]] * 3 + [[a]] * 3)
        self.assertEqual([e["status"] for e in events], ["SUSPECTED", "CLEARED", "SUSPECTED"])
        self.assertNotEqual(events[0]["event_id"], events[-1]["event_id"])

    def test_bbox_size_cannot_jump_100_times_and_keep_same_identity(self):
        manager = FireEventStateManager(window=1, min_hits=1)
        first = (40, 40, 50, 50)
        huge = (0, 0, 100, 100)
        events = run(manager, [[first], [huge]])
        self.assertEqual(len(events), 2)
        self.assertNotEqual(events[0]["event_id"], events[1]["event_id"])

    def test_stale_observing_duplicate_cannot_steal_live_event(self):
        # 다른 물체 후보로 시작한 OBSERVING 영역이 활성이 된 화재 안으로 이동해도
        # 사건 ID를 가로채 새 경보를 만들면 안 됩니다.
        manager = FireEventStateManager()
        active = (0, 0, 100, 100)
        other = (200, 0, 260, 60)
        events = run(manager, [[active, other], [active], [active]])
        self.assertEqual([e["status"] for e in events], ["SUSPECTED"])
        event_id = events[0]["event_id"]
        # 과거 실행에서 남을 수 있는 중복 관찰 영역을 의도적으로 구성합니다.
        from ai_vision.safety.fire_event_state import _Region
        from collections import deque
        manager.regions.append(_Region(kind="FIRE", region_id="legacy_observing",
                                       bbox=(20, 20, 80, 80),
                                       anchor=(20, 20, 80, 80), history=deque(maxlen=5),
                                       confidence=.9, last_seen=1.0))
        more = run(manager, [[(20, 20, 80, 80)]] * 4, offset=3)
        self.assertEqual(more, [])
        self.assertEqual(manager.snapshot()["active"], 1)
        self.assertNotIn("legacy_observing", [r.region_id for r in manager.regions])
        self.assertEqual([r.incident_id for r in manager.regions if r.status == "SUSPECTED"], [event_id])

    def test_stale_observing_duplicate_cannot_override_cleared_cooldown(self):
        manager = FireEventStateManager()
        a = (0, 0, 100, 100)
        events = run(manager, [[a]] * 3 + [[]] * 3)
        self.assertEqual([e["status"] for e in events], ["SUSPECTED", "CLEARED"])
        from ai_vision.safety.fire_event_state import _Region
        from collections import deque
        manager.regions.append(_Region(kind="FIRE", region_id="legacy_observing",
                                       bbox=(20, 20, 80, 80), anchor=(20, 20, 80, 80),
                                       history=deque(maxlen=5), last_seen=2.5))
        more = run(manager, [[(20, 20, 80, 80)]] * 3, offset=6)
        self.assertEqual([e["status"] for e in more], ["REOPENED"])
        self.assertEqual(more[0]["event_id"], events[0]["event_id"])

    # 6. 최대 추적 영역 및 확정 사건 보호도 기존과 동일해야 합니다.
    def test_active_event_not_evicted_at_capacity(self):
        manager = FireEventStateManager(window=1, min_hits=1, max_regions=1)
        a, b = (0, 0, 10, 10), (100, 100, 110, 110)
        events = run(manager, [[a, b]])
        self.assertEqual(len(events), 1)
        self.assertEqual(manager.snapshot()["ignored_regions"], 1)
        self.assertEqual(manager.snapshot()["active"], 1)


if __name__ == "__main__":
    unittest.main()

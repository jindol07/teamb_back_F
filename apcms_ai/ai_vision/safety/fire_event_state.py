# D:/finalProjectB/back/apcms_ai/ai_vision/safety/fire_event_state.py
"""화재·연기 의심 '사건'을 영역별로 관리합니다.

검출(FIRE/SMOKE)은 실제 화재 확정이 아니며, 이벤트는 로컬 연구·시험 기록입니다.
관찰 가능한 상태 변화만 기록합니다. 영상 종료나 카메라 오류를 '화재 해제'로 간주하지 않습니다.
"""

import math
import uuid
from collections import deque
from dataclasses import dataclass, field


KINDS = ("FIRE", "SMOKE")


def box_iou(a, b):
    """두 탐지 박스의 교집합/합집합 비율(IoU)."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    width = max(0, min(ax2, bx2) - max(ax1, bx1))
    height = max(0, min(ay2, by2) - max(ay1, by1))
    intersection = width * height
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def _overlap_features(a, b):
    """두 박스의 IoU·작은 박스 포함률·면적비·중심 간 상대 거리를 구합니다.

    두 영역이 조금만 겹친다는 이유로 서로 다른 화재를 합치지 않도록
    IoU 외에도 포함률, 상대 크기와 중심 위치를 함께 확인합니다.
    """
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    overlap_w = max(0., min(ax2, bx2) - max(ax1, bx1))
    overlap_h = max(0., min(ay2, by2) - max(ay1, by1))
    inter = overlap_w * overlap_h
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    smaller = min(area_a, area_b)
    larger = max(area_a, area_b)
    union = area_a + area_b - inter
    iou = inter / union if union else 0.
    coverage = inter / smaller if smaller else 0.
    ratio = smaller / larger if larger else 0.
    # 긴 박스/넓은 박스 어느 한쪽만큼 움직여도 임의로 재결합하지 않습니다.
    delta_x = abs((ax1 + ax2) - (bx1 + bx2)) / (2 * max(ax2-ax1, bx2-bx1))
    delta_y = abs((ay1 + ay2) - (by1 + by2)) / (2 * max(ay2-ay1, by2-by1))
    return iou, coverage, ratio, max(delta_x, delta_y)


def _same_visual_region(a, b):
    """한 프레임에서 동일 물체로 보이는 중복 박스를 보수적으로 합칩니다.

    1) 높은 IoU는 기존처럼 중복으로 취급합니다.
    2) 큰 박스 안쪽의 유사한 중심·크기의 박스도 중복 후보로 봅니다.
    3) 일부만 겹치는 서로 다른 불꽃은 함부로 합치지 않습니다.
    """
    iou, coverage, ratio, distance = _overlap_features(a, b)
    return iou >= .50 or (coverage >= .90 and ratio >= .12 and distance <= .30)


def _association_strength(candidate, last_box, anchor, min_iou):
    """현재 관측을 과거 추적 영역과 연결할 수 있을 때만 점수를 반환합니다.

    박스 크기가 크게 바뀌면 IoU가 떨어지므로, 작은 쪽 대부분이 겹치고
    중심도 유사할 때에 한해 재연결합니다. 서로 떨어진 박스는 연결하지 않습니다.
    """
    best = None
    for previous in (last_box, anchor):
        if previous is None:
            continue
        iou, coverage, ratio, distance = _overlap_features(candidate, previous)
        # 중심이 비슷하고 포함률이 높더라도 크기 차이가 지나치면 새 영역입니다.
        containment_match = coverage >= .88 and ratio >= .10 and distance <= .30
        if iou >= min_iou or containment_match:
            score = iou + (min(coverage, 1.) * .10 if containment_match else 0.)
            best = max(score, best) if best is not None else score
    return best


def _smooth_box(previous, observed, factor=.35):
    """현재 좌표는 그대로 보존하면서 매칭용 기준 좌표만 완만히 갱신합니다."""
    return tuple((1-factor) * a + factor * b for a, b in zip(previous, observed))


@dataclass
class _Region:
    # 1. 사건과 독립적인 관찰 영역 ID. 같은 위치에서 나중에 새 사건이 생겨도 영역은 유지될 수 있음.
    kind: str
    region_id: str
    bbox: tuple
    history: deque
    anchor: tuple | None = None   # 1-1. 박스 흔들림 대응용 완만한 기준 좌표
    status: str = "OBSERVING"
    misses: int = 0
    incident_id: str | None = None
    started_at: float | None = None
    cleared_at: float | None = None
    last_seen: float = 0.0
    last_reported: float | None = None
    confidence: float = 0.0


class FireEventStateManager:
    """같은 종류·같은 영역의 연속 탐지를 하나의 사건으로 묶는 유한 상태 관리자.

    - SUSPECTED: 최근 window 중 min_hits 이상 탐지되어 새 의심 사건 생성
    - ONGOING: 지속 관찰 중 heartbeat_seconds 간격으로 유지 상태 기록
    - CLEARED: clear_after번 연속 미탐지(화재 진화 확정 아님)
    - REOPENED: 해제 후 cooldown 안에 같은 영역에서 재탐지(기존 사건 ID 사용)
    - SESSION_ENDED: 감지 종료; 계속 발생 중인 사건을 '해제'라고 기록하지 않음

    여러 위치는 region_id로 구분합니다. 영역 매칭은 박스 IoU 기반 휴리스틱입니다.
    """

    def __init__(self, window=5, min_hits=3, clear_after=3, cooldown=30.0,
                 region_iou=0.15, heartbeat_seconds=10.0, max_regions=16):
        if type(window) is not int or window < 1 or type(min_hits) is not int or not 1 <= min_hits <= window:
            raise ValueError("관찰 창 크기와 최소 감지 횟수를 확인하세요.")
        if type(clear_after) is not int or clear_after < 1:
            raise ValueError("해제 미탐지 횟수는 양의 정수여야 합니다.")
        for key, value in (("cooldown", cooldown), ("region_iou", region_iou),
                           ("heartbeat_seconds", heartbeat_seconds)):
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{key} 설정이 잘못되었습니다.")
        if not 0 < region_iou <= 1:
            raise ValueError("영역 IoU는 0 초과 1 이하여야 합니다.")
        if heartbeat_seconds <= 0:
            raise ValueError("유지 기록 간격은 0보다 커야 합니다.")
        if type(max_regions) is not int or not 1 <= max_regions <= 128:
            raise ValueError("최대 추적 영역 수는 1~128이어야 합니다.")
        self.window, self.min_hits, self.clear_after = window, min_hits, clear_after
        self.cooldown, self.region_iou = float(cooldown), float(region_iou)
        self.heartbeat_seconds, self.max_regions = float(heartbeat_seconds), max_regions
        self.regions = []
        self.last_time = None
        self.last_frame_index = None
        self.ignored_regions = 0
        self._ended = False

    @staticmethod
    def _validate_detection(det):
        if not isinstance(det, dict) or det.get("class_name") not in KINDS:
            raise ValueError("FIRE/SMOKE 탐지 사전이 필요합니다.")
        score = det.get("confidence")
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("유효한 감지 신뢰도가 필요합니다.")
        box = det.get("bbox")
        if not isinstance(box, (list, tuple)) or len(box) != 4 or any(
            type(c) not in (int, float) or not math.isfinite(c) for c in box
        ):
            raise ValueError("네 좌표로 이루어진 탐지 박스가 필요합니다.")
        x1, y1, x2, y2 = box
        if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
            raise ValueError("유효한 탐지 영역이 아닙니다.")
        return det["class_name"], float(score), tuple(float(v) for v in box)

    def _record(self, region, status, second, frame_index, reason=None):
        record = {
            "event_id": region.incident_id,
            "region_id": region.region_id,
            "status": status,
            "type": region.kind,
            "source_seconds": round(second, 3),
            "frame_index": frame_index,
            "confidence": round(region.confidence, 4),
            "bbox": [round(v) for v in region.bbox],
            "hits_in_window": sum(region.history),
            "started_at_seconds": round(region.started_at, 3) if region.started_at is not None else None,
            "reason": reason,
        }
        return record

    def _remove_stale(self, second):
        # 2. 이미 종료되었거나 확정 전인 영역만 제거. 살아 있는 의심 사건은 자동 삭제하지 않음.
        lifespan = max(self.cooldown + 2, 10.0)
        self.regions = [r for r in self.regions if r.status == "SUSPECTED" or second - r.last_seen <= lifespan]

    def update(self, source_seconds, frame_index, detections):
        # 3. 입력 검증이 실패해도 내부 상태가 부분적으로 변경되지 않도록 사전 검사.
        if self._ended:
            raise RuntimeError("종료된 상태 관리자입니다.")
        if (type(source_seconds) not in (int, float) or not math.isfinite(source_seconds)
                or source_seconds < 0 or (self.last_time is not None and source_seconds < self.last_time)):
            raise ValueError("영상 경과 시각이 이전보다 빠르거나 잘못되었습니다.")
        if (type(frame_index) is not int or frame_index < 0 or
                (self.last_frame_index is not None and frame_index <= self.last_frame_index)):
            raise ValueError("프레임 번호는 증가하는 0 이상의 정수여야 합니다.")
        if not isinstance(detections, (list, tuple)):
            raise ValueError("탐지 목록이 필요합니다.")
        parsed = [self._validate_detection(det) for det in detections]
        self.last_time, self.last_frame_index = source_seconds, frame_index
        self._remove_stale(source_seconds)

        # 3-1. 이전 프레임에 남은 OBSERVING 후보가 확인된 사건의 영역과
        #      사실상 같다면 후보만 제거합니다. 확정 사건과 사건 ID는 보존합니다.
        #      CLEARED 상태는 쿨다운 기간에만 동일 영역으로 취급합니다.
        established = [r for r in self.regions if r.incident_id is not None and (
            r.status == "SUSPECTED" or
            (r.status == "CLEARED" and r.cleared_at is not None and
             source_seconds - r.cleared_at < self.cooldown))]
        self.regions = [r for r in self.regions if not (
            r.status == "OBSERVING" and any(
                r.kind == stable.kind and _same_visual_region(r.bbox, stable.bbox)
                for stable in established))]

        # 4. 같은 프레임의 중복 박스를 정리합니다.
        # 4-1. IoU가 높거나 거의 동일한 영역 안쪽에서 중복 잡힌 박스는 1회로 계산합니다.
        # 4-2. 서로 다른 종류(FIRE/SMOKE)는 반드시 독립적으로 유지합니다.
        candidates = []
        for kind, score, box in sorted(parsed, key=lambda item: item[1], reverse=True):
            if any(old_kind == kind and _same_visual_region(box, old_box)
                   for old_kind, _, old_box in candidates):
                continue
            candidates.append((kind, score, box))

        # 5. 후보와 이전 영역의 매칭 점수를 모두 계산하여 전역적으로 일대일 대응합니다.
        # 5-1. 높은 신뢰도 후보부터 영역을 선점하는 기존 순서 의존을 줄입니다.
        # 5-2. 살아 있는 의심 사건에는 소폭 우선순위를 주어 OBSERVING 후보로 갈아타지 않게 합니다.
        edges = []
        for index, (kind, _score, box) in enumerate(candidates):
            for region_index, region in enumerate(self.regions):
                if region.kind != kind:
                    continue
                strength = _association_strength(box, region.bbox, region.anchor, self.region_iou)
                if strength is not None:
                    priority = strength + (.04 if region.status == "SUSPECTED" else 0.)
                    edges.append((priority, strength, index, region_index))
        # 안정적인 점수순 매칭. 한 후보와 한 영역은 각각 한 번만 선택합니다.
        edges.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
        matched_candidates, matched_regions = set(), set()
        found = {}
        for _, _, index, region_index in edges:
            if index in matched_candidates or region_index in matched_regions:
                continue
            region = self.regions[region_index]
            score, box = candidates[index][1:]
            matched_candidates.add(index)
            matched_regions.add(region_index)
            found[region.region_id] = (score, box)

        # 5-3. 다른 영역에 맞지 않은 박스에 대해서만 새 추적 영역을 만듭니다.
        #      이미 매칭된 의심 사건과 같은 시각적 영역이면 중복 생성을 막습니다.
        for index, (kind, score, box) in enumerate(candidates):
            if index in matched_candidates:
                continue
            if any(r.kind == kind and r.region_id in found and
                   r.status == "SUSPECTED" and
                   _same_visual_region(box, found[r.region_id][1])
                   for r in self.regions):
                continue
            if len(self.regions) >= self.max_regions:
                # 비활성 영역을 먼저 내보내고, 활성 의심 사건은 덮어쓰지 않습니다.
                old = [r for r in self.regions if r.status != "SUSPECTED" and r.region_id not in found]
                if old:
                    self.regions.remove(min(old, key=lambda r: r.last_seen))
                else:
                    self.ignored_regions += 1
                    continue
            region = _Region(kind=kind, region_id=uuid.uuid4().hex,
                             bbox=box, anchor=box, history=deque(maxlen=self.window))
            self.regions.append(region)
            found[region.region_id] = (score, box)

        # 5-4. 확정된 화재 영역과 사실상 같은 위치의 OBSERVING 중복 영역은 정리합니다.
        #      진행 중이거나 해제된 사건은 이 과정에서 지우지 않습니다.
        confirmed = [(r, found[r.region_id][1]) for r in self.regions
                     if r.status == "SUSPECTED" and r.region_id in found]
        redundant = {r.region_id for r in self.regions if r.status == "OBSERVING" and
                     r.region_id not in found and
                     any(r.kind == active.kind and _same_visual_region(r.bbox, box)
                         for active, box in confirmed)}
        if redundant:
            self.regions = [r for r in self.regions if r.region_id not in redundant]

        transitions = []
        for region in self.regions:
            observation = found.get(region.region_id)
            if observation is not None:
                score, box = observation
                region.anchor = _smooth_box(region.anchor or region.bbox, box)
                region.bbox, region.confidence = box, score
                region.last_seen = source_seconds
                region.misses = 0
                region.history.append(True)
                hits = sum(region.history)
                if region.status != "SUSPECTED" and hits >= self.min_hits:
                    if (region.status == "CLEARED" and region.cleared_at is not None and
                            source_seconds - region.cleared_at < self.cooldown):
                        region.status = "SUSPECTED"
                        region.last_reported = source_seconds
                        transitions.append(self._record(region, "REOPENED", source_seconds,
                                                        frame_index, "SAME_REGION_WITHIN_COOLDOWN"))
                    else:
                        region.incident_id = uuid.uuid4().hex
                        region.started_at = source_seconds
                        region.status = "SUSPECTED"
                        region.last_reported = source_seconds
                        transitions.append(self._record(region, "SUSPECTED", source_seconds, frame_index))
                elif region.status == "SUSPECTED" and (
                        region.last_reported is None or
                        source_seconds - region.last_reported >= self.heartbeat_seconds):
                    region.last_reported = source_seconds
                    transitions.append(self._record(region, "ONGOING", source_seconds, frame_index))
            else:
                region.history.append(False)
                region.misses += 1
                if region.status == "SUSPECTED" and region.misses >= self.clear_after:
                    region.status = "CLEARED"
                    # 재감지에는 새로운 관측만 계산하여 이전 감지로 즉시 재발생하지 않게 합니다.
                    region.history.clear()
                    region.cleared_at = source_seconds
                    region.last_reported = source_seconds
                    transitions.append(self._record(region, "CLEARED", source_seconds,
                                                    frame_index, "CONSECUTIVE_MISSES"))
        return transitions

    def finish(self, source_seconds, frame_index, reason):
        # 6. 영상 끝/시간 제한/카메라 오류로 관찰이 끝난 사건은 해제했다고 주장하지 않습니다.
        if self._ended:
            return []
        self._ended = True
        return [self._record(region, "SESSION_ENDED", source_seconds, frame_index, reason)
                for region in self.regions if region.status == "SUSPECTED"]

    def snapshot(self):
        return {
            "active": sum(r.status == "SUSPECTED" for r in self.regions),
            "cleared": sum(r.status == "CLEARED" for r in self.regions),
            "observing": sum(r.status == "OBSERVING" for r in self.regions),
            "ignored_regions": self.ignored_regions,
            "regions": [{
                "region_id": r.region_id, "event_id": r.incident_id,
                "type": r.kind, "status": r.status,
                "bbox": [round(v) for v in r.bbox], "confidence": round(r.confidence, 4),
                "started_at_seconds": round(r.started_at, 3) if r.started_at is not None else None,
                "cleared_at_seconds": round(r.cleared_at, 3) if r.cleared_at is not None else None,
            } for r in self.regions],
        }

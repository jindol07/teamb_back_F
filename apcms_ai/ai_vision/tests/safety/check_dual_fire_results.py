"""두 불꽃 합성 영상의 사건 기록을 자동 검증합니다 (단순 JSON 검사, 모델 실행 X).

실행 예시:
python -m ai_vision.tests.safety.check_dual_fire_results --results ./ai_vision/results/safety/dual_fire_test_01
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from ai_vision.paths import TEST_IMAGE_DIR


# 1. 기존 상태 관리기의 출력 포맷을 그대로 읽어 판정합니다.
def _load(path, root_key):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"필요한 JSON이 없습니다: {path}")
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON 최상위 구조가 올바르지 않습니다: {path}")
    if root_key is not None and not isinstance(data.get(root_key), list):
        raise ValueError(f"{path.name}에는 {root_key} 목록이 필요합니다.")
    return data


def _label(record, frame_width):
    """1-1. 추적 박스 중심으로 LEFT/RIGHT를 구분합니다.

    양쪽 화재를 한 개의 큰 박스로 잡은 경우에는 MERGED를 반환해 숨기지 않습니다.
    """
    bbox = record.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return "UNKNOWN"
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in bbox):
        return "UNKNOWN"
    x1, _y1, x2, _y2 = bbox
    if x2 <= x1:
        return "UNKNOWN"
    midpoint = frame_width / 2
    if x1 < midpoint - frame_width * .06 and x2 > midpoint + frame_width * .06:
        return "MERGED"
    return "LEFT" if (x1 + x2) / 2 < midpoint else "RIGHT"


def _check(name, passed, detail):
    return {"name": name, "passed": bool(passed), "detail": detail}


def analyze_dual_fire_results(manifest, summary, events, transitions):
    """2. 사건 ID·좌우 독립성·구간별 발생/해제/재개 조건 검증."""
    if manifest.get("purpose") != "TWO_SEPARATE_FIRE_REGIONS_TEST_ONLY":
        raise ValueError("두 불꽃 시나리오 JSON이 아닙니다.")
    segments = manifest.get("segments")
    width = manifest.get("width")
    expected = ["BOTH", "RIGHT_ONLY", "BOTH", "LEFT_ONLY", "BOTH", "NONE"]
    if not isinstance(width, int) or width <= 0 or not isinstance(segments, list) or [s.get("scene") for s in segments] != expected:
        raise ValueError("지원하는 여섯 구간의 시나리오 JSON이 필요합니다.")
    if not isinstance(events, list) or not isinstance(transitions, list):
        raise ValueError("사건 및 상태 변화 목록이 필요합니다.")
    if not isinstance(summary, dict):
        raise ValueError("summary JSON 객체가 필요합니다.")

    fire_history = [r for r in transitions if r.get("type") == "FIRE"]
    by_side = {"LEFT": [], "RIGHT": []}
    problems = []
    for row in fire_history:
        side = _label(row, width)
        if side in by_side:
            by_side[side].append(row)
        else:
            problems.append({"status": row.get("status"), "bbox": row.get("bbox"), "side": side})

    checks = [_check("영상 정상 종료", summary.get("status") == "VIDEO_END",
                     f"상태={summary.get('status')}"),
              _check("독립적인 FIRE 최초 사건 2건", len([r for r in events if r.get("type") == "FIRE"]) == 2,
                     f"events.json의 FIRE={sum(r.get('type') == 'FIRE' for r in events)}건"),
              _check("양쪽을 가로지르는 잘못된 FIRE 박스 없음", not problems,
                     f"분류 불가능한 FIRE 상태 기록={len(problems)}건")]
    # 2-0. 왼쪽과 오른쪽이 같은 사건 ID를 공유하는 경우도 명시적으로 거부합니다.
    initial_ids = []
    for side in ("LEFT", "RIGHT"):
        initial_ids.extend(row.get("event_id") for row in by_side[side] if row.get("status") == "SUSPECTED")
    checks.append(_check("좌우가 서로 다른 사건 ID 사용", len(initial_ids) == 2 and
                         len(set(initial_ids)) == 2 and None not in initial_ids,
                         f"신규 사건 ID={len(initial_ids)}개, 고유 ID={len(set(initial_ids))}개"))
    required = {
        "LEFT": ((0, "SUSPECTED"), (1, "CLEARED"), (2, "REOPENED"), (5, "CLEARED")),
        "RIGHT": ((0, "SUSPECTED"), (3, "CLEARED"), (4, "REOPENED"), (5, "CLEARED")),
    }
    for side in ("LEFT", "RIGHT"):
        rows = by_side[side]
        initial = [r for r in rows if r.get("status") == "SUSPECTED"]
        # 2-1. 같은 쪽에서 불이 다시 켜져도 초기 사건과 ID가 같아야 합니다.
        ids = {r.get("event_id") for r in rows if r.get("status") in ("SUSPECTED", "CLEARED", "REOPENED", "ONGOING")}
        checks.append(_check(f"{side} 사건 ID 유지", len(initial) == 1 and len(ids) == 1 and None not in ids,
                             f"신규 사건 {len(initial)}건, 추적 ID {len(ids)}개"))
        for segment_id, status in required[side]:
            segment = segments[segment_id]
            # 2-2. 실제 감지 시간은 각 구간 내에서 달라질 수 있습니다.
            matches = [r for r in rows if r.get("status") == status and
                       isinstance(r.get("source_seconds"), (int, float)) and
                       segment["start_seconds"] <= r["source_seconds"] < segment["end_seconds"]]
            checks.append(_check(f"{side} {status} ({segment['start_seconds']:.0f}~{segment['end_seconds']:.0f}초)",
                                 len(matches) == 1,
                                 "관측 시점=" + (", ".join(f"{r['source_seconds']:.2f}초" for r in matches) or "없음")))
        final_scene_start = segments[-1]["start_seconds"]
        late_end = [r for r in rows if r.get("status") == "SESSION_ENDED" and
                    r.get("source_seconds", -1) >= final_scene_start]
        checks.append(_check(f"{side} 마지막 정상 구간에서 해제 상태", not late_end,
                             f"영상 종료 시 활성 상태 기록={len(late_end)}건"))

    smoke_count = sum(r.get("type") == "SMOKE" for r in events)
    warnings = []
    if smoke_count:
        warnings.append(f"영상에 실제 연기 장면을 의도적으로 넣지 않았으나 SMOKE 의심 사건 {smoke_count}건 발생했습니다.")
    if summary.get("source_name") != manifest.get("output_video"):
        warnings.append("분석한 영상명과 생성 시나리오 영상명이 다릅니다. 결과 폴더를 확인하세요.")
    if problems:
        warnings.append("박스가 화면 중앙을 넓게 가로질러 두 영역을 구분하지 못했을 가능성이 있습니다.")

    return {"passed": all(c["passed"] for c in checks), "checks": checks,
            "warnings": warnings, "unassigned_fire_records": problems,
            "fire_transitions": dict(Counter(r.get("status") for r in fire_history)),
            "smoke_suspected_events": smoke_count}


def main(argv=None):
    # 3. 감지 프로그램은 --output을 주면 결과 폴더가 고정되어 재현 검증이 쉽습니다.
    parser = argparse.ArgumentParser(description="두 화재 독립 추적 결과 검증")
    parser.add_argument("--results", type=Path, required=True, help="summary.json 등의 결과 폴더")
    parser.add_argument("--manifest", type=Path,
                        default=TEST_IMAGE_DIR / "safety" / "dual_fire_sequence.segments.json")
    args = parser.parse_args(argv)
    try:
        manifest = _load(args.manifest, "segments")
        summary = _load(args.results / "summary.json", None)
        events = _load(args.results / "events.json", "events")["events"]
        transitions = _load(args.results / "incident_history.json", "transitions")["transitions"]
        report = analyze_dual_fire_results(manifest, summary, events, transitions)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"[검증 오류] {error}")
        return 2
    for c in report["checks"]:
        print(f"[{'PASS' if c['passed'] else 'FAIL'}] {c['name']} | {c['detail']}")
    for warning in report["warnings"]:
        print(f"[주의] {warning}")
    print(f"[검증 결과] {'통과' if report['passed'] else '추가 확인 필요'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

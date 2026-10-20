# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/simulate_event_guard.py

"""입출차 후보의 반복 입력·ID 변경·타임아웃을 송신 없이 검증합니다."""

import argparse
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_vision.recognition.local_io import read_json
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.review_workflow import write_new_file
from ai_vision.recognition.vehicle_contract import validate_vehicle_payload
from ai_vision.recognition.vehicle_event_guard import VehicleEventGuard
from ai_vision.recognition.vehicle_response import assess_response


def _report(steps, synthetic, skipped=0):
    return {"record_type": "LOCAL_EVENT_GUARD_SIMULATION", "http_enabled": False, "sendable": False,
            "uses_synthetic_event": synthetic, "skipped_blocked_per_pass": skipped,
            "candidate_count": sum(step["decision"] == "NEW_CANDIDATE" for step in steps), "steps": steps,
            "note": "AI 프로세스 메모리의 중복 억제 검사입니다. 재시작·다중 프로세스 중복 방지와 실제 서버 처리를 보장하지 않습니다."}


def preview_candidates(preview):
    """중복 억제와 처리 흐름이 공유하는 전체 초안 입력 검증입니다."""
    if (not isinstance(preview, dict) or preview.get("record_type") != "LOCAL_VEHICLE_EVENT_PREVIEW" or
            preview.get("http_enabled") is not False or preview.get("sendable") is not False or
            not isinstance(preview.get("items"), list) or len(preview["items"]) > 1000):
        raise ValueError("1000건 이하의 전송 없는 로컬 초안이 필요합니다.")
    run = preview.get("run_id")
    if not isinstance(run, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", run):
        raise ValueError("실행 식별자를 확인해 주세요.")
    candidates, seen, skipped = [], set(), 0
    for item in preview["items"]:
        if (not isinstance(item, dict) or type(item.get("track_id")) is not int or item["track_id"] < 0 or
                item["track_id"] in seen):
            raise ValueError("초안 차량 ID가 유효하지 않거나 중복됐습니다.")
        seen.add(item["track_id"])
        if item.get("status") == "BLOCKED" and item.get("payload") is None:
            skipped += 1
        elif item.get("status") == "CANDIDATE_ONLY" and item.get("reasons") == []:
            candidates.append((item["track_id"], validate_vehicle_payload(item["payload"])))
        else:
            raise ValueError("초안 상태와 요청 본문을 확인해 주세요.")
    for key, expected in (("total", len(preview["items"])), ("candidate_count", len(candidates))):
        if type(preview.get(key)) is not int or preview[key] != expected:
            raise ValueError("초안의 요약 건수가 다릅니다.")
    return run, candidates, skipped


def evaluate_preview(preview, guard=None, passes=2):
    # 모든 입력을 먼저 검사한 뒤 동일한 Guard에 반복 적용합니다.
    if type(passes) is not int or not 1 <= passes <= 10:
        raise ValueError("반복 횟수는 1~10이어야 합니다.")
    run, candidates, skipped = preview_candidates(preview)
    guard = VehicleEventGuard() if guard is None else guard
    steps = [{"pass": number + 1, "track_id": track, **guard.consider(run, track, event)}
             for number in range(passes) for track, event in candidates]
    return _report(steps, False, skipped)


def demo_report():
    guard = VehicleEventGuard()
    at = datetime(2020, 1, 1, tzinfo=timezone.utc)

    def event(second, identity):
        return {"event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, identity)), "event_type": "VEHICLE_PASSAGE",
                "detected_at": (at + timedelta(seconds=second)).isoformat(), "camera_id": "SIMULATION_ONLY",
                "direction": "ENTRY", "plate_number": "91소6408", "confidence": .8}

    first = event(0, "first")
    steps = [{"case": "first_passage", **guard.consider("demo", 10, first)},
             {"case": "same_track_new_uuid", **guard.consider("demo", 10, event(0, "regenerated"))},
             {"case": "switched_track_within_window", **guard.consider("demo", 11, event(1, "switched"))}]
    timeout = assess_response(first, transport_error="TIMEOUT")
    steps.append({"case": "timeout_recorded", **guard.record_result("demo", 10, "SIMULATION_ONLY", timeout)})
    steps.append({"case": "same_track_after_timeout", **guard.consider("demo", 10, first)})
    steps.append({"case": "new_passage_at_boundary", **guard.consider("demo", 12, event(5, "later"))})
    steps.append({"case": "out_of_order", **guard.consider("demo", 13, event(2, "old"))})
    return _report(steps, True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--preview", type=Path)
    source.add_argument("--demo", action="store_true")
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.demo and args.passes != 2:
            raise ValueError("demo는 고정된 사례를 사용합니다.")
        report = demo_report() if args.demo else evaluate_preview(read_json(args.preview), passes=args.passes)
        write_new_file(ResultCatalog(), args.output, json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"), ".json")
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "중복 억제 검증 실패: 초안과 새 출력 파일을 확인해 주세요.\n")
    print(f"로컬 검증 저장: 새 후보 {report['candidate_count']}건 / 검사 {len(report['steps'])}단계 (전송 없음)")


if __name__ == "__main__":
    main()

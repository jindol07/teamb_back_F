# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/simulate_vehicle_exchange.py

"""가짜 Boot 응답으로 입출차 결과 처리를 검증합니다. 실제 통신 기능은 없습니다."""

import argparse
import json
from pathlib import Path

from ai_vision.recognition.local_io import read_json
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.review_workflow import write_new_file
from ai_vision.recognition.vehicle_contract import validate_vehicle_payload
from ai_vision.recognition.vehicle_response import assess_response

SCENARIOS = ("processed", "unchanged", "pending", "bad_request", "unauthorized", "forbidden", "conflict",
             "rate_limited", "server_error", "timeout", "connection_error", "invalid_json", "wrong_event", "unknown_outcome")


def simulate_payload(payload, scenario):
    if scenario not in SCENARIOS:
        raise ValueError("지원하지 않는 모의 응답입니다.")
    event = validate_vehicle_payload(payload)
    if scenario in {"timeout", "connection_error"}:
        return assess_response(event, transport_error=scenario.upper())
    codes = {"bad_request": 400, "unauthorized": 401, "forbidden": 403, "conflict": 409,
             "rate_limited": 429, "server_error": 500}
    if scenario in codes:
        return assess_response(event, codes[scenario], "모의 오류 응답")
    # 1. Boot DTO의 camelCase 응답을 로컬 메모리에서만 만듭니다.
    body = {"eventId": event["event_id"], "eventType": "VEHICLE_PASSAGE", "plateNumber": event["plate_number"],
            "spaceCode": None, "parkingUsageId": 1, "detail": "SIMULATED_ONLY",
            "outcome": {"processed": "PROCESSED", "unchanged": "UNCHANGED", "pending": "PENDING"}.get(scenario, "PROCESSED")}
    if scenario == "wrong_event":
        body["eventId"] = "00000000-0000-0000-0000-000000000000"
    if scenario == "unknown_outcome":
        body["outcome"] = "UNKNOWN"
    raw = "{not-json" if scenario == "invalid_json" else json.dumps(body, ensure_ascii=False)
    return assess_response(event, 200, raw)


def build_simulation(preview=None, demo=False, scenarios=None):
    if type(demo) is not bool or (demo and preview is not None) or (not demo and preview is None):
        raise ValueError("실제 초안 또는 명시적 demo 중 하나만 지정합니다.")
    scenarios = list(SCENARIOS) if scenarios is None else list(scenarios)
    if not scenarios or len(scenarios) != len(set(scenarios)) or any(s not in SCENARIOS for s in scenarios):
        raise ValueError("모의 응답 목록을 확인해 주세요.")
    skipped = 0
    if demo:
        # 합성 한국 번호판은 통신 정책 검사 전용입니다. 영상 인식 성능 증거가 아닙니다.
        candidates = [{"event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479", "event_type": "VEHICLE_PASSAGE",
                       "detected_at": "2020-01-01T00:00:00Z", "camera_id": "SIMULATION_ONLY", "direction": "ENTRY",
                       "plate_number": "91소6408", "confidence": .8}]
    else:
        if (not isinstance(preview, dict) or preview.get("record_type") != "LOCAL_VEHICLE_EVENT_PREVIEW" or
                preview.get("http_enabled") is not False or preview.get("sendable") is not False or
                not isinstance(preview.get("items"), list)):
            raise ValueError("전송 없는 로컬 입출차 초안이 필요합니다.")
        candidates = []
        for item in preview["items"]:
            if not isinstance(item, dict):
                raise ValueError("초안 차량 형식이 유효하지 않습니다.")
            if item.get("status") == "BLOCKED" and item.get("payload") is None:
                skipped += 1
            elif item.get("status") == "CANDIDATE_ONLY" and isinstance(item.get("payload"), dict) and item.get("reasons") == []:
                candidates.append(validate_vehicle_payload(item["payload"]))
            else:
                raise ValueError("초안 상태와 요청 본문이 일치하지 않습니다.")
        for key, expected in (("total", len(preview["items"])), ("candidate_count", len(candidates))):
            if type(preview.get(key)) is not int or preview[key] != expected:
                raise ValueError("초안의 후보·전체 건수가 다릅니다.")
    if len(candidates) * len(scenarios) > 1000:
        raise ValueError("한 번에 1000개 이하의 모의 사례만 생성할 수 있습니다.")
    ids = [event["event_id"] for event in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("같은 UUID의 초안이 중복됐습니다.")
    cases = [{"scenario": scenario, **simulate_payload(event, scenario)} for event in candidates for scenario in scenarios]
    return {"record_type": "MOCK_VEHICLE_EXCHANGE_REPORT", "http_enabled": False, "sendable": False,
            "uses_synthetic_event": demo, "candidate_count": len(candidates), "skipped_blocked_count": skipped,
            "case_count": len(cases), "cases": cases,
            "note": "모든 응답은 가짜입니다. 실제 Boot·DB 처리나 안전한 재전송을 검증한 결과가 아닙니다."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--preview", type=Path)
    source.add_argument("--demo", action="store_true")
    parser.add_argument("--scenario", choices=SCENARIOS, action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        preview = read_json(args.preview) if args.preview is not None else None
        report = build_simulation(preview, args.demo, args.scenario)
        write_new_file(ResultCatalog(), args.output, json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"), ".json")
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "모의 검증 실패: 입력 초안과 새 출력 파일을 확인해 주세요.\n")
    print(f"모의 검증 저장: {report['case_count']}개 사례 / 보류 {report['skipped_blocked_count']}건 (실제 통신 없음)")


if __name__ == "__main__":
    main()

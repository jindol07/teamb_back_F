# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/preview_vehicle_events.py

"""저장 결과로 Boot 이벤트 초안만 생성합니다. 실제 송신 기능은 없습니다."""

import argparse
import json
import math
import re
import unicodedata
import uuid
from datetime import timedelta
from pathlib import Path

from ai_vision.recognition.local_io import iter_jsonl
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.review_workflow import write_new_file
from ai_vision.recognition.run_audit import audit_run
from ai_vision.recognition.vehicle_contract import (
    VEHICLE_ENDPOINT, AUTH_HEADER, parse_detected_at, validate_camera_id, validate_vehicle_payload)


def detection_confidence(row):
    # 1. 일치 번호 표본의 번호판 상자 탐지 신뢰도 최솟값입니다. OCR 정확도가 아닙니다.
    values = []
    for sample in row["samples"]:
        text = sample.get("plate_number", "")
        if not isinstance(text, str):
            continue
        text = re.sub(r"\s+", "", unicodedata.normalize("NFC", text))
        if sample.get("plate_type") == "KOREAN_VALID" and text == row["plate_consensus"]["plate_number"]:
            value = sample.get("plate_detection_confidence")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1 or not math.isfinite(value):
                return None
            values.append(value)
    return min(values) if values else None


def build_preview(catalog, run_id, camera_id=None, down_direction=None, recording_started_at=None, now=None):
    if camera_id is not None:
        validate_camera_id(camera_id)
    if down_direction is not None and down_direction not in {"ENTRY", "EXIT"}:
        raise ValueError("DOWN의 실제 방향은 ENTRY 또는 EXIT로 지정합니다.")
    start = parse_detected_at(recording_started_at) if recording_started_at is not None else None
    audit = audit_run(catalog, run_id)
    if audit["status"] not in {"PASS", "WARNING"} or audit.get("kind") not in {"ocr", "pipeline"}:
        raise ValueError("연결 진단을 통과한 OCR 결과가 필요합니다.")
    snapshot = catalog.review_snapshot(run_id)
    expected = {item["track_id"]: item for item in snapshot["items"]}
    folder, _ = catalog.review_source(run_id)
    items = []
    for row in iter_jsonl(catalog.safe_file(folder / "passages.jsonl")):
        track = row["track_id"]
        public = expected[track]
        reasons = []
        if public["plate_status"] != "CONFIRMED":
            reasons.append("NO_CONFIRMED_KOREAN_PLATE")
        for missing, code in ((camera_id is None, "MISSING_CAMERA_ID"), (down_direction is None, "MISSING_DIRECTION_MAPPING"),
                              (start is None, "MISSING_RECORDING_START")):
            if missing:
                reasons.append(code)
        confidence = detection_confidence(row) if public["plate_status"] == "CONFIRMED" else None
        if public["plate_status"] == "CONFIRMED" and confidence is None:
            reasons.append("MISSING_DETECTION_CONFIDENCE")
        payload = None
        if not reasons:
            direction = down_direction if public["screen_direction"] == "DOWN" else {"ENTRY": "EXIT", "EXIT": "ENTRY"}[down_direction]
            # 2. 현재 시각으로 대체하지 않고 명시한 촬영 시작 시각에 영상 초를 더합니다.
            at = start + timedelta(seconds=public["video_seconds"])
            identity = json.dumps([run_id, snapshot["snapshot_sha256"], track, camera_id, direction, at.isoformat()], ensure_ascii=False)
            draft = {"event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, identity)), "event_type": "VEHICLE_PASSAGE",
                     "detected_at": at.isoformat(), "camera_id": camera_id, "direction": direction,
                     "plate_number": public["plate_number"], "confidence": confidence}
            payload = validate_vehicle_payload(draft, now)
        items.append({"track_id": track, "screen_direction": public["screen_direction"], "video_seconds": public["video_seconds"],
                      "status": "BLOCKED" if reasons else "CANDIDATE_ONLY", "reasons": reasons, "payload": payload})
    if catalog.review_snapshot(run_id) != snapshot or len(items) != len(expected):
        raise ValueError("이벤트 초안 생성 중 원본 결과가 변경됐습니다.")
    return {"run_id": run_id, "snapshot_sha256": snapshot["snapshot_sha256"], "record_type": "LOCAL_VEHICLE_EVENT_PREVIEW",
            "http_enabled": False, "sendable": False, "endpoint_path_without_context": VEHICLE_ENDPOINT,
            "authentication_header_name": AUTH_HEADER, "confidence_basis": "MIN_MATCHING_PLATE_DETECTION_CONFIDENCE_NOT_OCR_ACCURACY",
            "audit_status": audit["status"], "total": len(items), "candidate_count": sum(item["payload"] is not None for item in items),
            "items": items, "note": "검토용 초안입니다. 과거 영상의 실제 입출차 전송이나 UUID 재전송 중복 방지를 보장하지 않습니다."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--camera-id")
    parser.add_argument("--down-direction", choices=["ENTRY", "EXIT"])
    parser.add_argument("--recording-started-at")
    args = parser.parse_args(argv)
    try:
        catalog = ResultCatalog()
        result = build_preview(catalog, args.run_id, args.camera_id, args.down_direction, args.recording_started_at)
        write_new_file(catalog, args.output, json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"), ".json")
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        parser.exit(1, "입출차 초안 생성 실패: 입력 설정과 저장 결과를 확인해 주세요.\n")
    print(f"로컬 초안 저장: 후보 {result['candidate_count']} / 전체 {result['total']}건 (전송 없음)")


if __name__ == "__main__":
    main()

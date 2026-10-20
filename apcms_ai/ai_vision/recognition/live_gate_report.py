# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_report.py

"""로컬 세션 결과의 필수 항목과 건수를 검사하고 표시할 자료만 선택합니다."""

import math
import re
from collections import Counter
from datetime import datetime

from ai_vision.recognition.local_io import read_json
from ai_vision.recognition.vehicle_contract import validate_camera_id
from ai_vision.recognition.live_gate_metrics import validate_metrics, validate_processor_statistics
from ai_vision.recognition.live_gate_context import validate_run_context
from ai_vision.recognition.live_gate_deadline import validate_deadline
from ai_vision.recognition.plate_consensus import validate_plate_summary


DECISIONS = {"DISABLED", "BLOCKED", "NEW_CANDIDATE", "SUPPRESSED_SAME_TRACK",
             "SUPPRESSED_RECENT_PLATE", "HELD_TRACK_CONFLICT", "HELD_CAPACITY",
             "HELD_OUT_OF_ORDER", "HELD_EVENT_ID_REUSE"}


def _integer(value, maximum=100000):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("결과 건수·차량 번호의 범위를 확인해 주세요.")
    return value


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("시간대가 포함된 시각이 필요합니다.")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("시간대가 포함된 시각이 필요합니다.")
    return parsed


def validate_report(report):
    # 1. 종료 결과만 읽습니다. RUNNING이나 초기화 실패의 불완전 기록은 거부합니다.
    if not isinstance(report, dict) or report.get("record_type") != "LIVE_GATE_SESSION":
        raise ValueError("실시간 세션 결과가 필요합니다.")
    if report.get("status") not in {"STOPPED", "FAILED"} or report.get("closed") is not True:
        raise ValueError("종료된 전체 세션 결과가 필요합니다.")
    required = {"session_id", "camera_id", "down_direction", "started_at", "captured_frames",
                "processed_passages", "decision_counts", "request_attempts", "http_enabled",
                "stop_reason", "results", "uses_synthetic_source", "cleanup_errors", "error_type",
                "dropped_crops", "dropped_tracks"}
    if not required <= report.keys():
        raise ValueError("세션 결과의 필수 항목이 누락됐습니다.")
    if not isinstance(report["session_id"], str) or not re.fullmatch(r"gate_[0-9a-f]{32}", report["session_id"]):
        raise ValueError("세션 ID 형식이 올바르지 않습니다.")
    validate_camera_id(report["camera_id"])
    if report["down_direction"] not in {"ENTRY", "EXIT"}:
        raise ValueError("입출차 방향이 올바르지 않습니다.")
    if any(type(report[key]) is not bool for key in ("http_enabled", "uses_synthetic_source")):
        raise ValueError("실행 출처·HTTP 설정을 확인해 주세요.")
    if report["stop_reason"] not in {"FRAME_LIMIT", "TIME_LIMIT", "CAMERA_READ_ENDED", "CAMERA_OPEN_FAILED", "CAMERA_READ_FAILED",
                                    "USER_INTERRUPTED", "CAPTURE_OR_PROCESSING_FAILED"}:
        raise ValueError("종료 사유가 올바르지 않습니다.")
    started = _timestamp(report["started_at"])
    frames = _integer(report["captured_frames"])
    count = _integer(report["processed_passages"], 10000)
    requests = _integer(report["request_attempts"], 10000)
    cleanup = _integer(report["cleanup_errors"], 3)
    for key in ("dropped_crops", "dropped_tracks"):
        _integer(report[key], 2**63 - 1)
    if report["error_type"] is not None and (not isinstance(report["error_type"], str) or
            not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,95}", report["error_type"])):
        raise ValueError("오류 종류가 올바르지 않습니다.")
    if report["status"] == "STOPPED" and (cleanup or report["error_type"] is not None or
            report["stop_reason"] in {"CAPTURE_OR_PROCESSING_FAILED", "CAMERA_OPEN_FAILED", "CAMERA_READ_FAILED"}):
        raise ValueError("실패 정보와 정상 종료 상태가 모순됩니다.")
    source_end_expected = report.get("source_end_expected")
    if "source_end_expected" in report:
        if type(source_end_expected) is not bool:
            raise ValueError("입력 종료 허용 정책은 참·거짓이어야 합니다.")
        if source_end_expected is False and report["stop_reason"] == "CAMERA_READ_ENDED":
            raise ValueError("읽기 실패를 정상 입력 종료로 기록할 수 없습니다.")
    rows, decisions = report["results"], report["decision_counts"]
    if not isinstance(rows, list) or len(rows) != count or not isinstance(decisions, dict):
        raise ValueError("통과 결과 개수가 요약과 다릅니다.")
    if any(key not in DECISIONS or type(value) is not int or value <= 0 for key, value in decisions.items()):
        raise ValueError("판정별 건수가 올바르지 않습니다.")
    checked, elapsed_before, attempts = [], -1, 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("통과 행은 객체여야 합니다.")
        keys = {"track_id", "decision", "request_attempted", "automatic_retry_allowed", "http_enabled",
                "captured_at", "crossing_elapsed_seconds", "plate_consensus", "sample_count", "receipt_state"}
        if not keys <= row.keys():
            raise ValueError("통과 행의 필수 항목이 누락됐습니다.")
        _integer(row["track_id"], 2**63 - 1)
        samples = _integer(row["sample_count"], 3)
        if samples > frames:
            raise ValueError("표본 수가 수집 프레임 수보다 많습니다.")
        elapsed = row["crossing_elapsed_seconds"]
        if (isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or
                not math.isfinite(elapsed) or elapsed < 0 or elapsed < elapsed_before):
            raise ValueError("통과 시각의 순서가 올바르지 않습니다.")
        elapsed_before = elapsed
        if abs((_timestamp(row["captured_at"]) - started).total_seconds() - elapsed) > .002:
            raise ValueError("수집 시각과 경과 시각이 다릅니다.")
        if (row["decision"] not in DECISIONS or row["automatic_retry_allowed"] is not False or
                type(row["http_enabled"]) is not bool or row["http_enabled"] != report["http_enabled"] or
                (row["request_attempted"] is not None and type(row["request_attempted"]) is not bool)):
            raise ValueError("통과 행의 전송 상태가 올바르지 않습니다.")
        if not report["http_enabled"] and (row["decision"] not in {"DISABLED", "BLOCKED"} or row["request_attempted"] is not False):
            raise ValueError("HTTP 비활성 결과에 요청 기록이 있습니다.")
        if row["receipt_state"] is not None and row["receipt_state"] not in {
                "AWAITING_RESULT", "NOT_CREATED", "APPLIED", "UNCHANGED", "HELD", "REJECTED",
                "AUTH_REQUIRED", "DELIVERY_UNKNOWN"}:
            raise ValueError("응답 상태가 올바르지 않습니다.")
        consensus = validate_plate_summary(row["plate_consensus"], samples)
        attempts += row["request_attempted"] is True
        # 2. 원본 응답·추가 필드는 보고서에 옮기지 않고 표시용 항목만 선택합니다.
        checked.append({key: row[key] for key in ("track_id", "decision", "captured_at",
                        "crossing_elapsed_seconds", "sample_count", "receipt_state", "request_attempted")}
                       | consensus)
    if Counter(row["decision"] for row in checked) != decisions or attempts != requests or (count and not frames):
        raise ValueError("판정·요청 건수가 원본 행과 일치하지 않습니다.")
    # 4. 이전 버전의 파일은 허용하되 새 진단 항목이 있으면 건수도 검사합니다.
    performance = validate_metrics(report["performance"], frames) if "performance" in report else None
    statistics = report.get("processor_statistics")
    if statistics is not None:
        statistics = validate_processor_statistics(statistics, frames)
        if statistics["crossings"] < count:
            raise ValueError("통과 결과 수가 처리기의 통과 판정 수보다 많습니다.")
    context = validate_run_context(report["run_context"], report["uses_synthetic_source"]) if "run_context" in report else None
    if context is not None and frames > context["max_frames"]:
        raise ValueError("수집 프레임 수가 기록된 실행 제한을 넘었습니다.")
    deadline = validate_deadline(report["deadline"]) if report.get("deadline") is not None else None
    if deadline is not None:
        if context is not None and deadline["seconds"] != context["seconds"]:
            raise ValueError("시간 제한 검사와 실행 설정의 제한 시간이 다릅니다.")
        if deadline["expired_before_read"] and report["stop_reason"] != "TIME_LIMIT":
            raise ValueError("읽기 전 시간 초과와 종료 사유가 다릅니다.")
    return {key: report[key] for key in required - {"results"}} | {
        "status": report["status"], "rows": checked,
        "performance": performance, "processor_statistics": statistics,
        "run_context": context,
        "deadline": deadline,
        "source_end_expected": source_end_expected,
        "unknown_request_attempts": sum(row["request_attempted"] is None for row in checked)}


def load_report(path):
    # 3. 중복 키·무한대·파일 크기 제한은 공통 JSON 읽기를 재사용합니다.
    return validate_report(read_json(path, max_bytes=32 * 1024 * 1024))

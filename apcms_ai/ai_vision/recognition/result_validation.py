# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/result_validation.py

"""저장 결과를 공개하기 전에 건수와 OCR 원본 표본을 검사합니다."""

import math
from ai_vision.recognition.plate_consensus import summarize_plate_samples


def validate_summary(result):
    # 1. 개별 건수가 정상이어도 서로의 합계가 다르면 결과를 제공하지 않습니다.
    if result["kind"] == "pipeline":
        total = result["total_crossings"]
        processed = result["ocr_processed"]
        if sum(result["crossing_counts"].values()) != total or sum(result["plate_status_counts"].values()) != processed:
            raise ValueError("방향·판정별 합계가 처리 건수와 일치하지 않습니다.")
        expected = "ALL_RECORDED_TRACKS" if processed == total else "PARTIAL"
        if result["ocr_coverage"] != expected:
            raise ValueError("OCR 처리 범위와 건수가 일치하지 않습니다.")
    elif result["kind"] == "ocr":
        if not result["confirmed_plates"] <= result["processed_tracks"] <= result["crossings_in_run"]:
            raise ValueError("OCR 확정·처리·통과 건수 관계가 유효하지 않습니다.")


def public_passage(row):
    # 2. 잘못된 중첩 객체도 AttributeError 대신 검증 오류로 처리합니다.
    if (not isinstance(row, dict) or row.get("http_enabled") is not False or
            row.get("record_type") != "LOCAL_TRACKED_PASSAGE" or
            type(row.get("track_id")) is not int or row["track_id"] < 0 or
            row.get("screen_direction") not in {"UP", "DOWN"}):
        raise ValueError("통과 판정 결과 형식이 유효하지 않습니다.")
    time = row.get("crossing_video_seconds")
    if isinstance(time, bool) or not isinstance(time, (int, float)) or not math.isfinite(time) or time < 0:
        raise ValueError("통과 시각이 유효하지 않습니다.")
    consensus, samples = row.get("plate_consensus"), row.get("samples")
    if not isinstance(consensus, dict) or not isinstance(samples, list) or any(not isinstance(s, dict) for s in samples):
        raise ValueError("번호판 판정과 표본은 객체와 목록이어야 합니다.")
    checked = summarize_plate_samples(samples, consensus["minimum_votes"], consensus["minimum_spacing_seconds"])
    if checked != consensus:
        raise ValueError("번호판 판정과 원본 표본이 일치하지 않습니다.")
    return {"track_id": row["track_id"], "screen_direction": row["screen_direction"],
            "video_seconds": time, "plate_status": checked["status"],
            "plate_number": checked["plate_number"], "sample_count": len(samples)}

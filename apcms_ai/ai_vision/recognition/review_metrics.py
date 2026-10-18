# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/review_metrics.py

"""검증된 수동 검토만 집계하며 미검토를 정답으로 간주하지 않습니다."""

from collections import Counter
from ai_vision.recognition.review_labels import validate_labels


def build_report(snapshot, rows):
    checked = validate_labels(snapshot, rows)
    counts = Counter(row["review_status"] for row in checked)
    exact, wrong, unconfirmed, false_confirmed = 0, 0, 0, 0
    for row in checked:
        # 1. 사람이 번호를 읽은 행만 완전 일치율의 분모에 포함합니다.
        if row["review_status"] == "VERIFIED_PLATE":
            if row["predicted_status"] != "CONFIRMED":
                unconfirmed += 1
            elif row["predicted_plate"] == row["expected_plate"]:
                exact += 1
            else:
                wrong += 1
        elif row["review_status"] == "NO_PLATE" and row["predicted_status"] == "CONFIRMED":
            false_confirmed += 1
    verified = counts["VERIFIED_PLATE"]
    total = len(checked)
    overview = snapshot["overview"]
    return {"schema_version": 1, "run_id": snapshot["run_id"], "snapshot_sha256": snapshot["snapshot_sha256"],
            "http_enabled": False, "scope": "SAVED_OCR_TRACKS_ONLY", "total_review_rows": total,
            "review_status_counts": {key: counts[key] for key in ("PENDING", "VERIFIED_PLATE", "UNREADABLE", "NO_PLATE", "OUT_OF_SCOPE")},
            "review_complete": counts["PENDING"] == 0,
            "reviewed_fraction": (total - counts["PENDING"]) / total if total else None,
            "verified_plate_rows": verified, "exact_matches": exact, "wrong_confirmed_plates": wrong,
            "unconfirmed_on_verified_plate": unconfirmed, "confirmed_on_no_plate": false_confirmed,
            "exact_match_rate_on_verified_plates": exact / verified if verified else None,
            "source_total_crossings": overview.get("total_crossings", overview.get("crossings_in_run")),
            "note": "사용자가 입력한 검토 결과 기준입니다. 미검출 차량·OCR 미처리 차량과 전체 영상 정확도를 평가하지 않습니다."}

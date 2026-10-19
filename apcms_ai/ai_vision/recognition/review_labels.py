# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/review_labels.py

"""사람이 작성하는 번호판 검토 CSV의 열과 정답 입력 규칙."""

import re
import unicodedata

COLUMNS = ("run_id", "snapshot_sha256", "track_id", "screen_direction", "video_seconds",
           "predicted_status", "predicted_plate", "review_status", "expected_plate", "note")
FIXED_COLUMNS = COLUMNS[:7]
REVIEW_STATUSES = {"PENDING", "VERIFIED_PLATE", "UNREADABLE", "NO_PLATE", "OUT_OF_SCOPE"}


def template_rows(snapshot):
    # 1. AI 예측을 정답 칸에 복사하지 않습니다. 모든 행은 미검토로 시작합니다.
    return [{"run_id": snapshot["run_id"], "snapshot_sha256": snapshot["snapshot_sha256"],
             "track_id": str(item["track_id"]), "screen_direction": item["screen_direction"],
             "video_seconds": str(item["video_seconds"]), "predicted_status": item["plate_status"],
             "predicted_plate": item["plate_number"], "review_status": "PENDING", "expected_plate": "", "note": ""}
            for item in snapshot["items"]]


def validate_labels(snapshot, rows):
    expected = {row["track_id"]: row for row in template_rows(snapshot)}
    checked, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(COLUMNS) or any(not isinstance(v, str) for v in row.values()):
            raise ValueError("검토 CSV의 열이나 셀 형식을 확인해 주세요.")
        track = row["track_id"]
        if track in seen or track not in expected:
            raise ValueError("검토 차량이 중복됐거나 원본에 없는 차량입니다.")
        seen.add(track)
        # 2. 실행·해시·차량·시각·예측 칸은 수정할 수 없습니다.
        if any(row[key] != expected[track][key] for key in FIXED_COLUMNS):
            raise ValueError("AI 결과가 바뀌었거나 검토 CSV의 고정 열이 변경됐습니다.")
        status = row["review_status"].strip()
        plate = re.sub(r"\s+", "", unicodedata.normalize("NFC", row["expected_plate"]))
        if status not in REVIEW_STATUSES:
            raise ValueError("검토 상태를 확인해 주세요.")
        if status == "VERIFIED_PLATE":
            if not re.fullmatch(r"[0-9]{2,3}[가-힣][0-9]{4}", plate):
                raise ValueError("정답은 현재 지원하는 한국 번호판 형식이어야 합니다.")
        elif plate:
            raise ValueError("정답 번호는 VERIFIED_PLATE 상태에서만 입력합니다.")
        if len(row["note"]) > 2000:
            raise ValueError("검토 메모는 2000자 이하여야 합니다.")
        checked.append({**row, "review_status": status, "expected_plate": plate})
    if seen != set(expected):
        raise ValueError("검토 CSV에서 일부 차량 행이 누락됐습니다.")
    return checked

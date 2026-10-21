# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_report_csv.py

"""통과 자료를 Excel에서 열 수 있는 CSV 텍스트로 변환합니다."""

# 1. CSV 생성에 필요한 표준 라이브러리
import csv
# 1-1. 파일을 직접 만들지 않고 메모리 문자열에 CSV를 씁니다.
import io


# 2. CSV에 기록할 열 이름과 순서를 고정합니다.
# 2-1. 행마다 같은 순서로 값을 추출해 헤더와 데이터를 맞춥니다.
FIELDS = ("track_id", "captured_at", "crossing_elapsed_seconds", "plate_status", "plate_number",
          "sample_count", "decision", "receipt_state", "request_attempted",
          "accepted_votes", "required_votes", "minimum_spacing_seconds")
REVIEW_FIELDS = ("review_reason_state", "review_reasons")


# 3. 검증 완료된 보고서의 rows를 CSV 텍스트로 변환합니다.
# 3-1. 반환값은 파일 경로가 아닌 CSV 형식의 문자열입니다.
# 함수 설명: render_csv() — 보고서 표를 엑셀에서 열 수 있는 CSV 문자열로 만듭니다.
def render_csv(report, include_review_reasons=False):
    if type(include_review_reasons) is not bool:
        raise ValueError("검토 사유 열 옵션은 bool이어야 합니다.")
    # 1. 수식으로 해석될 문자열은 앞에 작은따옴표를 붙여 셀 텍스트로 표시합니다.
    # 4. Excel에서 위험한 수식으로 해석될 수 있는 값의 표시를 바꿉니다.
    # 함수 설명: safe() — 셀을 위험한 수식으로 인식하지 않도록 시작 문자를 검사합니다.
    def safe(value):
        # 4-1. None은 빈 셀로 표현합니다.
        if value is None:
            return ""
        # 4-2. =,+,-,@로 시작하는 문자열은 수식 해석을 피하도록 작은따옴표를 붙입니다.
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    # 5. 메모리 스트림과 CSV 작성기를 만들고 제목 행을 기록합니다.
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(FIELDS + REVIEW_FIELDS if include_review_reasons else FIELDS)
    # 6. 통과 기록을 열 순서에 맞춰 하나씩 작성합니다.
    # 6-1. request_attempted가 None이면 UNKNOWN을 표시합니다.
    for row in report["rows"]:
        values = [safe("UNKNOWN" if key == "request_attempted" and row[key] is None else row[key]) for key in FIELDS]
        if include_review_reasons:
            reasons = row.get("review_reasons")
            state = "UNRECORDED" if reasons is None else "HAS_REASONS" if reasons else "NO_REASONS"
            values += [state, "|".join(reasons or [])]
        writer.writerow(values)
    # 7. 작성한 CSV 내용을 문자열로 반환합니다.
    return stream.getvalue()

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_report_csv.py

"""통과 자료를 Excel에서 열 수 있는 CSV 텍스트로 변환합니다."""

import csv
import io


FIELDS = ("track_id", "captured_at", "crossing_elapsed_seconds", "plate_status", "plate_number",
          "sample_count", "decision", "receipt_state", "request_attempted",
          "accepted_votes", "required_votes", "minimum_spacing_seconds")


def render_csv(report):
    # 1. 수식으로 해석될 문자열은 앞에 작은따옴표를 붙여 셀 텍스트로 표시합니다.
    def safe(value):
        if value is None:
            return ""
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(FIELDS)
    for row in report["rows"]:
        writer.writerow([safe("UNKNOWN" if key == "request_attempted" and row[key] is None else row[key]) for key in FIELDS])
    return stream.getvalue()

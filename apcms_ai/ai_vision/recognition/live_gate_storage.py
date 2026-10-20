# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_storage.py

"""주 결과를 덮어쓰지 않고 실행 실패 정보와 가능한 복구 결과를 남깁니다."""

from pathlib import Path

from ai_vision.recognition.local_io import write_json_atomic


def save_failure(output, phase, error, cleanup_errors=0, report=None):
    output = Path(output)
    saved = []
    # 1. summary.json 저장 실패 시 이미 만든 전체 결과를 별도 파일에 한 번 저장합니다.
    if report is not None:
        try:
            write_json_atomic(output / "recovered_summary.json", report)
            saved.append("recovered_summary.json")
        except Exception:
            pass
    diagnostic = {"record_type": "LIVE_GATE_FAILURE", "phase": phase,
                  "error_type": type(error).__name__, "cleanup_errors": cleanup_errors,
                  "report_available_in_memory": report is not None,
                  "recovered_summary_saved": "recovered_summary.json" in saved}
    # 2. 오류 경로·API 키 등이 섞일 수 있는 예외 원문은 저장하지 않습니다.
    try:
        write_json_atomic(output / "failure.json", diagnostic)
        saved.append("failure.json")
    except Exception:
        pass
    return saved

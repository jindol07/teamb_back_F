# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_storage.py

"""주 결과를 덮어쓰지 않고 실행 실패 정보와 가능한 복구 결과를 남깁니다."""

# 1. 출력 경로와 안전한 JSON 저장 함수 가져오기
from pathlib import Path

# 1-1. write_json_atomic은 임시 파일 경유로 완전한 JSON 저장을 시도합니다.
from ai_vision.recognition.local_io import write_json_atomic


# 2. 실행 실패 시 남길 수 있는 기록을 보존합니다.
# 2-1. report가 있으면 복구용 요약 파일을 별도로 저장합니다.
# 2-2. cleanup_errors는 자원 정리 단계의 실패 횟수입니다.
# 함수 설명: save_failure() — 정상 결과 저장 실패 시 복구 요약과 최소한의 오류 기록을 순서대로 남깁니다.
def save_failure(output, phase, error, cleanup_errors=0, report=None):
    # 2-3. 문자열 또는 Path 형태로 전달된 출력 폴더를 통일합니다.
    output = Path(output)
    saved = []
    # 1. summary.json 저장 실패 시 이미 만든 전체 결과를 별도 파일에 한 번 저장합니다.
    # 3. 보고서가 이미 만들어졌다면 recovered_summary.json 저장을 우선 시도합니다.
    if report is not None:
        try:
            write_json_atomic(output / "recovered_summary.json", report)
            saved.append("recovered_summary.json")
        except Exception:
            pass
    # 4. 예외 원문을 제외한 구조화된 오류 정보를 만듭니다.
    # 4-1. 민감한 경로·인증정보 대신 에러 클래스 이름만 기록합니다.
    diagnostic = {"record_type": "LIVE_GATE_FAILURE", "phase": phase,
                  "error_type": type(error).__name__, "cleanup_errors": cleanup_errors,
                  "report_available_in_memory": report is not None,
                  "recovered_summary_saved": "recovered_summary.json" in saved}
    # 2. 오류 경로·API 키 등이 섞일 수 있는 예외 원문은 저장하지 않습니다.
    # 5. 실패 진단 정보를 failure.json으로 남깁니다.
    try:
        write_json_atomic(output / "failure.json", diagnostic)
        saved.append("failure.json")
    except Exception:
        pass
    # 6. 실제 저장에 성공한 파일 이름만 반환합니다.
    return saved

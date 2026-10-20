# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/inspect_live_gate.py

"""실행 폴더의 완료·실패·복구 가능 상태를 모델 없이 확인합니다."""

import argparse
import json
from pathlib import Path

from ai_vision.recognition.live_gate_report import load_report
from ai_vision.recognition.local_io import read_json


def inspect_session(folder):
    folder = Path(folder)
    result = {"record_type": "LIVE_GATE_INSPECTION", "status": "INCOMPLETE",
              "summary_status": "MISSING", "failure_phase": None, "recovery_available": False,
              "stop_reason": None,
              "processed_passages": None, "issues": [], "http_used_by_inspector": False}
    if not folder.is_dir():
        raise ValueError("실행 결과 폴더가 필요합니다.")
    summary = folder / "summary.json"
    try:
        if summary.exists():
            raw = read_json(summary, max_bytes=32 * 1024 * 1024)
            if raw.get("record_type") == "LIVE_GATE_SESSION" and raw.get("status") == "RUNNING":
                # 1. 파일만으로 현재 실행 중인지 비정상 종료인지 판별할 수 없습니다.
                result["summary_status"] = "RUNNING_OR_INTERRUPTED"
            else:
                checked = load_report(summary)
                result.update(summary_status=checked["status"], status=checked["status"],
                              stop_reason=checked["stop_reason"],
                              processed_passages=checked["processed_passages"])
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        result["issues"].append("INVALID_SUMMARY")
    failure = folder / "failure.json"
    if failure.exists():
        try:
            diagnostic = read_json(failure)
            if (diagnostic.get("record_type") != "LIVE_GATE_FAILURE" or
                    diagnostic.get("phase") not in {"INITIALIZATION", "EXECUTION", "FINAL_SAVE"}):
                raise ValueError("실패 기록 형식이 다릅니다.")
            result.update(status="FAILED", failure_phase=diagnostic["phase"])
        except (OSError, ValueError, TypeError):
            result["issues"].append("INVALID_FAILURE_RECORD")
    recovery = folder / "recovered_summary.json"
    if recovery.exists():
        try:
            recovered = load_report(recovery)
            result.update(recovery_available=True, recovered_status=recovered["status"],
                          recovered_passages=recovered["processed_passages"])
            # 2. 복구 파일이 있어도 원래 실행·저장 실패를 정상 완료로 바꾸지 않습니다.
            result["status"] = "FAILED"
        except (OSError, ValueError, TypeError, KeyError, OverflowError):
            result["issues"].append("INVALID_RECOVERY")
    if result["issues"]:
        result["status"] = "CORRUPT"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_session(args.session_dir)
    except (OSError, ValueError):
        parser.exit(1, "실행 결과 폴더를 확인해 주세요.\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "STOPPED":
        parser.exit(1)


if __name__ == "__main__":
    main()

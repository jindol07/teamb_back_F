# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/run_audit.py

"""실행 종류별 진단을 묶고 내부 경로 없는 결과만 반환합니다."""

from pathlib import Path
from collections import Counter
from ai_vision.recognition.local_io import read_json
from ai_vision.recognition.tracking_audit import audit_tracking
from ai_vision.recognition.passage_audit import audit_passages


def audit_run(catalog, run_id):
    folder = catalog.folder(run_id)
    result = {"run_id": run_id, "http_enabled": False, "scope": "SAVED_LOG_CONSISTENCY_ONLY", "checks": []}
    code = "RESULT_SCHEMA"
    try:
        overview = catalog.overview(run_id)
        result["kind"] = overview["kind"]
        if overview["status"] in {"RUNNING", "FAILED"}:
            return {**result, "status": "INCOMPLETE", "reason_code": "RUN_NOT_COMPLETED"}
        result["checks"].append(code)
        if overview["kind"] == "tracking":
            code = "TRACKING_LOGS"
            tracking = audit_tracking(catalog, folder)
            result.update(total_crossings=len(tracking["events"]), observations_checked=tracking["observations_checked"])
            result["checks"].append(code)
            if not tracking["observations_checked"]:
                return {**result, "status": "WARNING", "reason_code": "OBSERVATIONS_NOT_SAVED"}
        else:
            tracking_folder = None
            if overview["kind"] == "pipeline":
                code = "PIPELINE_SOURCES"
                summary = read_json(catalog.safe_file(folder / "summary.json"))
                tracking_folder = Path(summary["tracking_dir"]).resolve()
                if not tracking_folder.is_relative_to(catalog.root):
                    raise ValueError("허용 범위 밖의 추적 폴더입니다.")
                tracking_summary = read_json(catalog.safe_file(tracking_folder / "summary.json"))
                if Path(summary["source_video"]).resolve() != Path(tracking_summary["source"]).resolve():
                    raise ValueError("통합 실행의 원본 영상이 다릅니다.")
                result["checks"].append(code)
            code = "OCR_TRACK_LINKS"
            audited = audit_passages(catalog, run_id, tracking_folder)
            tracking = audited["tracking"]
            result.update(total_crossings=len(tracking["events"]), ocr_processed=audited["processed_tracks"],
                          samples_checked=audited["samples_checked"], observations_checked=True)
            result["checks"].append(code)
            if overview["kind"] == "pipeline":
                directions = Counter(row["direction"] for row in tracking["events"].values())
                if (result["total_crossings"] != overview["total_crossings"] or
                        dict(directions) != {k: v for k, v in overview["crossing_counts"].items() if v}):
                    raise ValueError("통합 실행의 통과 건수·방향이 원본 추적과 다릅니다.")
            if result["ocr_processed"] < result["total_crossings"]:
                return {**result, "status": "WARNING", "reason_code": "OCR_PARTIAL"}
        # 1. PASS는 저장 로그의 일관성 검사 통과이며 인식 정확도 합격이 아닙니다.
        return {**result, "status": "PASS", "reason_code": None}
    except (OSError, ValueError, KeyError, TypeError):
        # 2. 예외 문자열에는 원본 경로가 있을 수 있어 고정된 검사 코드만 제공합니다.
        return {**result, "status": "FAILED", "reason_code": code}

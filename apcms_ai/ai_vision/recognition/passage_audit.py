# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/passage_audit.py

"""OCR 표본을 원래 차량의 통과·관찰 기록과 대조합니다."""

from pathlib import Path
from ai_vision.recognition.local_io import read_json, iter_jsonl
from ai_vision.recognition.result_validation import public_passage
from ai_vision.recognition.tracking_audit import audit_tracking


def audit_passages(catalog, run_id, tracking_folder=None):
    # 1. OCR 요약·중복·번호판 판정을 기존 조회 규칙으로 먼저 검사합니다.
    public = catalog.all_passages(run_id)
    folder, _ = catalog.review_source(run_id)
    summary = read_json(catalog.safe_file(folder / "summary.json"))
    if (summary.get("http_enabled") is not False or type(summary.get("processed_tracks")) is not int or
            summary["processed_tracks"] != len(public) or type(summary.get("confirmed_plates")) is not int or
            summary["confirmed_plates"] != sum(item["plate_status"] == "CONFIRMED" for item in public)):
        raise ValueError("OCR 원본 요약의 처리·확정 건수가 다릅니다.")
    source_run = Path(summary["source_run"]).resolve()
    if not source_run.is_relative_to(catalog.root):
        raise ValueError("OCR의 원본 추적 폴더가 허용 범위 밖입니다.")
    if tracking_folder is not None and source_run != tracking_folder.resolve():
        raise ValueError("통합 실행과 OCR의 원본 추적 폴더가 다릅니다.")
    tracking = audit_tracking(catalog, source_run, require_observations=True)
    if (Path(summary["source_video"]).resolve() != Path(tracking["summary"]["source"]).resolve() or
            type(summary["crossings_in_run"]) is not int or summary["crossings_in_run"] != len(tracking["events"])):
        raise ValueError("OCR 원본 영상·통과 건수가 추적 기록과 다릅니다.")
    by_id = {item["track_id"]: item for item in public}
    seen, sample_count = set(), 0
    for row in iter_jsonl(catalog.safe_file(folder / "passages.jsonl")):
        item = public_passage(row)
        track = item["track_id"]
        if track in seen or by_id.get(track) != item or track not in tracking["events"]:
            raise ValueError("OCR 차량이 원본 통과 기록과 일치하지 않습니다.")
        seen.add(track)
        event = tracking["events"][track]
        if item["screen_direction"] != event["direction"] or abs(item["video_seconds"] - event["video_seconds"]) > .001:
            raise ValueError("OCR 차량의 통과 방향·시각이 다릅니다.")
        sample_frames = set()
        for sample in row["samples"]:
            if sample["frame_index"] in sample_frames:
                raise ValueError("같은 OCR 표본 프레임이 중복됐습니다.")
            sample_frames.add(sample["frame_index"])
            time = tracking["observations"].get((track, sample["frame_index"]))
            # 2. 같은 차량·프레임에서 관찰됐고 통과 전후 표본 범위 안이어야 합니다.
            if (time is None or abs(time - sample["video_seconds"]) > .001 or
                    not event["video_seconds"] - 2 <= sample["video_seconds"] <= event["video_seconds"] + .75):
                raise ValueError("번호판 표본이 해당 차량의 통과 전후 관찰과 다릅니다.")
            sample_count += 1
    if seen != set(by_id):
        raise ValueError("진단 중 OCR 차량 기록이 변경됐습니다.")
    return {"tracking": tracking, "processed_tracks": len(public), "samples_checked": sample_count}

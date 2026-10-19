# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/tracking_audit.py

"""모델 없이 저장된 통과·관찰 로그의 기본 형식과 시각을 검사합니다."""

import math
from collections import Counter
from ai_vision.recognition.local_io import read_json, iter_jsonl


def finite_time(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("영상 시각·좌표가 유효하지 않습니다.")
    return value


def valid_id(value):
    if type(value) is not int or value < 0:
        raise ValueError("차량·프레임 번호가 유효하지 않습니다.")
    return value


def audit_tracking(catalog, folder, require_observations=False):
    summary = read_json(catalog.safe_file(folder / "summary.json"))
    if summary.get("http_enabled") is not False:
        raise ValueError("로컬 전용 추적 결과가 필요합니다.")
    fps = finite_time(summary["source_fps"])
    width, height = summary["width"], summary["height"]
    if fps <= 0 or any(type(v) is not int or v <= 0 for v in (width, height)):
        raise ValueError("원본 FPS와 영상 크기를 확인해 주세요.")
    start = finite_time(summary.get("start_seconds", 0))
    counts = summary["counts"]
    if not isinstance(counts, dict) or any(k not in {"UP", "DOWN"} or type(v) is not int or v < 0 for k, v in counts.items()):
        raise ValueError("추적 방향별 건수가 유효하지 않습니다.")
    events, previous_time = {}, -1

    def frame_time(row):
        frame, time = valid_id(row["frame_index"]), finite_time(row["video_seconds"])
        # 1. 저장된 시각의 소수점 반올림 오차만 허용합니다.
        if abs(frame / fps - time) > .002 or time < start - .002:
            raise ValueError("프레임 번호와 영상 시각이 일치하지 않습니다.")
        return frame, time

    for row in iter_jsonl(catalog.safe_file(folder / "crossings.jsonl")):
        track = valid_id(row["track_id"])
        _, time = frame_time(row)
        if track in events or row["direction"] not in {"UP", "DOWN"} or time < previous_time:
            raise ValueError("통과 ID·방향·시각 순서가 유효하지 않습니다.")
        previous_time = time
        events[track] = row
    actual = Counter(row["direction"] for row in events.values())
    if dict(actual) != {k: v for k, v in counts.items() if v}:
        raise ValueError("통과 로그와 요약 건수가 다릅니다.")
    observations, previous_frames = {}, {}
    path = folder / "observations.jsonl"
    checked = path.exists() or path.is_symlink()
    if not checked and (require_observations or summary.get("observations_saved") is True):
        raise ValueError("필요한 관찰 로그가 없습니다.")
    if checked:
        for row in iter_jsonl(catalog.safe_file(path)):
            track = valid_id(row["track_id"])
            frame, time = frame_time(row)
            box = row["box"]
            if (not isinstance(box, list) or len(box) != 4 or
                    any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in box) or
                    not 0 <= box[0] < box[2] <= width or not 0 <= box[1] < box[3] <= height):
                raise ValueError("관찰 차량 상자가 영상 크기 밖이거나 유효하지 않습니다.")
            # 2. 같은 ID·프레임 중복과 차량별 프레임 역행을 거릅니다.
            if frame <= previous_frames.get(track, -1):
                raise ValueError("차량 관찰 프레임이 중복되거나 역행했습니다.")
            previous_frames[track] = frame
            observations[(track, frame)] = time
        for track, row in events.items():
            if (track, row["frame_index"]) not in observations:
                raise ValueError("통과 차량의 해당 프레임 관찰이 없습니다.")
    return {"summary": summary, "events": events, "observations": observations, "observations_checked": checked}

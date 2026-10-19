# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/review_tracking.py

"""저장된 추적 결과에서 통과 전후 장면과 누락 검토용 연속 장면을 만듭니다."""

import argparse
import csv
import json
import math
import hashlib
from collections import Counter
from pathlib import Path
from ai_vision.recognition.local_io import read_json, iter_jsonl, write_json_atomic


def event_fingerprint(events):
    return hashlib.sha256(json.dumps(events, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()


def validate_existing_review(output, events):
    # 1. 기존 수동 판정이 새 로그에 잘못 붙는 것을 막고 원래 메모를 보존
    audit = output / "audit.json"
    if audit.is_file():
        old = read_json(audit).get("event_fingerprint")
        if old is not None and old != event_fingerprint(events):
            raise ValueError("기존 검토 자료와 통과 로그가 다릅니다. 새 결과 폴더를 사용해 주세요.")
    labels = output / "event_review.csv"
    if labels.is_file():
        with labels.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != len(events):
            raise ValueError("기존 수동 판정표의 기록 수가 다릅니다.")
        for index, (row, event) in enumerate(zip(rows, events), 1):
            try:
                matches = (int(row["event_index"]) == index and int(row["track_id"]) == event["track_id"]
                           and float(row["video_seconds"]) == event["video_seconds"]
                           and row["direction"] == event["direction"])
            except (KeyError, ValueError, TypeError) as error:
                raise ValueError("기존 수동 판정표의 형식이 유효하지 않습니다.") from error
            if not matches:
                raise ValueError("기존 수동 판정표가 다른 차량·통과 기록을 가리킵니다.")


def review_window(summary, fps, total_frames):
    # 2. 잘못된 시각이나 메타데이터로 다른 원본 구간을 검토하지 않도록 검사
    start = summary.get("start_seconds", 0)
    values = (start, fps, summary["source_fps"])
    if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values) or
            fps <= 0 or summary["source_fps"] <= 0 or abs(fps - summary["source_fps"]) > .01 or
            total_frames <= 0 or not 0 <= start < total_frames / fps or
            type(summary["processed_frames"]) is not int or summary["processed_frames"] < 0 or
            type(summary["stride"]) is not int or summary["stride"] < 1):
        raise ValueError("검토할 원본 FPS·시작 시각·프레임 수를 확인해 주세요.")
    duration = min(total_frames / fps - start,
                   summary["processed_frames"] * summary["stride"] / summary["source_fps"])
    return start, duration


# 역할: 저장된 추적 실행 폴더와 예상 방향으로 검토 이미지와 감사 자료를 생성합니다.
def build_review(run_dir, expected_direction):
    # 1. 모델을 재실행하지 않고 기존 설정과 이벤트 로그만 읽습니다.
    import cv2
    import numpy as np

    if expected_direction not in {"UP", "DOWN"}:
        raise ValueError("검토 방향은 UP 또는 DOWN이어야 합니다.")
    summary = read_json(run_dir / "summary.json")
    events = list(iter_jsonl(run_dir / "crossings.jsonl"))
    output = run_dir / "review"
    validate_existing_review(output, events)
    output.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(summary["source"])
    if not cap.isOpened():
        raise ValueError("검토할 원본 영상을 열 수 없습니다.")
    try:
        # 2. ROI 주변을 잘라 멀리 있는 차량도 검토 이미지에서 보이게 합니다.
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or total_frames <= 0:
            raise ValueError("원본 영상의 길이와 FPS를 확인할 수 없습니다.")
        width, height = int(cap.get(3)), int(cap.get(4))
        start_seconds, duration = review_window(summary, fps, total_frames)
        if (width, height) != (summary["width"], summary["height"]):
            raise ValueError("원본 해상도가 추적 결과와 다릅니다.")
        # 2-1. 추적 실행 시 사용한 ROI 픽셀 좌표를 그대로 읽어 검토 이미지에 겹쳐 표시합니다.
        roi = np.array(summary["roi"], dtype=np.int32)
        left = max(0, int(roi[:, 0].min()) - 24)
        right = min(width, int(roi[:, 0].max()) + 24)
        top = max(0, int(roi[:, 1].min()) - 24)
        bottom = min(height, int(roi[:, 1].max()) + 24)
        if left >= right or top >= bottom:
            raise ValueError("검토할 ROI가 원본 영상 안에 없습니다.")

        # 역할: 영상 시각의 원본 프레임을 읽어 ROI·기준선을 표시한 검토 칸을 반환합니다.
        def frame_at(seconds, label):
            # 2-2. 영상 시각을 원본 프레임 번호로 바꾸고 마지막 범위를 넘지 않게 제한
            # 2-3. 영상 시각을 프레임 번호로 바꾼 뒤 0부터 마지막 프레임 사이로 제한합니다.
            index = min(total_frames - 1, max(0, round(seconds * fps)))
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if not ok:
                raise OSError(f"검토 프레임을 읽을 수 없습니다: {index}")
            cv2.polylines(frame, [roi], True, (255, 150, 0), 2)
            cv2.line(frame, (summary["line_x"][0], summary["line_y"]),
                     (summary["line_x"][1], summary["line_y"]), (0, 0, 255), 2)
            crop = frame[top:bottom, left:right]
            # 2-4. 비율을 유지하며 검정 여백을 붙여 모든 검토 칸의 크기를 통일
            # 2-5. 가로와 세로 배율 중 작은 값을 사용해 ROI 이미지를 찌그러뜨리지 않고 칸에 맞춥니다.
            scale = min(384 / crop.shape[1], 216 / crop.shape[0])
            resized = cv2.resize(crop, (max(1, round(crop.shape[1] * scale)),
                                       max(1, round(crop.shape[0] * scale))))
            tile = np.zeros((246, 384, 3), dtype=np.uint8)
            tile[30:30 + resized.shape[0], :resized.shape[1]] = resized
            cv2.putText(tile, f"{index / fps:.2f}s {label}", (6, 21),
                        cv2.FONT_HERSHEY_SIMPLEX, .47, (0, 255, 255), 1)
            return tile

        # 역할: 검토 이미지 행을 페이지 단위 JPEG로 저장하고 파일 이름 목록을 반환합니다.
        def save_rows(rows, prefix, rows_per_page):
            # 2-6. 몇 줄씩 한 이미지에 모아 차량 이동을 나란히 비교
            paths = []
            for start in range(0, len(rows), rows_per_page):
                path = output / f"{prefix}_{start // rows_per_page + 1:02d}.jpg"
                if not cv2.imwrite(str(path), cv2.vconcat(rows[start:start + rows_per_page])):
                    raise OSError(f"검토 이미지 저장 실패: {path}")
                paths.append(path.name)
            return paths

        # 3. 이벤트 전후 0.75초를 표시해 잘못 연결된 차량과 역방향 기록을 검토합니다.
        event_rows = []
        for index, event in enumerate(events, start=1):
            time = event["video_seconds"]
            # 3-1. 리스트 컴프리헨션으로 이전·당시·이후 프레임 세 장을 만들어 가로로 붙입니다.
            event_rows.append(cv2.hconcat([
                frame_at(time + offset, f"#{index} ID{event['track_id']} {event['direction']}")
                for offset in (-.75, 0, .75)]))
        event_pages = save_rows(event_rows, "events", 4)

        # 4. 이벤트가 없는 구간도 포함해 0.5초 간격 장면을 만듭니다.
        # 4-1. 통과한 것으로 기록된 차량만 보면 누락을 발견하기 어려우므로 별도 생성
        # 4-2. 원본에 남은 길이와 추적 실행에서 처리한 예상 길이 중 짧은 쪽을 검토 구간으로 잡습니다.
        # 4-3. 처리 시작 시각부터 0.5초 간격으로 장면을 뽑아 누락 여부를 눈으로 살핍니다.
        tiles = [frame_at(start_seconds + index * .5, "timeline") for index in range(math.ceil(duration * 2))]
        while tiles and len(tiles) % 3:
            tiles.append(np.zeros_like(tiles[0]))
        timeline_pages = save_rows([cv2.hconcat(tiles[i:i + 3])
                                   for i in range(0, len(tiles), 3)], "timeline", 4)

        # 5. 자동 점검과 사람이 판단할 검토 결과를 구분해 저장합니다.
        # 5-1. Counter로 기록된 추적 ID와 방향의 출현 횟수를 따로 셉니다.
        ids = Counter(event["track_id"] for event in events)
        directions = Counter(event["direction"] for event in events)
        report = {
            "event_fingerprint": event_fingerprint(events),
            "expected_direction": expected_direction, "reviewed_seconds": duration,
            "start_seconds": start_seconds,
            "event_count": len(events), "direction_counts": dict(directions),
            "duplicate_track_ids": [key for key, count in ids.items() if count > 1],
            "unexpected_direction_indices": [i + 1 for i, event in enumerate(events)
                                               if event["direction"] != expected_direction],
            "summary_counts_match": dict(directions) == {
                key: value for key, value in summary["counts"].items() if value},
            "manual_review_status": "UNREVIEWED",
            "note": "자동 점검만으로 같은 차량의 ID 변경 중복이나 누락을 판정할 수 없습니다.",
            "event_pages": event_pages, "timeline_pages": timeline_pages,
        }
        write_json_atomic(output / "audit.json", report)
        # 5-2. 기존 사람이 작성한 판정표가 있다면 덮어쓰지 않음
        labels = output / "event_review.csv"
        # 5-3. 이미 사람이 입력한 판정 CSV가 있으면 내용을 보존하지만, 이전 로그와의 일치 여부는 자동 확인하지 않습니다.
        if not labels.exists():
            with labels.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["event_index", "track_id", "video_seconds", "direction", "review_status", "notes"])
                writer.writerows([i + 1, e["track_id"], e["video_seconds"], e["direction"], "UNREVIEWED", ""]
                                 for i, e in enumerate(events))
        lines = ["# 차량 통과 검토", "", "자동 점검 결과: `audit.json`", "",
                 "통과 전후 이미지와 전체 시간 순서 이미지를 모두 검토하세요.",
                 "CSV의 UNREVIEWED는 아직 사람이 판정하지 않은 상태입니다.", ""]
        lines += [f"![{name}]({name})" for name in event_pages + timeline_pages]
        (output / "review.md").write_text("\n\n".join(lines), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        cap.release()


if __name__ == "__main__":
    # 6. 명령에서 받은 기존 실행 폴더와 기대 방향으로 검토 자료를 생성합니다.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--expected-direction", choices=["UP", "DOWN"], required=True)
    options = parser.parse_args()
    build_review(options.run_dir, options.expected_direction)

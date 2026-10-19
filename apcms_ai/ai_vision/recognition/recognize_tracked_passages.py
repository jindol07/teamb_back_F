# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/recognize_tracked_passages.py

"""저장된 통과 ID의 원본 프레임에 OCR을 적용하고 로컬 관찰 결과를 저장합니다."""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.local_io import read_json, iter_jsonl, write_json_atomic


def validate_observation(row):
    # 모델 초기화 전에 좌표·시각·프레임 번호를 검사합니다.
    box, time = row.get("box"), row.get("video_seconds")
    if (type(row.get("frame_index")) is not int or row["frame_index"] < 0 or
            isinstance(time, bool) or not isinstance(time, (int, float)) or not math.isfinite(time) or time < 0 or
            not isinstance(box, (list, tuple)) or len(box) != 4 or
            any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in box) or
            box[0] >= box[2] or box[1] >= box[3]):
        raise ValueError("관찰 로그의 프레임·시각·차량 상자가 유효하지 않습니다.")


def load_tracking_inputs(run_dir, max_tracks=None):
    summary = read_json(run_dir / "summary.json")
    if summary.get("http_enabled") is not False:
        raise ValueError("로컬 전용 추적 결과가 필요합니다.")
    if max_tracks is not None and (type(max_tracks) is not int or max_tracks < 1):
        raise ValueError("max-tracks는 1 이상이어야 합니다.")
    if not Path(summary["source"]).is_file():
        raise ValueError("원본 영상 파일이 없습니다.")
    events = list(iter_jsonl(run_dir / "crossings.jsonl"))
    seen, counts = set(), defaultdict(int)
    for event in events:
        track_id, time = event.get("track_id"), event.get("video_seconds")
        if (type(track_id) is not int or track_id < 0 or track_id in seen or
                event.get("direction") not in {"UP", "DOWN"} or isinstance(time, bool) or
                not isinstance(time, (int, float)) or not math.isfinite(time) or time < 0):
            raise ValueError("통과 로그의 ID·방향·시각 또는 중복 기록을 확인해 주세요.")
        seen.add(track_id)
        counts[event["direction"]] += 1
    if dict(counts) != {key: value for key, value in summary["counts"].items() if value}:
        raise ValueError("추적 요약과 통과 기록 수가 다릅니다.")
    selected = events if max_tracks is None else events[:max_tracks]
    selected_ids = {event["track_id"] for event in selected}
    grouped = defaultdict(list)
    for row in iter_jsonl(run_dir / "observations.jsonl"):
        validate_observation(row)
        if type(row.get("track_id")) is not int or row["track_id"] < 0:
            raise ValueError("관찰 ID가 유효하지 않습니다.")
        if row["track_id"] in selected_ids:
            grouped[row["track_id"]].append(row)
    return summary, events, selected, grouped


# 역할: 한 ID의 관찰 기록에서 통과 시각 근처의 서로 떨어진 프레임을 골라 반환합니다.
def select_samples(observations, crossing_time, limit=3, spacing=.25):
    if (type(limit) is not int or limit < 1 or isinstance(spacing, bool) or
            not isinstance(spacing, (int, float)) or not math.isfinite(spacing) or spacing < .25 or
            isinstance(crossing_time, bool) or not isinstance(crossing_time, (int, float)) or
            not math.isfinite(crossing_time) or crossing_time < 0):
        raise ValueError("표본 선택 횟수·간격·통과 시각을 확인해 주세요.")
    for row in observations:
        validate_observation(row)
    # 1. 통과 전후의 같은 추적 ID만 선택합니다. 다른 ID와 번호판을 합치지 않음
    candidates = [row for row in observations
                  if crossing_time - 2 <= row["video_seconds"] <= crossing_time + .75]
    # 1-1. 크기가 큰 차량 상자를 우선 선택하되 서로 다른 시점의 화면을 사용
    # 1-2. 차량 상자 면적이 큰 프레임을 우선합니다. 이는 번호판 선명도의 직접적인 측정값은 아닙니다.
    candidates.sort(key=lambda row: (row["box"][2] - row["box"][0]) *
                    (row["box"][3] - row["box"][1]), reverse=True)
    selected, seen_frames = [], set()
    for row in candidates:
        if row["frame_index"] in seen_frames:
            continue
        if any(abs(row["video_seconds"] - old["video_seconds"]) < spacing - 1e-9 for old in selected):
            continue
        selected.append(row)
        seen_frames.add(row["frame_index"])
        if len(selected) >= limit:
            break
    return sorted(selected, key=lambda row: row["video_seconds"])


# 역할: 저장된 통과 이벤트와 원본 영상으로 번호판을 읽고 ID별 로컬 결과를 저장합니다.
def run(run_dir, output_dir, max_tracks=None):
    # 2. 기존 추적 결과만 읽습니다. 원본 영상이나 추적 로그는 수정하지 않음
    summary, events, selected_events, grouped = load_tracking_inputs(run_dir, max_tracks)
    if run_dir.resolve() == output_dir.resolve():
        raise ValueError("OCR 출력 폴더는 추적 폴더와 달라야 합니다.")
    output_dir.mkdir(parents=True, exist_ok=False)
    if not selected_events:
        # 빈 구간은 영상이나 OCR 모델을 초기화하지 않고 결과만 저장합니다.
        (output_dir / "passages.jsonl").write_text("", encoding="utf-8")
        write_json_atomic(output_dir / "summary.json", {
            "source_run": str(run_dir.resolve()), "source_video": summary["source"],
            "crossings_in_run": 0, "processed_tracks": 0, "confirmed_plates": 0, "http_enabled": False})
        return
    import cv2
    cap = cv2.VideoCapture(summary["source"])
    if not cap.isOpened():
        raise ValueError("OCR 대상 원본 영상을 열 수 없습니다.")
    outcomes = []
    try:
        # 3. 기존 번호판 탐지·OCR 함수를 재사용. sender와 .env는 불러오지 않음
        from ai_vision.recognition.recognizer import (
            detect_best_plate, crop_plate_from_original, recognize_plate)

        with (output_dir / "passages.jsonl").open("w", encoding="utf-8") as output:
            for event in selected_events:
                track_id = event["track_id"]
                samples = []
                for row in select_samples(grouped[track_id], event["video_seconds"]):
                    # 3-1. OCR은 표시용 영상 대신 선이나 글자를 그리지 않은 원본으로 수행
                    # 3-2. 저장된 원본 프레임 번호로 이동해 추적 결과와 같은 순간의 영상을 읽습니다.
                    cap.set(cv2.CAP_PROP_POS_FRAMES, row["frame_index"])
                    ok, frame = cap.read()
                    if not ok:
                        raise OSError(f"OCR 프레임 읽기 실패: {row['frame_index']}")
                    height, width = frame.shape[:2]
                    x1, y1, x2, y2 = row["box"]
                    # 3-3. 추적 상자가 프레임 바깥으로 나가도 잘라낼 범위를 영상의 실제 너비·높이 안으로 제한합니다.
                    box = (max(0, x1), max(0, y1), min(width, x2), min(height, y2))
                    x1, y1, x2, y2 = box
                    sample = {"frame_index": row["frame_index"], "video_seconds": row["video_seconds"],
                              "plate_number": "", "plate_type": "NOT_DETECTED"}
                    crop = frame[y1:y2, x1:x2]
                    if x2 > x1 and y2 > y1 and crop.size:
                        plate = detect_best_plate(crop)
                        if plate is not None:
                            plate_crop = crop_plate_from_original(frame, box, plate["box"])
                            if plate_crop.size:
                                # 3-4. 인식기가 반환한 번호 문자열과 형식 판정 등을 현재 표본 딕셔너리에 합칩니다.
                                sample.update(recognize_plate(plate_crop))
                                # 3-5. 번호판 상자 탐지 신뢰도이며 OCR 문자 정확도와 다름
                                sample["plate_detection_confidence"] = round(plate["confidence"], 4)
                                if not cv2.imwrite(str(output_dir / f"id_{track_id}_frame_{row['frame_index']}_plate.jpg"), plate_crop):
                                    raise OSError("번호판 검토 사진을 저장하지 못했습니다.")
                    samples.append(sample)

                # 4. 실제 통과 기록이 있는 ID에만 OCR 결과를 연결합니다.
                # 4-1. DOWN/UP을 임의로 ENTRY/EXIT로 바꾸거나 실제 발생 날짜를 만들지 않음
                result = {"track_id": track_id, "screen_direction": event["direction"],
                          "crossing_video_seconds": event["video_seconds"],
                          # 4-2. 같은 ID에서 수집한 여러 OCR 표본으로 확정·충돌·증거 부족을 판정합니다.
                          "plate_consensus": summarize_plate_samples(samples),
                          "samples": samples, "http_enabled": False,
                          # 4-3. 저장 결과는 로컬 관찰 자료로 표시합니다. 이 함수에는 서버 송신 호출이 없습니다.
                          "record_type": "LOCAL_TRACKED_PASSAGE"}
                output.write(json.dumps(result, ensure_ascii=False) + "\n")
                output.flush()
                outcomes.append(result)
                print(f"ID {track_id}: {result['plate_consensus']['status']}", flush=True)
        report = {"source_run": str(run_dir.resolve()), "source_video": summary["source"],
                  "crossings_in_run": len(events), "processed_tracks": len(outcomes),
                  "confirmed_plates": sum(r["plate_consensus"]["status"] == "CONFIRMED" for r in outcomes),
                  "http_enabled": False,
                  "note": "서로 다른 프레임의 반복 인식도 실제 번호판 정답을 보장하지 않습니다."}
        write_json_atomic(output_dir / "summary.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    finally:
        cap.release()


if __name__ == "__main__":
    # 5. --save-observations로 실행한 추적 폴더를 입력으로 사용합니다.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-tracks", type=int)
    args = parser.parse_args()
    if args.max_tracks is not None and args.max_tracks < 1:
        parser.error("max-tracks는 1 이상이어야 합니다.")
    if args.run_dir.resolve() == args.output_dir.resolve():
        parser.error("추적 결과 보존을 위해 다른 출력 폴더를 지정해 주세요.")
    run(args.run_dir, args.output_dir, args.max_tracks)

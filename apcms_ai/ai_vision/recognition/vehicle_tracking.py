# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_tracking.py

# 영상에서 차량을 추적하고 통과 결과를 로컬 파일에만 저장

import argparse
import importlib.util
import json
import os
from contextlib import nullcontext

from pathlib import Path
from time import perf_counter

from ai_vision.paths import MODEL_DIR, RESULT_DIR
from ai_vision.recognition.line_crossing import LineCrossingCounter
from ai_vision.recognition.tracking_config import parse_with_config


# 역할: 명령행 영상 경로와 분석 설정을 읽고 유효성을 검사해 설정값을 반환합니다.
def parse_args():
    # 1. traffic.mp4의 가까운 차로를 기본 실험 영역으로 사용
    # 1-1. argparse: 실행 명령 뒤에 붙인 --source, --stride 등의 값을 읽는 기능
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=RESULT_DIR / "recognition" / "traffic_tracking")
    parser.add_argument("--line-y", type=float, default=0.60)
    # 1-2. 좌표는 해상도에 대한 비율: line-y=0.60이면 높이 720의 60%인 y=432
    parser.add_argument("--line-x", nargs=2, type=float, default=(0.15, 0.90))
    parser.add_argument("--roi", nargs=8, type=float,
                        default=(0.10, 1.0, 0.365, 0.24, 0.64, 0.24, 0.92, 1.0))
    # 1-3. ROI(관심 영역): 네 꼭짓점의 x/y 비율 8개로 분석할 차로만 지정
    parser.add_argument("--stride", type=int, default=2)
    # 1-4. stride=2: 두 프레임 중 하나 처리. 60fps 원본이면 초당 30장을 분석
    parser.add_argument("--max-seconds", type=float, default=None)
    # 1-5. 특정 오류 구간만 재현할 때 사용. 시작 시각은 원본 영상 기준이며 로그도 원본 시각 유지
    parser.add_argument("--start-seconds", type=float, default=0)
    parser.add_argument("--save-observations", action="store_true")
    # 1-6. 선택 옵션: 프레임별 ID/중심점/확정 상태를 남겨 ID 변경과 누락 원인을 추적
    parser.add_argument("--imgsz", type=int, default=640)
    # 1-7. NMS: 한 물체에 겹쳐 붙은 탐지 상자를 줄이는 후처리. 작을수록 강하게 제거
    parser.add_argument("--nms-iou", type=float, default=0.5)
    parser.add_argument("--agnostic-nms", action="store_true")
    # 1-8. 추적 방식만 바꿔 비교. 모델·기준선·전송 동작은 그대로 유지
    parser.add_argument("--tracker", choices=["bytetrack", "botsort"], default="bytetrack")
    # 1-9. 차량 종류를 다르게 예측한 겹치는 상자도 함께 제거할 때만 선택
    args = parse_with_config(parser)
    if (args.stride < 1 or args.imgsz < 32 or args.start_seconds < 0 or
            not 0 < args.nms_iou <= 1 or
            not 0 < args.line_y < 1 or
            not 0 <= args.line_x[0] < args.line_x[1] <= 1 or
            any(not 0 <= coordinate <= 1 for coordinate in args.roi) or
            (args.max_seconds is not None and args.max_seconds <= 0)):
        parser.error("좌표는 0~1, stride/imgsz/seconds는 양수로 지정해 주세요.")
    return args


# 역할: 영상에서 차량 ID를 추적하고 통과 이벤트·진단 로그·표시 영상을 로컬에 저장합니다.
def run(args):
    # 2. 자동 패키지 설치를 막고 OCR·송신 모듈은 불러오지 않습니다.
    # 2-1. YOLO가 부족한 의존성을 실행 중 자동으로 설치하려 하지 않도록 설정합니다.
    os.environ["YOLO_AUTOINSTALL"] = "false"
    if importlib.util.find_spec("lap") is None:
        raise RuntimeError("추적에 필요한 lap 패키지를 먼저 설치해 주세요.")
    import cv2
    import numpy as np
    from ultralytics import YOLO

    model_path = MODEL_DIR / "yolo11n.pt"
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    cap = cv2.VideoCapture(str(args.source))
    # 2-2. VideoCapture: 영상 파일을 열고 read()를 호출할 때마다 다음 한 장을 읽음
    writer = None
    started = perf_counter()
    try:
        # 2-3. 입력 영상의 FPS(초당 프레임 수)와 해상도를 확인합니다.
        if not cap.isOpened():
            raise ValueError(f"영상을 열 수 없습니다: {args.source}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        width, height = int(cap.get(3)), int(cap.get(4))
        if fps <= 0 or width <= 0 or height <= 0:
            raise ValueError("영상의 해상도 또는 FPS를 확인할 수 없습니다.")
        start_frame = round(args.start_seconds * fps)
        if start_frame >= int(cap.get(cv2.CAP_PROP_FRAME_COUNT)):
            raise ValueError("시작 시각이 영상 길이보다 짧아야 합니다.")
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        # 2-4. 처리한 프레임을 MP4 영상으로 저장할 준비를 합니다.
        video_path = args.output_dir / "tracking.mp4"
        writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"),
                                 fps / args.stride, (width, height))
        # 2-5. 저장 FPS도 stride로 나눠 프레임을 줄여도 원본과 같은 시간 동안 재생되게 함
        if not writer.isOpened():
            raise OSError("결과 영상 저장기를 열 수 없습니다.")
        # 2-6. 비율 좌표를 실제 영상의 픽셀 좌표로 변환합니다.
        # 2-7. 리스트 컴프리헨션은 비율 x·y 네 쌍을 영상 픽셀의 다각형 꼭짓점으로 바꿉니다.
        roi = np.array([(int(args.roi[i] * width), int(args.roi[i + 1] * height))
                        for i in range(0, 8, 2)], dtype=np.int32)
        line_y = int(args.line_y * height)
        x_min, x_max = (int(value * width) for value in args.line_x)
        # 2-8. 기본 여유 폭·연속 프레임·공백 조건은 판별 클래스 기본값을 사용하고 속도 한계만 높이에 맞춥니다.
        counter = LineCrossingCounter(line_y, x_min, x_max, max_speed=height * 1.25)
        # 2-9. 기존 차량 모델을 로딩하고 차량 종류에 해당하는 클래스만 선택합니다.
        model = YOLO(model_path)
        # 2-10. 모델의 클래스 이름 사전에서 차량 종류에 해당하는 번호만 골라 추적에 전달합니다.
        classes = [key for key, value in model.names.items()
                   if value in {"car", "truck", "bus", "motorcycle"}]
        frame_index, processed = start_frame, 0
        # 2-11. frame_index는 원본 프레임 번호, processed는 실제로 분석한 프레임 수
        events = []
        counts = {"DOWN": 0, "UP": 0}
        seen_ids = set()

        # 3. 원본 프레임 시각을 사용하고 결과 영상의 재생 속도를 맞춥니다.
        # 3-1. 진단 옵션을 끈 경우에는 파일을 만들지 않고 None을 사용
        # 3-2. 저장 옵션이 꺼지면 nullcontext(None)으로 같은 with 구조를 사용하되 관찰 파일은 만들지 않습니다.
        observation_file = ((args.output_dir / "observations.jsonl").open("w", encoding="utf-8")
                            if args.save_observations else nullcontext(None))
        with (args.output_dir / "crossings.jsonl").open("w", encoding="utf-8") as log, observation_file as observations:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                # 3-3. 영상 시작부터의 시각을 원본 프레임 번호와 FPS로 계산합니다.
                timestamp = frame_index / fps
                # 3-4. 예) 60fps 영상의 120번 프레임이면 영상 시작 후 2초 지점
                current_index = frame_index
                frame_index += 1
                if args.max_seconds is not None and timestamp >= start_frame / fps + args.max_seconds:
                    break
                if (current_index - start_frame) % args.stride:
                    # 3-5. 나머지가 0인 프레임만 분석: stride=2이면 0, 2, 4, ... 처리
                    continue
                counter.expire(timestamp)
                # 3-6. YOLO로 차량을 찾고 선택한 추적기로 이전 프레임의 차량과 연결합니다.
                # 3-7. persist=True: 프레임마다 추적 상태를 유지해 같은 차량의 ID를 이어 감
                # 3-8. conf: 최소 탐지 신뢰도, iou: 겹치는 탐지 상자를 줄이는 NMS 기준
                result = model.track(frame, persist=True, tracker=f"{args.tracker}.yaml",
                                     classes=classes, conf=0.25, iou=args.nms_iou,
                                     agnostic_nms=args.agnostic_nms, imgsz=args.imgsz,
                                     verbose=False)[0]
                if result.boxes.id is not None:
                    # 3-9. ID가 부여된 차량이 있는 경우에만 기준선 판별을 수행
                    for box in result.boxes:
                        track_id = int(box.id.item())
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        center = ((x1 + x2) / 2, (y1 + y2) / 2)
                        # 3-10. 차량 중심점이 관심 영역 밖이면 집계와 표시에서 제외합니다.
                        # 3-11. pointPolygonTest(): 영역 밖은 음수, 테두리는 0, 내부는 양수
                        # 3-12. 차량 중심점이 ROI 경계 포함 내부에 있는 경우에만 이후 계산을 진행합니다.
                        if cv2.pointPolygonTest(roi, center, False) < 0:
                            continue
                        # 3-13. ROI 안에서 본 고유 추적 ID를 세는 용도이며 실제 차량 대수의 정답은 아닙니다.
                        seen_ids.add(track_id)
                        # 3-14. 통과가 확정되면 딕셔너리, 아니면 None을 반환합니다.
                        event = counter.update(track_id, center, timestamp)
                        if observations is not None:
                            # 3-15. 디버깅용 내부 상태이며 서버 이벤트와는 무관한 로컬 기록
                            state = counter.states[track_id]
                            observations.write(json.dumps({
                                "frame_index": current_index, "video_seconds": round(timestamp, 3),
                                "track_id": track_id, "box": [x1, y1, x2, y2], "center": center,
                                "confidence": round(float(box.conf.item()), 4),
                                "confirmed_side": state.side, "candidate_side": state.candidate,
                                "candidate_count": state.candidate_count,
                                "counted": track_id in counter.counted_ids}) + "\n")
                        # 3-16. update()가 None이면 아직 통과 미확정이고 딕셔너리를 반환하면 확정 이벤트를 기록합니다.
                        if event:
                            event.update({"frame_index": current_index,
                                          "vehicle_type": model.names[int(box.cls.item())],
                                          "detection_confidence": round(float(box.conf.item()), 4)})
                            events.append(event)
                            counts[event["direction"]] += 1
                            log.write(json.dumps(event, ensure_ascii=False) + "\n")
                            # 3-17. JSONL: 한 줄에 이벤트 하나 저장. flush()로 대기 중인 내용을 파일에 반영
                            log.flush()
                            print(json.dumps(event, ensure_ascii=False), flush=True)
                        # 3-18. OpenCV 색상은 BGR 순서; 집계한 ID는 노랑, 나머지는 초록
                        color = (0, 255, 255) if track_id in counter.counted_ids else (0, 255, 0)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        cv2.circle(frame, tuple(map(int, center)), 4, color, -1)
                        cv2.putText(frame, f"ID {track_id}", (x1, max(20, y1 - 5)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                # 3-19. 관심 영역, 기준선, 누적 통과 수를 영상 위에 표시합니다.
                cv2.polylines(frame, [roi], True, (255, 150, 0), 2)
                cv2.line(frame, (x_min, line_y), (x_max, line_y), (0, 0, 255), 3)
                cv2.putText(frame, f"LOCAL ONLY | DOWN {counts['DOWN']} UP {counts['UP']} | {timestamp:.1f}s",
                            (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                # 3-20. 상자·ROI·기준선이 표시된 영상 프레임을 결과 MP4에 추가합니다.
                writer.write(frame)
                # 3-21. 첫 처리 장면과 가장 최근 통과 장면은 사진으로도 남겨 확인하기 쉽게 함
                if processed == 0:
                    cv2.imwrite(str(args.output_dir / "preview.jpg"), frame)
                if events and events[-1]["frame_index"] == current_index:
                    cv2.imwrite(str(args.output_dir / "last_crossing.jpg"), frame)
                processed += 1
                if processed % 300 == 0:
                    print(f"진행: {timestamp:.1f}초 / {processed}프레임", flush=True)

        # 4. 서버 이벤트와 구분되는 실험 결과 및 실행 설정을 남깁니다.
        summary = {"source": str(args.source.resolve()), "source_fps": fps,
                   "width": width, "height": height, "stride": args.stride,
                   "processed_frames": processed, "counts": counts,
                   "start_seconds": start_frame / fps,
                   "observations_saved": args.save_observations,
                   "unique_track_ids_in_roi": len(seen_ids),
                   "line_y": line_y, "line_x": [x_min, x_max], "roi": roi.tolist(),
                   "margin_pixels": 12, "stable_frames": 3, "max_gap_seconds": 1.0,
                   "max_speed_pixels_per_second": height * 1.25,
                   "model": str(model_path), "tracker": f"{args.tracker}.yaml",
                   "confidence_threshold": 0.25, "nms_iou": args.nms_iou, "imgsz": args.imgsz,
                   "agnostic_nms": args.agnostic_nms,
                   "config_file": str(args.config.resolve()) if args.config else None,
                   "deduplication": "once per tracker ID per run; ID switches may overcount",
                   "http_enabled": False, "elapsed_seconds": round(perf_counter() - started, 2)}
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    finally:
        # 5. 정상 종료뿐 아니라 오류가 발생해도 영상 파일과 저장기를 닫습니다.
        # 5-1. writer.release()까지 실행되어야 MP4 저장이 마무리됨
        cap.release()
        if writer is not None:
            writer.release()


# 6. 실행부 (이 모듈을 직접 실행했을 때만)
if __name__ == "__main__":
    run(parse_args())

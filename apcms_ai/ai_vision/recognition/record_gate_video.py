# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/record_gate_video.py
"""웹캠에서 짧은 원본 영상을 저장합니다. 인식이나 서버 전송은 수행하지 않습니다."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter as monotonic
import math
import hashlib

from ai_vision.paths import RESULT_DIR
from ai_vision.camera_runtime import open_camera, require_display, release_resources, CAMERA_BACKENDS, validate_camera_backend
from ai_vision.recognition.local_io import write_json_atomic, read_json


# 역할: 카메라 번호, 최대 촬영 시간, 저장 폴더를 받아 원본 MP4와 촬영 정보를 생성합니다.
def record(camera, seconds, output_dir, preview=True, camera_backend='default', config_path=None,
           wait_for_start=False, check_vehicle=False):
    # 1. 운영체제에 맞는 백엔드로 USB 웹캠을 엽니다.
    # 1-1. 파일을 import하는 것만으로는 카메라가 열리지 않으며 명령 실행 시 시작
    import cv2

    if (type(camera) is not int or not 0 <= camera <= 99 or type(seconds) not in (int, float)
            or not math.isfinite(seconds) or not 0 < seconds <= 300 or type(preview) is not bool
            or type(wait_for_start) is not bool or (wait_for_start and not preview)
            or type(check_vehicle) is not bool or (check_vehicle and (not wait_for_start or config_path is None))):
        raise ValueError("카메라 번호·촬영 시간·미리보기 옵션을 확인해 주세요.")
    validate_camera_backend(camera_backend)
    config = read_json(config_path) if config_path is not None else None
    if config is not None:
        from ai_vision.parking.parking_validation import validate_spaces
        from ai_vision.parking.parking_calibration import validate_resolution
        validate_spaces(config)
        validate_resolution(config['image_width'], config['image_height'])
    if preview:
        require_display()
    checker = None
    if check_vehicle:
        # 준비 단계에서만 차량 모델을 실행합니다. 녹화 중 프레임 속도를 떨어뜨리지 않습니다.
        import os
        os.environ['YOLO_AUTOINSTALL'] = 'false'
        from ultralytics import YOLO
        from ai_vision.paths import MODEL_DIR
        from ai_vision.recognition.model_files import require_model_file
        from ai_vision.parking.vehicle_space_tracker import VehicleSpaceTracker
        require_model_file(MODEL_DIR / 'yolo11n.pt')
        model = YOLO(MODEL_DIR / 'yolo11n.pt')
        classes = [key for key, name in model.names.items() if name in {'car', 'truck', 'bus', 'motorcycle'}]
        if not classes:
            raise ValueError('차량 종류가 포함된 모델이 필요합니다.')
        geometry = VehicleSpaceTracker(config)
        def checker(frame):
            result = model.predict(frame, classes=classes, conf=.25, imgsz=640, verbose=False)[0]
            boxes = [box.xyxy[0].tolist() for box in result.boxes]
            visible = any(geometry._space(box) is not None for box in boxes)
            # 휴대폰 사진이 차량으로 잡혔는지와 구획 경계 조건을 별도로 안내합니다.
            status = 'VEHICLE NOT DETECTED' if not boxes else ('VEHICLE IN SPACE' if visible else 'VEHICLE OUTSIDE SPACE')
            view.source_label = status
            return visible

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # 1-2. 매 촬영마다 새 이름으로 저장해 이전 테스트 영상을 덮어쓰지 않음
    # 1-3. 촬영마다 날짜·시각·마이크로초를 이름에 넣어 기존 MP4를 덮어쓰지 않도록 합니다.
    name = datetime.now().strftime("gate_%Y%m%d_%H%M%S_%f")
    video_path = output_dir / f"{name}.mp4"
    cap = open_camera(camera) if camera_backend == 'default' else open_camera(camera, backend=camera_backend)
    writer = None
    frames = 0
    started = None
    ended = None
    stopped_by_key = False
    view = None
    frame_times = []
    recording_started_at = None
    try:
        if not cap.isOpened():
            raise OSError(f"{camera}번 웹캠을 열 수 없습니다. 다른 프로그램의 카메라 사용 여부를 확인해 주세요.")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config['image_width'] if config else 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config['image_height'] if config else 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        # 2. 실제로 읽힌 해상도로 저장기를 만듭니다. 요청한 해상도와 다를 수 있음
        ok, frame = cap.read()
        if not ok:
            raise OSError("웹캠에서 첫 프레임을 읽을 수 없습니다.")
        height, width = frame.shape[:2]
        if config is not None and (width, height) != (config['image_width'], config['image_height']):
            raise ValueError('카메라와 구획 설정의 해상도가 다릅니다.')
        if wait_for_start:
            # 준비 화면은 저장하지 않습니다. 스페이스바 이후 프레임부터 시험 자료입니다.
            from ai_vision.parking.parking_preview import ParkingPreview
            view = ParkingPreview(config, source_label=f'Camera {camera} / {camera_backend}')
            ready_frame = (view.wait_until_ready(cap, check_ready=checker) if checker is not None
                           else view.wait_until_ready(cap))
            if ready_frame is None:
                return {'status': 'CANCELLED', 'http_enabled': False}
            ok, frame = cap.read()
            if not ok or frame.shape[:2] != (height, width):
                raise OSError('시작 직후 카메라 프레임을 확인할 수 없습니다.')
        # 2-1. 카메라가 보고한 FPS가 비정상적이면 인코딩용 값으로 30을 사용합니다.
        reported_fps = cap.get(cv2.CAP_PROP_FPS)
        fps = reported_fps if 1 <= reported_fps <= 120 else 30.0
        writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            raise OSError("촬영 영상 저장기를 열 수 없습니다.")
        print(f"촬영 시작: 카메라 {camera}, 최대 {seconds}초. Ctrl+C로 종료", flush=True)
        # 2-2. monotonic()은 시스템 시계 변경에 영향받지 않는 경과 시간 측정용 시계입니다.
        started = monotonic()
        recording_started_at = datetime.now().astimezone().isoformat()
        while True:
            elapsed = monotonic() - started
            if elapsed >= seconds:
                break
            # 3. 파일에는 안내 문구 없는 원본을 저장하고 화면 복사본에만 안내 표시
            writer.write(frame)
            frame_times.append(elapsed)
            frames += 1
            if frames >= 36000:
                raise ValueError('촬영 프레임 수 한도를 초과했습니다.')
            # 3-1. 화면 표시용 복사본에만 글자를 그려 저장 파일의 원본 프레임을 유지합니다.
            if view is not None:
                if view.show(frame) == ord('q'):
                    stopped_by_key = True
                    break
            elif preview:
                display = frame.copy()
                cv2.putText(display, f"RECORDING {elapsed:.1f}s / {seconds:.1f}s | Q: stop",
                        (12, 30), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 2)
                cv2.imshow("APCMS Gate Recording", display)
            # 3-2. waitKey()에서 키 입력을 받아 Q 키이면 시간 제한 전에 촬영을 끝냅니다.
            if preview and view is None and cv2.waitKey(1) & 0xFF == ord("q"):
                stopped_by_key = True
                break
            ok, frame = cap.read()
            if not ok:
                raise OSError("촬영 중 웹캠 프레임을 읽지 못했습니다.")
            # 3-3. 중간에 카메라 해상도가 바뀌면 저장기의 고정 크기와 달라지므로 오류로 처리합니다.
            if frame.shape[:2] != (height, width):
                raise ValueError("촬영 중 해상도가 변경되었습니다.")
        ended = monotonic()
    finally:
        # 4. 오류가 나거나 사용자가 종료해도 카메라와 저장기를 닫습니다.
        try:
            release_resources(cap, writer)
        finally:
            if view is not None:
                view.close()
            elif preview:
                cv2.destroyAllWindows()

    # 5. 카메라의 표시 FPS와 실제 수집 속도를 별도로 남깁니다.
    # 5-1. 저장 영상 시각은 인코딩 FPS 기준이며 실제 시각과 차이가 날 수 있음
    elapsed = ended - started
    with video_path.open('rb') as video_file:
        video_sha256 = hashlib.file_digest(video_file, 'sha256').hexdigest()
    report = {"video": str(video_path.resolve()), "camera_index": camera,
              "video_sha256": video_sha256,
              "status": "STOPPED" if stopped_by_key else "COMPLETED",
              "camera_backend": camera_backend, "recording_started_at": recording_started_at,
              "preparation_vehicle_check": check_vehicle,
              "frame_times_seconds": frame_times,
              "width": width, "height": height, "encoded_fps": fps,
              "captured_frames": frames, "capture_wall_seconds": round(elapsed, 3),
              # 5-2. 저장 영상 길이는 실제 경과 시간이 아니라 프레임 수를 인코딩 FPS로 나눈 값입니다.
              "encoded_duration_seconds": round(frames / fps, 3),
              "measured_capture_fps": round(frames / elapsed, 3) if elapsed else 0,
              "stopped_by_key": stopped_by_key, "http_enabled": False}
    # 5-3. MP4와 같은 파일명에 확장자만 JSON으로 바꾸어 촬영 정보를 기록합니다.
    write_json_atomic(video_path.with_suffix(".json"), report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return report


if __name__ == "__main__":
    # 6. 실행 옵션. 기존 인식용 카메라 0번을 기본으로 사용
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--no-preview", action="store_true", help="창·키 입력 없이 녹화 (서버용)")
    parser.add_argument("--output-dir", type=Path, default=RESULT_DIR / "recognition" / "gate_recordings")
    parser.add_argument('--camera-backend', choices=CAMERA_BACKENDS, default='default')
    parser.add_argument('--config', type=Path, help='주차 구획 설정과 같은 해상도로 촬영')
    parser.add_argument('--wait-for-start', action='store_true', help='구도 확인 후 스페이스바로 촬영 시작')
    parser.add_argument('--check-vehicle', action='store_true', help='준비 화면에 차량 탐지 상태 표시. 시작을 차단하지 않음')
    args = parser.parse_args()
    if args.camera < 0 or not 0 < args.seconds <= 300:
        parser.error("카메라 번호는 0 이상, 촬영 시간은 0초 초과 300초 이하로 지정해 주세요.")
    record(args.camera, args.seconds, args.output_dir, preview=not args.no_preview,
           camera_backend=args.camera_backend, config_path=args.config, wait_for_start=args.wait_for_start,
           check_vehicle=args.check_vehicle)

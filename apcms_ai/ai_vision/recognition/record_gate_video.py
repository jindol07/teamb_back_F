# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/record_gate_video.py
"""웹캠에서 짧은 원본 영상을 저장합니다. 인식이나 서버 전송은 수행하지 않습니다."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import monotonic

from ai_vision.paths import RESULT_DIR
from ai_vision.camera_runtime import open_camera, require_display, release_resources
from ai_vision.recognition.local_io import write_json_atomic


# 역할: 카메라 번호, 최대 촬영 시간, 저장 폴더를 받아 원본 MP4와 촬영 정보를 생성합니다.
def record(camera, seconds, output_dir, preview=True):
    # 1. 운영체제에 맞는 백엔드로 USB 웹캠을 엽니다.
    # 1-1. 파일을 import하는 것만으로는 카메라가 열리지 않으며 명령 실행 시 시작
    import cv2

    if type(camera) is not int or camera < 0 or type(seconds) not in (int, float) or not 0 < seconds <= 300 or type(preview) is not bool:
        raise ValueError("카메라 번호·촬영 시간·미리보기 옵션을 확인해 주세요.")
    if preview:
        require_display()

    output_dir.mkdir(parents=True, exist_ok=True)
    # 1-2. 매 촬영마다 새 이름으로 저장해 이전 테스트 영상을 덮어쓰지 않음
    # 1-3. 촬영마다 날짜·시각·마이크로초를 이름에 넣어 기존 MP4를 덮어쓰지 않도록 합니다.
    name = datetime.now().strftime("gate_%Y%m%d_%H%M%S_%f")
    video_path = output_dir / f"{name}.mp4"
    cap = open_camera(camera)
    writer = None
    frames = 0
    started = None
    ended = None
    stopped_by_key = False
    try:
        if not cap.isOpened():
            raise OSError(f"{camera}번 웹캠을 열 수 없습니다. 다른 프로그램의 카메라 사용 여부를 확인해 주세요.")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        # 2. 실제로 읽힌 해상도로 저장기를 만듭니다. 요청한 해상도와 다를 수 있음
        ok, frame = cap.read()
        if not ok:
            raise OSError("웹캠에서 첫 프레임을 읽을 수 없습니다.")
        height, width = frame.shape[:2]
        # 2-1. 카메라가 보고한 FPS가 비정상적이면 인코딩용 값으로 30을 사용합니다.
        reported_fps = cap.get(cv2.CAP_PROP_FPS)
        fps = reported_fps if 1 <= reported_fps <= 120 else 30.0
        writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            raise OSError("촬영 영상 저장기를 열 수 없습니다.")
        print(f"촬영 시작: 카메라 {camera}, 최대 {seconds}초. Ctrl+C로 종료", flush=True)
        # 2-2. monotonic()은 시스템 시계 변경에 영향받지 않는 경과 시간 측정용 시계입니다.
        started = monotonic()
        while True:
            elapsed = monotonic() - started
            if elapsed >= seconds:
                break
            # 3. 파일에는 안내 문구 없는 원본을 저장하고 화면 복사본에만 안내 표시
            writer.write(frame)
            frames += 1
            # 3-1. 화면 표시용 복사본에만 글자를 그려 저장 파일의 원본 프레임을 유지합니다.
            if preview:
                display = frame.copy()
                cv2.putText(display, f"RECORDING {elapsed:.1f}s / {seconds:.1f}s | Q: stop",
                        (12, 30), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 2)
                cv2.imshow("APCMS Gate Recording", display)
            # 3-2. waitKey()에서 키 입력을 받아 Q 키이면 시간 제한 전에 촬영을 끝냅니다.
            if preview and cv2.waitKey(1) & 0xFF == ord("q"):
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
            if preview:
                cv2.destroyAllWindows()

    # 5. 카메라의 표시 FPS와 실제 수집 속도를 별도로 남깁니다.
    # 5-1. 저장 영상 시각은 인코딩 FPS 기준이며 실제 시각과 차이가 날 수 있음
    elapsed = ended - started
    report = {"video": str(video_path.resolve()), "camera_index": camera,
              "width": width, "height": height, "encoded_fps": fps,
              "captured_frames": frames, "capture_wall_seconds": round(elapsed, 3),
              # 5-2. 저장 영상 길이는 실제 경과 시간이 아니라 프레임 수를 인코딩 FPS로 나눈 값입니다.
              "encoded_duration_seconds": round(frames / fps, 3),
              "measured_capture_fps": round(frames / elapsed, 3) if elapsed else 0,
              "stopped_by_key": stopped_by_key, "http_enabled": False}
    # 5-3. MP4와 같은 파일명에 확장자만 JSON으로 바꾸어 촬영 정보를 기록합니다.
    write_json_atomic(video_path.with_suffix(".json"), report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    # 6. 실행 옵션. 기존 인식용 카메라 0번을 기본으로 사용
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--no-preview", action="store_true", help="창·키 입력 없이 녹화 (서버용)")
    parser.add_argument("--output-dir", type=Path, default=RESULT_DIR / "recognition" / "gate_recordings")
    args = parser.parse_args()
    if args.camera < 0 or not 0 < args.seconds <= 300:
        parser.error("카메라 번호는 0 이상, 촬영 시간은 0초 초과 300초 이하로 지정해 주세요.")
    record(args.camera, args.seconds, args.output_dir, preview=not args.no_preview)

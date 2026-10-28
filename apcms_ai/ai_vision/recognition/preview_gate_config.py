# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/preview_gate_config.py

"""파일 또는 명시한 카메라의 한 프레임에 ROI·통과선을 표시합니다."""

import argparse
from pathlib import Path

import cv2
import numpy as np

from ai_vision.recognition.local_io import read_json
from ai_vision.recognition.tracking_config import validate_config
from ai_vision.recognition.read_camera_frame import read_camera_frame
from ai_vision.camera_runtime import require_display


class LiveGatePreview:
    """실시간 시험의 ROI·기준선을 보여줍니다. 프레임 파일은 저장하지 않습니다."""

    def __init__(self, config, down_direction):
        # 1. 화면 없는 서버에서는 Qt 창을 만들기 전에 안내합니다.
        self.config = validate_config(config)
        if down_direction not in {'ENTRY', 'EXIT'}:
            raise ValueError("화면 아래쪽의 입출차 방향을 지정하세요.")
        require_display()
        self.direction = down_direction
        self._shown = False
        self._name = 'APCMS Live Gate - Q to stop'

    def __call__(self, frame):
        # 2. 원본 프레임 대신 복사본에 선을 그려 OCR 입력을 훼손하지 않습니다.
        rendered = render_preview(frame, self.config, self.direction)
        from ai_vision.safety.preview_overlay import draw_configured_overlay
        rendered=draw_configured_overlay(rendered)
        self._shown = True
        cv2.imshow(self._name, rendered)
        return (cv2.waitKey(1) & 0xFF) != ord('q')

    def wait_until_ready(self, capture):
        # 측정 시계·세션을 만들기 전에 구도를 맞춥니다. 준비 시간은 60초 제한에 포함하지 않습니다.
        print("카메라 구도를 맞추세요. 창을 클릭하고 스페이스바를 누르면 측정을 시작합니다. Q는 취소입니다.", flush=True)
        if not capture.isOpened():
            raise ValueError("카메라를 열 수 없습니다.")
        while True:
            ok, frame = capture.read()
            if not ok:
                raise ValueError("준비 중 카메라 프레임을 읽지 못했습니다.")
            rendered = render_preview(frame, self.config, self.direction)
            cv2.putText(rendered, 'SPACE: start / Q: quit', (4, 55), cv2.FONT_HERSHEY_SIMPLEX,
                        .5, (0, 255, 255), 1, cv2.LINE_AA)
            self._shown = True
            cv2.imshow(self._name, rendered)
            key = cv2.waitKey(20) & 0xFF
            if key == ord('q'):
                return False
            if key == ord(' '):
                print("준비 완료. 지금부터 측정을 시작합니다.", flush=True)
                return True

    def close(self):
        # 3. 이 도구가 연 창만 닫습니다. 다른 프로그램의 OpenCV 창은 유지합니다.
        if self._shown:
            self._shown = False
            cv2.destroyWindow(self._name)


def render_preview(frame, config, down_direction):
    # 1. 실시간 처리기와 같은 비율 좌표를 사용하고 원본 배열은 보존합니다.
    config = validate_config(config)
    if down_direction not in {"ENTRY", "EXIT"}:
        raise ValueError("DOWN 방향을 ENTRY 또는 EXIT로 지정해 주세요.")
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3
            or frame.shape[2] != 3 or min(frame.shape[:2]) < 32):
        raise ValueError("가로·세로 32픽셀 이상의 BGR 이미지가 필요합니다.")
    result = frame.copy()
    height, width = frame.shape[:2]
    points = np.array([(int(config["roi"][i] * width), int(config["roi"][i + 1] * height))
                       for i in range(0, 8, 2)], dtype=np.int32)
    cv2.polylines(result, [points], True, (0, 255, 0), 2)
    y = int(config["line_y"] * height)
    left, right = [int(x * width) for x in config["line_x"]]
    cv2.line(result, (left, y), (right, y), (0, 0, 255), 2)
    # 2. 화면 아래쪽 방향의 실제 의미를 함께 표시해 입차/출차 반전을 확인합니다.
    up = "EXIT" if down_direction == "ENTRY" else "ENTRY"
    for index, label in enumerate(("ROI: green / crossing: red", f"DOWN: {down_direction} / UP: {up}")):
        cv2.putText(result, label, (4, 15 + index * 16), cv2.FONT_HERSHEY_SIMPLEX,
                    .4, (255, 255, 255), 1, cv2.LINE_AA)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path)
    source.add_argument("--camera-index", type=int, help="한 프레임을 읽을 물리 카메라 번호 0~32")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--down-direction", choices=["ENTRY", "EXIT"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        # 3. 한글 경로는 바이트 디코딩으로 읽고 기존 출력은 덮어쓰지 않습니다.
        if args.output.suffix.lower() != ".png":
            raise ValueError("출력 확장자는 .png여야 합니다.")
        if args.output.exists() or not args.output.parent.is_dir():
            raise ValueError("기존 부모 폴더에 새 출력 파일을 지정해 주세요.")
        # 3-1. 설정·출력 경로를 먼저 확인해 잘못된 입력으로 카메라를 열지 않습니다.
        config = validate_config(read_json(args.config))
        if args.image is not None:
            data = args.image.read_bytes()
            frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        else:
            frame = read_camera_frame(args.camera_index)
        result = render_preview(frame, config, args.down_direction)
        ok, encoded = cv2.imencode(".png", result)
        if not ok:
            raise ValueError("미리보기 이미지 생성에 실패했습니다.")
        with args.output.open("xb") as stream:
            stream.write(encoded.tobytes())
    except (OSError, ValueError, cv2.error):
        parser.exit(1, "설정 미리보기 실패: 입력 이미지 또는 카메라·설정·새 PNG 출력 경로를 확인해 주세요.\n")
    except KeyboardInterrupt:
        parser.exit(130, "사용자가 설정 미리보기를 중단했습니다.\n")
    print(f"설정 미리보기 저장: {args.output}")


if __name__ == "__main__":
    main()

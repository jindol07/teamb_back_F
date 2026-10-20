# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/preview_gate_config.py

"""정지 이미지에 ROI·통과선을 표시합니다. 카메라·모델·HTTP는 사용하지 않습니다."""

import argparse
from pathlib import Path

import cv2
import numpy as np

from ai_vision.recognition.local_io import read_json
from ai_vision.recognition.tracking_config import validate_config


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
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--down-direction", choices=["ENTRY", "EXIT"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        # 3. 한글 경로는 바이트 디코딩으로 읽고 기존 출력은 덮어쓰지 않습니다.
        if args.output.suffix.lower() != ".png":
            raise ValueError("출력 확장자는 .png여야 합니다.")
        data = args.image.read_bytes()
        frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        result = render_preview(frame, read_json(args.config), args.down_direction)
        ok, encoded = cv2.imencode(".png", result)
        if not ok:
            raise ValueError("미리보기 이미지 생성에 실패했습니다.")
        with args.output.open("xb") as stream:
            stream.write(encoded.tobytes())
    except (OSError, ValueError, cv2.error):
        parser.exit(1, "설정 미리보기 실패: 입력 이미지·설정·새 PNG 출력 경로를 확인해 주세요.\n")
    print(f"설정 미리보기 저장: {args.output}")


if __name__ == "__main__":
    main()

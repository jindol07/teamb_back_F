"""동일 FIRE MP4를 두 영역에 합성해 독립적인 화재 사건의 상태 전이를 시험합니다.

실행: python -m ai_vision.tests.safety.build_dual_fire_sequence_video
기존 감지 모델과 fire_event_state.py는 변경하지 않습니다.
합성 영상은 추적 로직의 시험 입력일 뿐 실제 두 곳에서 난 화재 자료가 아닙니다.
"""

import argparse
import json
import math
import os
from pathlib import Path

import cv2
import numpy as np

from ai_vision.paths import TEST_IMAGE_DIR


# 1. 시나리오: 왼쪽과 오른쪽이 서로 독립적으로 꺼졌다 켜지는지 시험합니다.
# 1-1. 각 구간은 충분한 연속 추론(기본 0.5초)을 확보하도록 8초로 구성합니다.
# 1-2. LEFT/RIGHT/BOTH/NONE은 검증용 화면 구성이며 실제 YOLO 결과는 아닙니다.
DEFAULT_SEGMENTS = (
    ("BOTH", 8),         # 두 곳에 새 SUSPECTED 예상
    ("RIGHT_ONLY", 8),   # 왼쪽 CLEARED, 오른쪽 계속 감지
    ("BOTH", 8),         # 왼쪽 REOPENED, 오른쪽 기존 사건 유지
    ("LEFT_ONLY", 8),    # 오른쪽 CLEARED, 왼쪽 계속 감지
    ("BOTH", 8),         # 오른쪽 REOPENED, 왼쪽 기존 사건 유지
    ("NONE", 8),         # 양쪽 CLEARED
)
SCENES = {"BOTH": (True, True), "LEFT_ONLY": (True, False),
          "RIGHT_ONLY": (False, True), "NONE": (False, False)}


# 2. 입력 MP4 접근 객체 (YOLO나 다른 프로젝트 모듈에 의존하지 않습니다.)
class VideoSource:
    def __init__(self, filename):
        self.filename = Path(filename).resolve()
        if not self.filename.is_file():
            raise FileNotFoundError(f"화재 원본 MP4가 없습니다: {self.filename}")
        self.cap = None
        self.fps = None
        self.frames = None
        self.last_index = -1
        self.last_frame = None
        self._open()

    def _open(self):
        if self.cap is not None:
            self.cap.release()
        self.cap = cv2.VideoCapture(str(self.filename))
        if not self.cap.isOpened():
            raise RuntimeError(f"화재 MP4를 열 수 없습니다: {self.filename}")
        fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or count <= 0:
            self.cap.release()
            self.cap = None
            raise ValueError("원본 MP4의 FPS 또는 프레임 수를 확인할 수 없습니다.")
        self.fps, self.frames = fps, count
        self.last_index = -1
        self.last_frame = None

    def read_at(self, source_seconds):
        # 2-1. 장면이 반복되면 원본도 반복 재생하고 소스 FPS로 위치를 계산합니다.
        if not math.isfinite(source_seconds) or source_seconds < 0:
            raise ValueError("영상 읽기 시간은 0 이상의 유한한 숫자여야 합니다.")
        index = min(int(source_seconds * self.fps) % self.frames, self.frames - 1)
        if index < self.last_index:
            self._open()
        while self.last_index < index:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                raise RuntimeError(f"원본 MP4 {index}번 프레임을 읽지 못했습니다.")
            self.last_index += 1
            self.last_frame = frame
        return self.last_frame

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None


# 3. 같은 프레임에서 두 화재를 시각적으로 구분할 수 있도록 배치합니다.
def panel_boxes(width, height):
    """각 패널은 분리된 좌우 영역이며, 중앙에 넓은 간격을 둡니다."""
    panel_width = int(width * .36)
    panel_height = int(height * .72)
    top = (height - panel_height) // 2
    left_x = int(width * .055)
    right_x = width - left_x - panel_width
    return {"LEFT": [left_x, top, left_x + panel_width, top + panel_height],
            "RIGHT": [right_x, top, right_x + panel_width, top + panel_height]}


def _center_crop_fire(frame, focus_ratio=.70):
    """3-1. 원본 중앙의 불꽃을 크게 보여 주되 영상 비율을 임의로 늘리지 않습니다."""
    if frame is None or len(frame.shape) != 3 or frame.shape[2] != 3:
        raise ValueError("3채널 BGR 프레임이 필요합니다.")
    h, w = frame.shape[:2]
    crop_w = max(1, min(w, int(w * focus_ratio)))
    x = (w - crop_w) // 2
    return frame[:, x:x + crop_w]


def _fit_panel(frame, width, height):
    """3-2. 비율을 유지해 패널 안에 맞추고 남는 여백만 채웁니다."""
    h, w = frame.shape[:2]
    if not w or not h:
        raise ValueError("이미지 폭과 높이가 필요합니다.")
    scale = min(width / w, height / h)
    target_w = max(1, round(w * scale))
    target_h = max(1, round(h * scale))
    resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    panel = np.full((height, width, 3), 26, dtype=np.uint8)
    x, y = (width - target_w) // 2, (height - target_h) // 2
    panel[y:y + target_h, x:x + target_w] = resized
    return panel


def compose_frame(left_frame, right_frame, *, width, height):
    """3-3. 두 패널이 일정 거리 떨어지도록 한 화면으로 합성합니다."""
    canvas = np.full((height, width, 3), 26, dtype=np.uint8)
    for name, frame in (("LEFT", left_frame), ("RIGHT", right_frame)):
        x1, y1, x2, y2 = panel_boxes(width, height)[name]
        if frame is not None:
            canvas[y1:y2, x1:x2] = _fit_panel(_center_crop_fire(frame), x2 - x1, y2 - y1)
        cv2.rectangle(canvas, (x1, y1), (x2 - 1, y2 - 1), (90, 90, 90), 1)
        # 클래스 이름 'FIRE'를 영상에 쓰지 않습니다(탐지 모델에 레이블 힌트 금지).
        cv2.putText(canvas, "CAM A" if name == "LEFT" else "CAM B", (x1, y1 - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, .8, (190, 190, 190), 2, cv2.LINE_AA)
    return canvas


# 4. MP4 및 검증용 시나리오 JSON 생성
def build_dual_fire_sequence(fire_path, output_path, *, fps=15, width=1280,
                             height=720, segments=DEFAULT_SEGMENTS, overwrite=False):
    if type(fps) is not int or not 1 <= fps <= 60:
        raise ValueError("FPS는 1~60의 정수여야 합니다.")
    if any(type(v) is not int or v % 2 or v < lo or v > hi
           for v, lo, hi in ((width, 320, 3840), (height, 180, 2160))):
        raise ValueError("영상 폭/높이는 각각 320~3840, 180~2160 범위의 짝수여야 합니다.")
    if not isinstance(segments, (tuple, list)) or not segments or any(
            not isinstance(seg, (tuple, list)) or len(seg) != 2 or seg[0] not in SCENES or
            type(seg[1]) is not int or not 1 <= seg[1] <= 600 for seg in segments):
        raise ValueError("구간은 (BOTH/LEFT_ONLY/RIGHT_ONLY/NONE, 양의 정수 초) 형태여야 합니다.")

    fire_path = Path(fire_path).resolve()
    output_path = Path(output_path).resolve()
    manifest_path = output_path.with_suffix(".segments.json")
    if output_path == fire_path or manifest_path == fire_path:
        raise ValueError("원본 영상을 출력 경로로 덮어쓸 수 없습니다.")
    if output_path.suffix.lower() != ".mp4":
        raise ValueError("출력 영상은 .mp4 확장자여야 합니다.")
    if not overwrite and (output_path.exists() or manifest_path.exists()):
        raise FileExistsError("영상 또는 구간 JSON이 이미 있습니다. 덮어쓰려면 --overwrite를 지정하세요.")
    # 4-1. 먼저 입력 영상을 열어 재생 불가능한 파일을 조기에 확인합니다.
    left_source = right_source = None
    writer = None
    temp_video = output_path.with_name(output_path.stem + ".partial.mp4")
    temp_preexisted = temp_video.exists()
    total_frames = 0
    stages = []
    try:
        left_source = VideoSource(fire_path)
        right_source = VideoSource(fire_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if temp_preexisted:
            raise FileExistsError(f"이전 임시 영상이 남았습니다: {temp_video}")
        writer = cv2.VideoWriter(str(temp_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError("OpenCV에서 MP4 파일을 열 수 없습니다. mp4v 코덱을 확인하세요.")
        for scene, duration in segments:
            on_left, on_right = SCENES[scene]
            start = total_frames
            for offset in range(duration * fps):
                second = offset / fps
                # 4-2. 같은 원본이라도 오른쪽 영상은 1.3초 다른 시점으로 재생합니다.
                #      두 화면은 실제 두 화재가 아니라 공간적으로 분리한 시험 영상입니다.
                left = left_source.read_at(second) if on_left else None
                right = right_source.read_at(second + 1.3) if on_right else None
                writer.write(compose_frame(left, right, width=width, height=height))
                total_frames += 1
            stages.append({"scene": scene, "start_seconds": start / fps,
                           "end_seconds": total_frames / fps, "left_fire": on_left,
                           "right_fire": on_right})
    except Exception:
        if writer is not None:
            writer.release()
            writer = None
        if not temp_preexisted and temp_video.exists():
            temp_video.unlink()
        raise
    finally:
        if writer is not None:
            writer.release()
        for source in (left_source, right_source):
            if source is not None:
                source.close()

    # 4-3. 영상이 완성된 후에만 최종 경로를 노출합니다.
    manifest = {"purpose": "TWO_SEPARATE_FIRE_REGIONS_TEST_ONLY",
                "source_video": fire_path.name, "output_video": output_path.name,
                "fps": fps, "width": width, "height": height,
                "total_frames": total_frames, "total_seconds": total_frames / fps,
                "regions": panel_boxes(width, height), "segments": stages,
                "note": "같은 원본 화재 영상의 2화면 합성입니다. 실제 독립 화재의 물리적 검증 자료가 아닙니다."}
    # 영상이 유효한지 확인한 후 결과 파일을 교체합니다.
    check = cv2.VideoCapture(str(temp_video))
    try:
        if not check.isOpened() or int(check.get(cv2.CAP_PROP_FRAME_COUNT)) != total_frames:
            raise RuntimeError("작성된 MP4의 프레임 개수가 맞지 않습니다.")
    finally:
        check.release()
    os.replace(temp_video, output_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main(argv=None):
    # 5. 이전에 사용한 화재 원본 영상이 설치되어 있으면 별도 인수 없이 실행 가능합니다.
    root = TEST_IMAGE_DIR / "safety"
    parser = argparse.ArgumentParser(description="양쪽 화재 독립 추적 검증용 MP4 제작")
    parser.add_argument("--fire", type=Path, default=root / "fire_video.mp4")
    parser.add_argument("--output", type=Path, default=root / "dual_fire_sequence.mp4")
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    result = build_dual_fire_sequence(args.fire, args.output, fps=args.fps,
                                      width=args.width, height=args.height, overwrite=args.overwrite)
    print(f"[완료] MP4: {args.output.resolve()}")
    print(f"[구간 JSON] {args.output.resolve().with_suffix('.segments.json')}")
    print(f"[영상] {result['total_seconds']:.1f}초 / {result['total_frames']}프레임")
    for stage in result["segments"]:
        print(f"  {stage['start_seconds']:5.1f}~{stage['end_seconds']:5.1f}초 | {stage['scene']}")


if __name__ == "__main__":
    main()

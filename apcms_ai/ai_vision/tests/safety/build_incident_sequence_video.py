"""기존 FIRE/정상 MP4로 화재 발생·해제·재발생 검증 영상을 만듭니다.

실행: python -m ai_vision.tests.safety.build_incident_sequence_video
기존 모델/실시간 감지 코드를 변경하지 않는 테스트 영상 제작 도구입니다.
"""

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

from ai_vision.paths import TEST_IMAGE_DIR


# 1. 테스트 시나리오
# 1-1. FIRE 6초 → NORMAL 6초 → FIRE 6초는 CLEARED/REOPENED를 확인합니다.
# 1-2. NORMAL 36초 → FIRE 6초는 쿨다운 30초 경과 뒤 새 사건 생성을 확인합니다.
# 1-3. 모든 시간은 생성한 동영상의 재생 시간이며, 실제 감지 결과는 모델에 따라 달라집니다.
DEFAULT_SEGMENTS = (
    ("FIRE", 6),
    ("NORMAL", 6),
    ("FIRE", 6),
    ("NORMAL", 36),
    ("FIRE", 6),
)


# 2. 영상 프레임을 시간 기준으로 읽는 객체
class VideoSource:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(f"입력 영상을 찾을 수 없습니다: {self.path}")
        self.capture = None
        self.fps = 0.0
        self.frame_count = 0
        self.current_index = -1
        self.cached_frame = None
        self._open()

    def _open(self):
        # 2-1. 구간이 반복되는 경우에도 소스의 처음으로 안전하게 돌아갈 수 있도록 합니다.
        if self.capture is not None:
            self.capture.release()
        self.capture = cv2.VideoCapture(str(self.path))
        if not self.capture.isOpened():
            raise RuntimeError(f"영상을 열 수 없습니다: {self.path}")
        self.fps = float(self.capture.get(cv2.CAP_PROP_FPS))
        self.frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(self.fps) or self.fps <= 0 or self.frame_count <= 0:
            self.capture.release()
            raise ValueError(f"입력 영상의 FPS/프레임 수를 읽을 수 없습니다: {self.path}")
        self.current_index = -1
        self.cached_frame = None

    def at(self, elapsed_seconds):
        # 2-2. 출력 15FPS와 입력 FPS가 달라도 실제 시간에 맞는 프레임을 선택합니다.
        target_index = min(int((elapsed_seconds * self.fps) % self.frame_count), self.frame_count - 1)
        if target_index < self.current_index:
            self._open()
        while self.current_index < target_index:
            ok, frame = self.capture.read()
            if not ok or frame is None:
                raise RuntimeError(f"입력 영상의 {target_index}번 프레임을 읽지 못했습니다: {self.path}")
            self.current_index += 1
            self.cached_frame = frame
        if self.cached_frame is None:
            raise RuntimeError(f"입력 영상에 사용 가능한 프레임이 없습니다: {self.path}")
        return self.cached_frame

    def close(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None


def fit_frame(frame, width, height):
    """3. 원본 가로세로 비율을 유지하고 빈 공간만 검은색으로 채웁니다."""
    src_h, src_w = frame.shape[:2]
    if src_w <= 0 or src_h <= 0:
        raise ValueError("입력 프레임 크기가 올바르지 않습니다.")
    scale = min(width / src_w, height / src_h)
    dst_w, dst_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    resized = cv2.resize(frame, (dst_w, dst_h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    left, top = (width - dst_w) // 2, (height - dst_h) // 2
    canvas[top:top + dst_h, left:left + dst_w] = resized
    return canvas


def build_sequence(fire_path, normal_path, output_path, *, fps=15, width=960,
                   height=540, segments=DEFAULT_SEGMENTS, overwrite=False):
    """4. 연속 감지 상태를 검증할 MP4와 구간 설명 JSON을 생성합니다."""
    if isinstance(fps, bool) or not isinstance(fps, int) or fps <= 0 or fps > 120:
        raise ValueError("FPS는 1~120 사이의 정수여야 합니다.")
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 16 or v % 2 for v in (width, height)):
        raise ValueError("영상 크기는 각각 16 이상의 짝수여야 합니다.")
    if not segments or any(kind not in ("FIRE", "NORMAL") or
                           isinstance(seconds, bool) or not isinstance(seconds, int) or seconds <= 0
                           for kind, seconds in segments):
        raise ValueError("영상 구간은 FIRE/NORMAL 종류와 양의 정수 초로 지정해야 합니다.")

    output_path = Path(output_path).resolve()
    fire_path = Path(fire_path).resolve()
    normal_path = Path(normal_path).resolve()
    manifest_path = output_path.with_suffix(".segments.json")
    if output_path in (fire_path, normal_path) or manifest_path in (fire_path, normal_path):
        raise ValueError("출력 경로는 입력 영상 경로와 달라야 합니다.")
    if not overwrite and (output_path.exists() or manifest_path.exists()):
        raise FileExistsError(f"이미 결과 파일이 존재합니다: {output_path} (덮어쓰려면 --overwrite)")

    # 4-1. 소스 영상 두 개를 각각 한 번만 엽니다. 소스 간 FPS 차이는 내부에서 보정합니다.
    sources = {}
    writer = None
    stages = []
    total_frames = 0
    try:
        sources["FIRE"] = VideoSource(fire_path)
        sources["NORMAL"] = VideoSource(normal_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError(f"MP4 저장을 시작할 수 없습니다: {output_path}")
        for kind, seconds in segments:
            # 4-2. 각 구간 시작점에서 소스의 0초부터 다시 재생합니다.
            start_frame = total_frames
            segment_frame_count = seconds * fps
            for frame_number in range(segment_frame_count):
                video_frame = sources[kind].at(frame_number / fps)
                writer.write(fit_frame(video_frame, width, height))
                total_frames += 1
            stages.append({
                "scene": kind,
                "start_seconds": start_frame / fps,
                "end_seconds": total_frames / fps,
                "frames": segment_frame_count,
            })
    finally:
        if writer is not None:
            writer.release()
        for source in sources.values():
            source.close()

    # 4-3. 재생 구간을 별도 JSON으로 남겨 이벤트 시간과 비교할 수 있게 합니다.
    manifest = {
        "purpose": "TEST_ONLY_FIRE_CLEAR_REOPEN_AND_NEW_INCIDENT",
        "output_video": output_path.name,
        "fps": fps,
        "width": width,
        "height": height,
        "total_frames": total_frames,
        "total_seconds": total_frames / fps,
        "segments": stages,
        "note": "예상 구간 정보이며 실제 탐지 성능이나 화재 진위를 보증하지 않습니다.",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main(argv=None):
    # 5. 프로젝트에서 바로 실행할 수 있도록 기존 테스트 영상 경로를 기본값으로 사용합니다.
    root = TEST_IMAGE_DIR / "safety"
    parser = argparse.ArgumentParser(description="FIRE→NORMAL→FIRE→NORMAL→FIRE 테스트 MP4 제작")
    parser.add_argument("--fire", type=Path, default=root / "fire_video.mp4")
    parser.add_argument("--normal", type=Path, default=root / "normal_parking_video.mp4")
    parser.add_argument("--output", type=Path, default=root / "fire_incident_sequence.mp4")
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    result = build_sequence(args.fire, args.normal, args.output, fps=args.fps,
                            width=args.width, height=args.height, overwrite=args.overwrite)
    print(f"[완료] {args.output.resolve()}")
    print(f"[구간] {result['total_seconds']:.0f}초 / {result['total_frames']}프레임")
    for stage in result["segments"]:
        print(f"  {stage['start_seconds']:5.1f}~{stage['end_seconds']:5.1f}초  {stage['scene']}")
    print(f"[구간 JSON] {args.output.resolve().with_suffix('.segments.json')}")


if __name__ == "__main__":
    main()

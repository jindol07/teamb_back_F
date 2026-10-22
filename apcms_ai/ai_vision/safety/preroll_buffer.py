"""화재 의심 이벤트 *직전*의 추론 샘플만 저장하는 크기 제한 JPEG 순환 버퍼.

- 평상시에는 메모리에서만 보관하며 이벤트 발생 시에만 파일로 저장합니다.
- 각 샘플은 전체 카메라 프레임이 아니라 추론 시각의 프레임입니다.
- 이 기능은 사건 판단에 참여하지 않으며, 증거 확보를 위한 보조 수단입니다.
"""

import json
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import cv2


@dataclass(frozen=True)
class EncodedSample:
    source_seconds: float
    frame_index: int
    jpg: bytes
    width: int
    height: int


class PreEventFrameBuffer:
    """초 단위 시간 창, 프레임 수, 바이트 수를 동시에 제한합니다."""

    def __init__(self, seconds=5.0, max_frames=30, max_bytes=16 * 1024 * 1024,
                 max_width=960, jpeg_quality=75):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("저장할 과거 시간은 양의 유한한 값이어야 합니다.")
        if type(max_frames) is not int or not 1 <= max_frames <= 120:
            raise ValueError("버퍼 최대 프레임은 1~120이어야 합니다.")
        if type(max_bytes) is not int or max_bytes < 1024:
            raise ValueError("버퍼 최대 크기는 1024바이트 이상이어야 합니다.")
        if type(max_width) is not int or not 32 <= max_width <= 3840:
            raise ValueError("저장할 이미지 최대 너비는 32~3840이어야 합니다.")
        if type(jpeg_quality) is not int or not 1 <= jpeg_quality <= 95:
            raise ValueError("JPEG 품질은 1~95여야 합니다.")
        self.seconds = float(seconds)
        self.max_frames = max_frames
        self.max_bytes = max_bytes
        self.max_width = max_width
        self.jpeg_quality = jpeg_quality
        self._frames = deque()
        self._bytes = 0
        self._latest = None
        self.total_seen = 0
        self.skipped_oversize = 0

    @property
    def frames(self):
        return len(self._frames)

    @property
    def bytes_used(self):
        return self._bytes

    def _discard_oldest(self):
        old = self._frames.popleft()
        self._bytes -= len(old.jpg)

    def add(self, frame, source_seconds, frame_index):
        """추론에 사용한 프레임만 JPEG로 메모리에 저장합니다."""
        if type(source_seconds) not in (int, float) or not math.isfinite(source_seconds) or source_seconds < 0:
            raise ValueError("잘못된 소스 시간입니다.")
        if self._latest is not None and source_seconds < self._latest:
            raise ValueError("소스 시간은 역행할 수 없습니다.")
        if type(frame_index) is not int or frame_index < 1:
            raise ValueError("프레임 번호는 양의 정수여야 합니다.")
        if frame is None or getattr(frame, "size", 0) == 0 or len(frame.shape) < 2:
            raise ValueError("빈 프레임은 보관할 수 없습니다.")
        self._latest = float(source_seconds)
        self.total_seen += 1

        height, width = frame.shape[:2]
        if width > self.max_width:
            scaled_height = max(1, round(height * self.max_width / width))
            frame = cv2.resize(frame, (self.max_width, scaled_height), interpolation=cv2.INTER_AREA)
        encoded_ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        if not encoded_ok:
            raise OSError("이벤트 이전 프레임의 JPEG 인코딩에 실패했습니다.")
        content = encoded.tobytes()
        if len(content) > self.max_bytes:
            self.skipped_oversize += 1
        else:
            self._frames.append(EncodedSample(self._latest, frame_index, content, frame.shape[1], frame.shape[0]))
            self._bytes += len(content)

        # 두 설정이 동시에 적용됩니다. 시각 창이 작아도 오래된 프레임은 제거합니다.
        while self._frames and (
            self._latest - self._frames[0].source_seconds > self.seconds or
            len(self._frames) > self.max_frames or self._bytes > self.max_bytes
        ):
            self._discard_oldest()

    def save_before(self, output_dir, folder_name, event_seconds):
        """사건 시각보다 과거의 샘플만 저장하고 상대 폴더 이름을 반환합니다."""
        if type(event_seconds) not in (int, float) or not math.isfinite(event_seconds) or event_seconds < 0:
            raise ValueError("사건 시각이 잘못되었습니다.")
        if not isinstance(folder_name, str) or not folder_name or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in folder_name):
            raise ValueError("저장 폴더명은 영문 소문자·숫자·_-만 허용합니다.")
        destination = Path(output_dir) / folder_name
        # 이벤트가 없는 평상시에는 이 경로에 파일이 생기지 않습니다.
        destination.mkdir(parents=True, exist_ok=False)
        metadata = []
        for sample in self._frames:
            if sample.source_seconds >= event_seconds or event_seconds - sample.source_seconds > self.seconds:
                continue
            filename = f"frame_{len(metadata) + 1:03d}.jpg"
            (destination / filename).write_bytes(sample.jpg)
            metadata.append({"file": filename, "frame_index": sample.frame_index,
                             "source_seconds": round(sample.source_seconds, 3),
                             "seconds_before_event": round(event_seconds - sample.source_seconds, 3),
                             "width": sample.width, "height": sample.height})
        (destination / "manifest.json").write_text(
            json.dumps({"record_type": "FIRE_SMOKE_PREROLL", "event_seconds": round(event_seconds, 3),
                        "requested_seconds": self.seconds, "saved_samples": len(metadata),
                        "frames": metadata}, ensure_ascii=False, indent=2), encoding="utf-8")
        return folder_name, len(metadata)

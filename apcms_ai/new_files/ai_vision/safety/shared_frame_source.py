"""주차 A/B가 발행한 APCMSF1 최신 프레임을 화재 감지기에 공급합니다.

주차 프로세스와 카메라 장치를 건드리지 않습니다. 파일은 주차 측 read_latest를
통해 읽으며, 성공한 새 sequence만 전달하고 입력 중단 시 종료 상태를 반환합니다.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Callable


class SharedFrameCapture:
    """OpenCV 캡처와 호환되는 최소 read/isOpened/release 어댑터입니다.

    * 소스 카메라는 오직 주차 런타임이 소유합니다.
    * 중복, CLOSED, 만료 프레임은 재추론하지 않습니다.
    * 주차 실행 폴더(run_id) 교체 시 자동으로 과거 폴더를 추측하지 않습니다.
    """

    def __init__(self, run_dir: Path, role: str, camera_id: str, *,
                 max_age: float = 3.0, max_silence: float = 12.0, poll: float = 0.1,
                 reader: Callable | None = None, clock: Callable = time.monotonic,
                 sleeper: Callable = time.sleep):
        if role not in ("gate", "parking"):
            raise ValueError("공유 프레임 role은 gate 또는 parking이어야 합니다.")
        if not isinstance(camera_id, str) or not camera_id.strip() or len(camera_id) > 128:
            raise ValueError("논리 camera_id가 필요합니다.")
        for label, value in (("max_age", max_age), ("max_silence", max_silence), ("poll", poll)):
            if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{label}은 양의 유한한 초여야 합니다.")
        if max_silence <= max_age:
            raise ValueError("max_silence는 max_age보다 길어야 합니다.")
        self.run_dir = Path(run_dir)
        if not self.run_dir.is_dir() or not self.run_dir.name:
            raise ValueError("주차 런타임의 현재 실행 폴더를 지정하세요.")
        self.path = self.run_dir / f"{role}.frame"
        self.role = role
        self.camera_id = camera_id
        self.max_age = float(max_age)
        self.max_silence = float(max_silence)
        self.poll = float(poll)
        self._clock = clock
        self._sleep = sleeper
        if reader is None:
            # frame_exchange는 코덱스 주차 담당이 제공하는 모듈입니다.
            # 주차 장치/VideoCapture는 여는 코드가 없습니다.
            from ai_vision.parking.frame_exchange import read_latest
            reader = read_latest
        self._reader = reader
        self._last_token: tuple | None = None
        self._stopped = False
        self._last_reason: str | None = None
        self._seen = False

    @property
    def last_reason(self) -> str | None:
        return self._last_reason

    def isOpened(self) -> bool:  # OpenCV 캡처 계약 최소 호환
        return not self._stopped and self.run_dir.is_dir()

    def read(self):
        """새 유효 프레임 1개를 반환합니다. 입력 중단은 (False, None)으로 전달."""
        if self._stopped:
            return False, None
        deadline = self._clock() + self.max_silence
        while not self._stopped:
            try:
                sample = self._reader(self.path, max_age=self.max_age)
            except (ValueError, OSError) as exc:
                self._last_reason = type(exc).__name__
                sample = None
            if sample is not None:
                metadata, frame = sample
                if not isinstance(metadata, dict):
                    self._last_reason = "INVALID_METADATA"
                elif metadata.get("role") != self.role or metadata.get("run_id") != self.run_dir.name or metadata.get("camera_id") != self.camera_id:
                    # 다른 카메라/과거 실행 프레임을 오인해 알림 전송하지 않습니다.
                    self._last_reason = "IDENTITY_MISMATCH"
                elif metadata.get("status") != "FRAME" or type(metadata.get("sequence")) is not int or metadata["sequence"] < 0:
                    self._last_reason = "INVALID_SEQUENCE"
                elif frame is None or getattr(frame, "size", 0) == 0:
                    self._last_reason = "INVALID_FRAME"
                else:
                    token = (metadata["run_id"], metadata["role"], metadata["sequence"])
                    if token != self._last_token:
                        self._last_token = token
                        self._last_reason = None
                        self._seen = True
                        return True, frame
            if self._clock() >= deadline:
                if self._last_reason is None:
                    self._last_reason = "INPUT_STALE" if self._seen else "NO_FIRST_FRAME"
                return False, None
            self._sleep(min(self.poll, max(0, deadline - self._clock())))
        return False, None

    def release(self) -> None:
        self._stopped = True

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_clock.py

"""카메라 read 직후의 단조 시계를 타임존 포함 세션 시각에 연결합니다."""

import math
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class FrameStamp:
    frame_index: int
    elapsed_seconds: float
    captured_at: datetime


class LiveGateClock:
    def __init__(self, started_at=None, monotonic_start=None, history_limit=512):
        self.started_at = datetime.now(timezone.utc) if started_at is None else started_at
        if not isinstance(self.started_at, datetime) or self.started_at.utcoffset() is None:
            raise ValueError("세션 시작 시각에는 타임존이 필요합니다.")
        self._start = time.monotonic() if monotonic_start is None else self._number(monotonic_start)
        if type(history_limit) is not int or not 1 <= history_limit <= 4096:
            raise ValueError("프레임 시각 보관 한도는 1~4096이어야 합니다.")
        self._limit, self._history = history_limit, OrderedDict()
        self._last_index, self._last_time, self.frame_count = -1, None, 0

    @staticmethod
    def _number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < 1e12 or not math.isfinite(value):
            raise ValueError("단조 시각이 유효하지 않습니다.")
        return value

    def capture(self, frame_index, monotonic_seconds=None):
        value = self._number(time.monotonic() if monotonic_seconds is None else monotonic_seconds)
        if (type(frame_index) is not int or frame_index <= self._last_index or value < self._start or
                (self._last_time is not None and value <= self._last_time)):
            raise ValueError("프레임 번호·수집 시각이 중복되거나 역행했습니다.")
        elapsed = value - self._start
        try:
            stamp = FrameStamp(frame_index, elapsed, self.started_at + timedelta(seconds=elapsed))
        except OverflowError as error:
            raise ValueError("수집 시각의 표현 범위를 초과했습니다.") from error
        self._history[frame_index] = stamp
        if len(self._history) > self._limit:
            self._history.popitem(last=False)
        self._last_index, self._last_time = frame_index, value
        self.frame_count += 1
        return stamp

    @property
    def oldest_frame_index(self):
        # 현재 시각을 확인할 수 있는 경계를 제공하고 내부 사전은 노출하지 않습니다.
        return next(iter(self._history), None)

    def lookup(self, frame_index):
        if type(frame_index) is not int or frame_index < 0:
            raise ValueError("프레임 번호가 유효하지 않습니다.")
        try:
            return self._history[frame_index]
        except KeyError as error:
            raise ValueError("이 세션에서 보관한 프레임 시각이 아닙니다.") from error

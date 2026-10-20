# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_clock.py

"""카메라 read 직후의 단조 시계를 타임존 포함 세션 시각에 연결합니다."""

# 1. 시각 계산과 자료 보관에 필요한 모듈
# 1-1. math는 숫자 값이 무한대·NaN인지 검사합니다.
import math
# 1-2. time.monotonic은 시스템 시계 조정의 영향을 받지 않는 경과 시간 기준입니다.
import time
# 1-3. OrderedDict는 오래된 프레임 기록부터 제거할 수 있는 순서 보장 사전입니다.
from collections import OrderedDict
# 1-4. dataclass는 프레임별 시각 자료의 데이터 클래스를 간결하게 선언합니다.
from dataclasses import dataclass
# 1-5. datetime·timedelta·timezone은 UTC 시작 시각에 경과 초를 합산합니다.
from datetime import datetime, timedelta, timezone


# 2. 프레임 한 장의 불변 시각 기록
# 2-1. frozen=True로 생성 후 필드가 바뀌지 않게 합니다.
@dataclass(frozen=True)
class FrameStamp:
    frame_index: int
    elapsed_seconds: float
    captured_at: datetime


# 3. 한 카메라 세션에서 프레임 시간과 순서를 관리하는 시계
class LiveGateClock:
    # 3-1. UTC 시작 시각, 단조 시계 기준점, 기록 최대 수를 초기화합니다.
    # 함수 설명: __init__() — 실제 UTC 시작시각과 역행하지 않는 단조시각의 기준점을 등록합니다.
    def __init__(self, started_at=None, monotonic_start=None, history_limit=512):
        # 3-2. 시작 시각이 주어지지 않으면 현재 UTC 시각을 사용합니다.
        self.started_at = datetime.now(timezone.utc) if started_at is None else started_at
        if not isinstance(self.started_at, datetime) or self.started_at.utcoffset() is None:
            raise ValueError("세션 시작 시각에는 타임존이 필요합니다.")
        # 3-3. 경과 시간 계산을 위한 기준점은 monotonic 값입니다.
        self._start = time.monotonic() if monotonic_start is None else self._number(monotonic_start)
        if type(history_limit) is not int or not 1 <= history_limit <= 4096:
            raise ValueError("프레임 시각 보관 한도는 1~4096이어야 합니다.")
        # 3-4. 프레임 기록은 유한한 OrderedDict에 보관합니다.
        self._limit, self._history = history_limit, OrderedDict()
        self._last_index, self._last_time, self.frame_count = -1, None, 0

    # 4. 단조 시계의 입력 숫자 검증
    @staticmethod
    # 함수 설명: _number() — NaN, 무한대, bool 및 범위 밖의 시각 입력을 거절합니다.
    def _number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < 1e12 or not math.isfinite(value):
            raise ValueError("단조 시각이 유효하지 않습니다.")
        return value

    # 5. 새 프레임에 번호·경과 시간·UTC 감지 시각을 부여합니다.
    # 5-1. 중복/역행 프레임이나 시각은 오류 처리합니다.
    # 함수 설명: capture() — 프레임 번호와 읽은 시각을 기록하며 중복/역행 값은 거절합니다.
    def capture(self, frame_index, monotonic_seconds=None):
        value = self._number(time.monotonic() if monotonic_seconds is None else monotonic_seconds)
        if (type(frame_index) is not int or frame_index <= self._last_index or value < self._start or
                (self._last_time is not None and value <= self._last_time)):
            raise ValueError("프레임 번호·수집 시각이 중복되거나 역행했습니다.")
        # 5-2. 시각 차이를 UTC 시작 시각에 더해 captured_at을 만듭니다.
        elapsed = value - self._start
        try:
            stamp = FrameStamp(frame_index, elapsed, self.started_at + timedelta(seconds=elapsed))
        except OverflowError as error:
            raise ValueError("수집 시각의 표현 범위를 초과했습니다.") from error
        # 5-3. 최근 기록만 남기고 한도 초과 시 가장 오래된 프레임을 삭제합니다.
        self._history[frame_index] = stamp
        if len(self._history) > self._limit:
            self._history.popitem(last=False)
        self._last_index, self._last_time = frame_index, value
        self.frame_count += 1
        return stamp

    # 6. 현재 보관 중인 가장 오래된 프레임 번호 조회
    @property
    # 함수 설명: oldest_frame_index() — 지금 조회 가능한 가장 오래된 프레임 번호를 노출합니다.
    def oldest_frame_index(self):
        # 현재 시각을 확인할 수 있는 경계를 제공하고 내부 사전은 노출하지 않습니다.
        return next(iter(self._history), None)

    # 7. 같은 세션에서 보관 중인 특정 프레임의 시각 조회
    # 7-1. 삭제된 과거 프레임·잘못된 번호는 사용할 수 없습니다.
    # 함수 설명: lookup() — 과거 프레임의 시간표를 찾아 동일 세션의 기록인지 확인합니다.
    def lookup(self, frame_index):
        if type(frame_index) is not int or frame_index < 0:
            raise ValueError("프레임 번호가 유효하지 않습니다.")
        try:
            return self._history[frame_index]
        except KeyError as error:
            raise ValueError("이 세션에서 보관한 프레임 시각이 아닙니다.") from error

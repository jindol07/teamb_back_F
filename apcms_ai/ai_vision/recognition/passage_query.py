# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/passage_query.py

"""API와 CSV에서 함께 사용하는 차량 통과 검색 조건."""

import math
from dataclasses import dataclass

PLATE_STATUSES = frozenset({"CONFIRMED", "CONFLICT", "INSUFFICIENT_EVIDENCE", "NO_VALID_KOREAN_PLATE"})


@dataclass(frozen=True)
class PassageQuery:
    direction: str | None = None
    plate_status: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None

    def __post_init__(self):
        # 1. 시각은 촬영 날짜가 아니라 원본 영상 시작부터의 초입니다.
        if self.direction is not None and self.direction not in {"UP", "DOWN"}:
            raise ValueError("방향은 UP 또는 DOWN이어야 합니다.")
        if self.plate_status is not None and self.plate_status not in PLATE_STATUSES:
            raise ValueError("번호판 판정 조건을 확인해 주세요.")
        for value in (self.start_seconds, self.end_seconds):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or
                                      not math.isfinite(value) or value < 0):
                raise ValueError("영상 시각은 유한한 0 이상의 숫자여야 합니다.")
        if self.start_seconds is not None and self.end_seconds is not None and self.start_seconds > self.end_seconds:
            raise ValueError("시작 시각은 종료 시각 이하여야 합니다.")

    def matches(self, row):
        # 2. 시작·종료 경계를 포함하고, 모든 조건을 동시에 만족해야 채택합니다.
        return ((self.direction is None or row["screen_direction"] == self.direction) and
                (self.plate_status is None or row["plate_status"] == self.plate_status) and
                (self.start_seconds is None or row["video_seconds"] >= self.start_seconds) and
                (self.end_seconds is None or row["video_seconds"] <= self.end_seconds))

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_deadline.py

"""새 카메라 읽기를 시작하기 전에 실행 시간 한도를 검사합니다."""

import math
import time


def _number(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
            not math.isfinite(value) or not 0 <= value < 1e12):
        raise ValueError("시간 제한 시계 값이 올바르지 않습니다.")
    return value


class LiveGateDeadline:
    def __init__(self, seconds, reader=None):
        if not 0 < _number(seconds) <= 300:
            raise ValueError("실행 제한은 0초 초과 300초 이하여야 합니다.")
        self.seconds = seconds
        self.reader = time.monotonic if reader is None else reader
        self.start = _number(self.reader())
        self.last, self.checks, self.expired = self.start, 0, False

    def before_read(self):
        # 1. 수집 시각·성능 측정과 별도로 확인하므로 기존 프레임 시각을 바꾸지 않습니다.
        current = _number(self.reader())
        if current < self.last:
            raise ValueError("시간 제한 시계가 역행했습니다.")
        self.last = current
        self.checks += 1
        self.expired = current - self.start >= self.seconds
        return self.expired

    def summary(self):
        # 2. 마지막 확인 시각이며 종료·저장까지 포함한 전체 실행 시간은 아닙니다.
        return {"scope": "READ_BOUNDARY_CHECKS_ONLY", "seconds": self.seconds, "checks": self.checks,
                "last_checked_elapsed_seconds": self.last - self.start, "expired_before_read": self.expired}


def validate_deadline(value):
    keys = {"scope", "seconds", "checks", "last_checked_elapsed_seconds", "expired_before_read"}
    if not isinstance(value, dict) or set(value) != keys or value["scope"] != "READ_BOUNDARY_CHECKS_ONLY":
        raise ValueError("읽기 전 시간 제한 검사 형식이 올바르지 않습니다.")
    seconds, elapsed = _number(value["seconds"]), _number(value["last_checked_elapsed_seconds"])
    if (not 0 < seconds <= 300 or type(value["checks"]) is not int or not 0 <= value["checks"] <= 100000 or
            type(value["expired_before_read"]) is not bool or
            value["expired_before_read"] != (elapsed >= seconds) or (value["checks"] == 0 and elapsed != 0)):
        raise ValueError("읽기 전 시간 제한 검사 수치가 일치하지 않습니다.")
    return dict(value)

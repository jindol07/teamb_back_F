# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_metrics.py

"""실행 단계의 벽시계 소요 시간과 프레임 수집 간격을 누적합니다."""

import math
import time
from contextlib import contextmanager


class LiveGateMetrics:
    def __init__(self, reader=None):
        self.reader = time.perf_counter if reader is None else reader
        self.stages = {name: {"calls": 0, "errors": 0, "total_seconds": 0.0, "max_seconds": 0.0}
                       for name in ("read", "process")}
        self.frames, self.previous, self.max_gap, self.long_gaps = 0, None, 0.0, 0

    @contextmanager
    def measure(self, name):
        # 1. 실패·사용자 중단이 있어도 해당 호출의 시간과 오류 횟수를 남깁니다.
        stage = self.stages[name]
        started = self.reader()
        stage["calls"] += 1
        try:
            yield
        except BaseException:
            stage["errors"] += 1
            raise
        finally:
            duration = self.reader() - started
            if not math.isfinite(duration) or duration < 0:
                raise ValueError("처리 시간 측정 시계가 역행했습니다.")
            stage["total_seconds"] += duration
            stage["max_seconds"] = max(stage["max_seconds"], duration)

    def record_frame(self, elapsed):
        if (isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or
                not math.isfinite(elapsed) or elapsed < 0 or
                (self.previous is not None and elapsed <= self.previous)):
            raise ValueError("수집 프레임 시각은 순서대로 증가해야 합니다.")
        # 2. 1초 초과 간격은 기존 추적 연결 제한과 비교할 진단 수치입니다.
        if self.previous is not None:
            gap = elapsed - self.previous
            self.max_gap = max(self.max_gap, gap)
            self.long_gaps += gap > 1
        self.previous = elapsed
        self.frames += 1

    def summary(self):
        return {"scope": "LOCAL_WALL_TIME_ONLY", "captured_frames": self.frames,
                "max_frame_gap_seconds": self.max_gap, "frame_gaps_over_one_second": self.long_gaps,
                "stages": {name: dict(values) for name, values in self.stages.items()}}


def validate_metrics(value, captured_frames):
    # 3. 예전 결과에는 측정값이 없을 수 있지만, 있으면 손상 여부를 검사합니다.
    if not isinstance(value, dict) or value.get("scope") != "LOCAL_WALL_TIME_ONLY":
        raise ValueError("처리 시간 진단 형식이 올바르지 않습니다.")
    if type(value.get("captured_frames")) is not int or value["captured_frames"] != captured_frames:
        raise ValueError("처리 시간 진단의 프레임 수가 요약과 다릅니다.")
    def nonnegative(number):
        return (not isinstance(number, bool) and isinstance(number, (int, float)) and
                math.isfinite(number) and number >= 0)
    gap, long_gaps = value.get("max_frame_gap_seconds"), value.get("frame_gaps_over_one_second")
    if (not nonnegative(gap) or type(long_gaps) is not int or
            not 0 <= long_gaps <= max(0, captured_frames - 1) or
            (captured_frames < 2 and gap != 0) or (long_gaps > 0 and gap <= 1) or
            (long_gaps == 0 and gap > 1)):
        raise ValueError("프레임 간격 진단이 올바르지 않습니다.")
    stages = value.get("stages")
    if not isinstance(stages, dict) or set(stages) != {"read", "process"}:
        raise ValueError("읽기·처리 시간 진단이 필요합니다.")
    for stage in stages.values():
        if not isinstance(stage, dict) or set(stage) != {"calls", "errors", "total_seconds", "max_seconds"}:
            raise ValueError("단계별 진단 항목이 올바르지 않습니다.")
        if (type(stage["calls"]) is not int or type(stage["errors"]) is not int or
                not 0 <= stage["errors"] <= stage["calls"] <= 100000 or
                not nonnegative(stage["total_seconds"]) or not nonnegative(stage["max_seconds"]) or
                stage["max_seconds"] > stage["total_seconds"] + 1e-9 or
                (stage["calls"] == 0 and stage["total_seconds"] != 0)):
            raise ValueError("단계별 시간·호출 횟수가 올바르지 않습니다.")
    if stages["read"]["calls"] < captured_frames or stages["process"]["calls"] > captured_frames:
        raise ValueError("단계별 호출 수가 수집 프레임 수와 다릅니다.")
    return {"scope": value["scope"], "captured_frames": captured_frames,
            "max_frame_gap_seconds": gap, "frame_gaps_over_one_second": long_gaps,
            "stages": {name: dict(stage) for name, stage in stages.items()}}


def validate_processor_statistics(value, captured_frames):
    keys = {"frames", "observations", "already_counted", "outside_roi", "eligible",
            "gap_resets", "crossings", "ocr_calls", "peak_buffer_bytes"}
    optional = {"roi_resets", "speed_resets", "expired_history_crops"}
    if (not isinstance(value, dict) or not keys <= set(value) or not set(value) <= keys | optional or
            any(type(number) is not int or not 0 <= number <= 2**63 - 1 for number in value.values())):
        raise ValueError("차량 관찰 통계의 항목·건수가 올바르지 않습니다.")
    if (value["frames"] > captured_frames or
            value["observations"] != value["already_counted"] + value["outside_roi"] + value["eligible"] or
            value["crossings"] > value["eligible"] or value["ocr_calls"] > value["crossings"] * 3):
        raise ValueError("차량 관찰 통계가 일치하지 않습니다.")
    return dict(value)

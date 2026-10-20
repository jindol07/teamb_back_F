# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/line_crossing.py
"""AI 모델 없이 차량 중심점의 수평 기준선 통과를 안정적으로 판별합니다."""

# 1. 차량별 상태 및 기하 계산에 필요한 도구
# 1-1. dataclass는 추적 ID 하나의 상태를 저장할 클래스를 간결하게 만듭니다.
from dataclasses import dataclass
# 1-2. hypot은 이동 거리, isfinite는 무한대·NaN 여부를 검사합니다.
from math import hypot, isfinite

# 2. 추적 ID별 위치 확정 상태 저장
@dataclass
class TrackState:
    # 2-1. 마지막 관찰 영상 시각입니다. 초 단위를 사용합니다.
    last_time: float
    # 2-2. 기준선 위 -1, 아래 1, 아직 확정되지 않은 경우 0입니다.
    side: int = 0
    # 2-3. 마지막 확정 위치와 새 위치 확정 후보를 따로 보관합니다.
    point: tuple = None
    candidate: int = 0
    candidate_count: int = 0
    # 2-4. 확정 여부와 무관하게 마지막으로 관찰한 좌표입니다.
    observed_point: tuple = None

# 3. 동일 차량을 중복 집계하지 않는 기준선 판정기
class LineCrossingCounter:
    # 3-1. 기준선 길이, 여유 픽셀, 필요한 안정 프레임 수, 관찰 공백·속도 한도를 받습니다.
    # 함수 설명: __init__() — 좌표 경계와 흔들림·프레임 안정화·추적 공백 제한을 설정합니다.
    def __init__(self, line_y, x_min, x_max, margin=12,
                 stable_frames=3, max_gap_seconds=1.0, max_speed=900):
        numbers = (line_y, x_min, x_max, margin, max_gap_seconds, max_speed)
        # 3-2. 숫자 입력의 유효성과 선분 방향, 안정화 설정을 확인합니다.
        if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in numbers) or
                type(stable_frames) is not int or x_min >= x_max or margin < 0 or stable_frames < 1 or
                max_gap_seconds <= 0 or max_speed <= 0):
            raise ValueError("기준선 범위와 안정화 설정을 확인해 주세요.")
        self.line_y = line_y
        self.x_min, self.x_max = x_min, x_max
        self.margin = margin
        self.stable_frames = stable_frames
        self.max_gap_seconds = max_gap_seconds
        self.max_speed = max_speed
        self.states = {}
        # 3-3. 위치 기록이 만료되더라도 통과한 ID 기록은 유지합니다.
        self.counted_ids = set()

    # 4. 오래된 차량 위치 상태 정리
    # 함수 설명: expire() — 오래 관찰되지 않은 차량 위치 상태만 제거합니다.
    def expire(self, timestamp):
        # 4-1. 음수·무한대·NaN 시각을 거부합니다.
        if (isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or
                not isfinite(timestamp) or timestamp < 0):
            raise ValueError("영상 시각은 유효한 0 이상의 숫자여야 합니다.")
        # 4-2. 너무 오래 보이지 않은 ID의 과거 위치와 현재 위치를 이어 붙이지 않습니다.
        self.states = {key: value for key, value in self.states.items()
                       if timestamp - value.last_time <= self.max_gap_seconds}

    # 5. 차량 한 대의 위치 이력만 제거
    # 함수 설명: reset_track() — 특정 차량의 위치 추적을 초기화하되 이미 집계한 사실은 유지합니다.
    def reset_track(self, track_id):
        # 5-1. counted_ids는 유지하므로 같은 ID의 재집계를 허용하지 않습니다.
        if type(track_id) is not int or track_id < 0:
            raise ValueError("추적 ID를 확인해 주세요.")
        return self.states.pop(track_id, None) is not None

    # 6. 관찰 시각·위치의 연속성 검사
    # 함수 설명: continuity_break_reason() — 위치·시간 불연속 또는 비현실적 속도 변화를 검사합니다.
    def continuity_break_reason(self, track_id, point, timestamp):
        # 6-1. 추적 ID, 중심점 (x, y), 영상 시각의 입력 형식을 검증합니다.
        if (type(track_id) is not int or track_id < 0 or not isinstance(point, (list, tuple)) or
                len(point) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in point)):
            raise ValueError("추적 ID와 중심점 좌표를 확인해 주세요.")
        if (isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or
                not isfinite(timestamp) or timestamp < 0):
            raise ValueError("영상 시각은 유효한 0 이상의 숫자여야 합니다.")
        state = self.states.get(track_id)
        if state is None:
            return None
        elapsed = timestamp - state.last_time
        if elapsed < 0:
            raise ValueError("같은 차량의 영상 시각이 역행했습니다.")
        # 6-2. 마지막 관찰 뒤 허용 공백을 넘으면 GAP을 반환합니다.
        if elapsed > self.max_gap_seconds:
            return "GAP"
        if state.observed_point is not None and elapsed > 0:
            distance = hypot(point[0] - state.observed_point[0], point[1] - state.observed_point[1])
            # 6-3. 이동 거리 > 최대 속도 × 경과 시간이라면 ID 연결 오류 가능성이 있습니다.
            if distance > self.max_speed * elapsed:
                return "SPEED"
        return None

    # 7. 프레임별 중심점으로 통과 여부 갱신
    # 함수 설명: update() — 중심점의 이동이 지정 선분을 실제 통과했는지 안정화 후 판정합니다.
    def update(self, track_id, point, timestamp):
        # 7-1. 비정상적인 위치 연결은 상태를 초기화하고 새 관찰로 시작합니다.
        reason = self.continuity_break_reason(track_id, point, timestamp)
        self.expire(timestamp)
        if reason is not None:
            self.reset_track(track_id)
        state = self.states.setdefault(track_id, TrackState(timestamp))
        if state.observed_point is not None:
            elapsed = timestamp - state.last_time
            if elapsed < 0:
                raise ValueError("같은 차량의 영상 시각이 역행했습니다.")
            if elapsed == 0:
                # 7-2. 같은 시각의 중복 관찰은 안정화 프레임 수에 합산하지 않습니다.
                return None
        state.last_time = timestamp
        state.observed_point = point
        x, y = point
        # 7-3. OpenCV 영상 좌표는 아래로 내려갈수록 y가 커집니다.
        # 예: y=100, margin=12이면 88~112는 판정 보류 영역입니다.
        side = -1 if y < self.line_y - self.margin else (
            1 if y > self.line_y + self.margin else 0)
        if side == 0:
            state.candidate, state.candidate_count = 0, 0
            return None

        # 8. 여러 연속 프레임으로 한쪽 위치를 확정
        if side == state.side:
            # 8-1. 확정된 같은 쪽에 있으면 최종 위치만 갱신합니다.
            state.point = point
            state.candidate, state.candidate_count = 0, 0
            return None
        if side != state.candidate:
            state.candidate, state.candidate_count = side, 0
        state.candidate_count += 1
        if state.candidate_count < self.stable_frames:
            # 8-2. 일시적인 탐지 흔들림만으로 선을 통과했다고 보지 않습니다.
            return None
        old_side, old_point = state.side, state.point
        state.side, state.point = side, point
        state.candidate, state.candidate_count = 0, 0
        if old_side == 0 or track_id in self.counted_ids:
            # 8-3. 최초 위치 확정은 통과가 아니며, 이미 센 차량은 재집계하지 않습니다.
            return None

        # 9. 지정된 길이의 기준선 구간을 통과했는지 판정
        old_x, old_y = old_point
        # 9-1. 두 확정 중심점을 직선으로 연결한 뒤 선 높이에서 x를 보간합니다.
        crossing_x = old_x + (x - old_x) * (self.line_y - old_y) / (y - old_y)
        if not self.x_min <= crossing_x <= self.x_max:
            return None
        self.counted_ids.add(track_id)
        # 9-2. DOWN/UP은 화면 이동 방향이며 실제 입차/출차는 아닙니다.
        return {
            "track_id": track_id,
            "direction": "DOWN" if side == 1 else "UP",
            # 9-3. 통과 시각은 선 교차 추정 시각이 아니라 반대편 위치의 확정 시각입니다.
            "video_seconds": round(timestamp, 3),
            "from_point": list(old_point),
            "to_point": list(point),
            "crossing_point": [round(crossing_x, 2), self.line_y],
        }

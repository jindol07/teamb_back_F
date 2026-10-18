# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/line_crossing.py

# AI 모델 없이 시험할 수 있는 수평 기준선 통과 판별

from dataclasses import dataclass
from math import hypot, isfinite


@dataclass
# 역할: 차량 ID별 마지막 시각, 확정 위치, 임시 위치 후보를 보관합니다.
class TrackState:
    # dataclass: 차량 하나의 상태를 묶고 초기화 코드를 자동으로 만들어 줌
    last_time: float # 마지막으로 관찰한 영상 시각(초)
    side: int = 0 # 확정 위치: -1은 선 위, 1은 선 아래, 0은 아직 미확정
    point: tuple = None # 확정된 쪽에서 마지막으로 확인한 중심점 (x, y)
    candidate: int = 0 # 새로 확정하려는 위치 후보(-1 또는 1)
    candidate_count: int = 0 # 같은 위치 후보가 연속으로 관찰된 처리 프레임 수
    observed_point: tuple = None # 확정 여부와 관계없이 직전에 관찰한 중심점


# 역할: 차량별 중심점 이동을 누적하고 기준선 통과를 한 번만 기록합니다.
class LineCrossingCounter:
    # 1. 선 주변 여유 구간과 연속 확인으로 작은 흔들림을 무시합니다.
    # 역할: 기준선 선분과 흔들림·공백·속도 제한을 받아 내부 상태를 준비합니다.
    def __init__(self, line_y, x_min, x_max, margin=12,
                 stable_frames=3, max_gap_seconds=1.0, max_speed=900):
        numbers = (line_y, x_min, x_max, margin, max_gap_seconds, max_speed)
        if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in numbers) or
                type(stable_frames) is not int or x_min >= x_max or margin < 0 or stable_frames < 1 or
                max_gap_seconds <= 0 or max_speed <= 0):
            raise ValueError("기준선 범위와 안정화 설정을 확인해 주세요.")
        self.line_y = line_y
        self.x_min, self.x_max = x_min, x_max
        self.margin = margin # 선 위아래에서 판정을 보류할 거리(픽셀)
        self.stable_frames = stable_frames # 새 위치 확정에 필요한 연속 관찰 횟수
        self.max_gap_seconds = max_gap_seconds # 이전 위치를 연결할 수 있는 최대 공백
        self.max_speed = max_speed # 허용할 중심점 이동 속도(픽셀/초)
        self.states = {} # {추적 ID: 차량 상태} 형태로 여러 차량을 따로 관리
        # 1-1. 집합은 이미 통과한 추적 ID를 빠르게 검사하며 expire()가 상태를 지워도 그대로 유지됩니다.
        self.counted_ids = set() # 이미 집계한 ID 보관; 같은 ID는 한 실행에서 한 번만 집계

    # 역할: 마지막 관찰 이후 허용 시간이 지난 위치 상태를 제거합니다.
    def expire(self, timestamp):
        if (isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or
                not isfinite(timestamp) or timestamp < 0):
            raise ValueError("영상 시각은 유효한 0 이상의 숫자여야 합니다.")
        # 1-2. 오래 안 보인 차량의 위치를 새 위치와 바로 연결하지 않습니다.
        # 1-3. 딕셔너리 컴프리헨션으로 시간 제한을 넘지 않은 차량 상태만 남깁니다.
        self.states = {key: value for key, value in self.states.items()
                       if timestamp - value.last_time <= self.max_gap_seconds}

    # 역할: 새 중심점과 영상 시각을 받아 확정 통과 시 이벤트 딕셔너리를 반환합니다.
    def update(self, track_id, point, timestamp):
        if (type(track_id) is not int or track_id < 0 or not isinstance(point, (list, tuple)) or
                len(point) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in point)):
            raise ValueError("추적 ID와 중심점 좌표를 확인해 주세요.")
        # 1-4. track_id: 추적기가 붙인 차량 번호, point: 중심점, timestamp: 영상 시각
        self.expire(timestamp)
        # 1-5. setdefault(): 새 ID이면 상태를 만들고, 기존 ID이면 저장된 상태를 가져옴
        # 1-6. setdefault()는 ID가 처음이면 TrackState를 저장하고, 있으면 기존 상태를 반환합니다.
        state = self.states.setdefault(track_id, TrackState(timestamp))
        # 1-7. ID가 다른 차량으로 잘못 연결된 듯한 급격한 위치 변화는 끊습니다.
        if state.observed_point is not None:
            elapsed = timestamp - state.last_time
            if elapsed < 0:
                raise ValueError("같은 차량의 영상 시각이 역행했습니다.")
            if elapsed == 0:
                # 같은 시점의 중복 관찰로 안정화 횟수를 늘리지 않음
                return None
            # 1-8. hypot(dx, dy): 두 중심점 사이의 직선거리 계산
            distance = hypot(point[0] - state.observed_point[0],
                             point[1] - state.observed_point[1])
            # 1-9. 시간이 역행하거나 허용 거리보다 멀리 이동했다면 이전 차량 위치와 새 관찰을 분리합니다.
            if elapsed <= 0 or distance > self.max_speed * elapsed:
                state = TrackState(timestamp)
                self.states[track_id] = state
        state.last_time = timestamp
        state.observed_point = point
        x, y = point
        # 1-10. OpenCV 좌표는 아래로 갈수록 y가 커짐
        # 1-11. 예) 선 y=100, 여유 12이면 y<88은 위쪽, y>112는 아래쪽으로 판단
        # 1-12. 조건 표현식으로 선 위(-1), 아래(1), 판정 보류 영역(0)을 구분합니다.
        side = -1 if y < self.line_y - self.margin else (
            1 if y > self.line_y + self.margin else 0)
        if side == 0:
            # 1-13. 선에 너무 가까우면 후보의 연속 횟수도 끊어 흔들림을 걸러냄
            state.candidate, state.candidate_count = 0, 0
            return None

        # 2. 선 바깥 한쪽에서 여러 프레임 확인된 위치만 채택합니다.
        if side == state.side:
            # 2-1. 같은 쪽에 있는 동안 마지막 위치를 갱신해 통과 전 위치로 사용
            state.point = point
            state.candidate, state.candidate_count = 0, 0
            return None
        if side != state.candidate:
            state.candidate, state.candidate_count = side, 0
        state.candidate_count += 1
        if state.candidate_count < self.stable_frames:
            # 2-2. 반대쪽에서 잠깐 보인 것만으로는 통과를 확정하지 않음
            return None

        old_side, old_point = state.side, state.point
        state.side, state.point = side, point
        state.candidate, state.candidate_count = 0, 0
        # 2-3. 한쪽이 처음 확정된 상태에서는 통과로 세지 않고, 이미 센 ID도 다시 세지 않습니다.
        if old_side == 0 or track_id in self.counted_ids:
            # 2-4. 처음 관찰한 위치의 확정 또는 이미 집계한 ID이면 이벤트를 만들지 않음
            return None

        # 3. 무한 직선이 아니라 지정한 선분을 통과했는지 확인합니다.
        old_x, old_y = old_point
        # 3-1. 이전 중심점~현재 중심점을 직선으로 연결하고 선 높이에서의 x좌표를 계산
        # 3-2. 실제 경로를 정밀 복원하는 것이 아니라, 지정한 선분을 지났는지 확인하는 근사값
        # 3-3. 두 확정 중심점을 연결한 선분이 기준선 높이에 닿는 가로 위치를 보간합니다.
        crossing_x = old_x + (x - old_x) * (self.line_y - old_y) / (y - old_y)
        if not self.x_min <= crossing_x <= self.x_max:
            return None
        self.counted_ids.add(track_id)
        return {
            "track_id": track_id,
            "direction": "DOWN" if side == 1 else "UP",
            # 3-4. 이 시각은 선과 닿은 정확한 순간이 아니라 반대편 위치가 안정적으로 확정된 시각입니다.
            "video_seconds": round(timestamp, 3), # 반대쪽 위치가 확정된 시각
            "from_point": list(old_point),
            "to_point": list(point),
            "crossing_point": [round(crossing_x, 2), self.line_y],
        }

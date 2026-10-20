# ai_vision/recognition/live_gate_session.py
"""카메라의 단일 실행 세션을 관리하는 클래스.

프레임 시각의 소속 확인, 통과 전 OCR 표본 검사, 이벤트 전송 판단,
처리 횟수 누적 및 세션 종료를 책임집니다.
"""

# 1. 라이브러리 및 프로젝트 모듈
# 1-1. RLock은 같은 세션 객체에 대한 동시 접근을 보호하는 재진입 잠금입니다.
import threading
# 1-2. UUID는 실행마다 다른 session_id 생성에 사용합니다.
import uuid
# 1-3. Counter는 판단 유형(BLOCKED, DISABLED 등)별 개수를 셉니다.
from collections import Counter

from ai_vision.recognition.live_gate_clock import FrameStamp, LiveGateClock
from ai_vision.recognition.result_validation import public_passage
from ai_vision.recognition.vehicle_contract import validate_camera_id
from ai_vision.recognition.vehicle_delivery_flow import VehicleDeliveryFlow
from ai_vision.recognition.vehicle_live_candidate import create_live_candidate


# 2. 카메라 실행 1회에 대한 상태 관리
class LiveGateSession:
    # 2-1. camera_id와 화면 DOWN의 실제 방향을 필수로 검증합니다.
    # 2-2. clock/flow를 외부에서 주입하면 시뮬레이션과 테스트에도 사용할 수 있습니다.
    def __init__(self, camera_id, down_direction, clock=None, flow=None):
        validate_camera_id(camera_id)
        if not isinstance(down_direction, str) or down_direction not in {"ENTRY", "EXIT"}:
            raise ValueError("DOWN의 실제 입출차 방향이 필요합니다.")
        self.camera_id, self.down_direction = camera_id, down_direction
        # 2-3. 새 세션 ID를 발급해 추적 ID 재사용에 따른 혼동을 줄입니다.
        self.session_id = "gate_" + uuid.uuid4().hex
        self.clock = LiveGateClock() if clock is None else clock
        self.flow = VehicleDeliveryFlow() if flow is None else flow
        # 2-4. 종료 여부, 판단 통계, 실제 HTTP 요청 시도 수를 초기화합니다.
        self._closed, self._decisions, self._requests = False, Counter(), 0
        self._lock = threading.RLock()

    # 3. 카메라에서 수집한 프레임의 시각을 기록합니다.
    def capture(self, frame_index, monotonic_seconds=None):
        with self._lock:
            # 3-1. 종료된 세션에는 새 프레임을 받지 않습니다.
            if self._closed:
                raise ValueError("종료된 세션에는 프레임을 추가할 수 없습니다.")
            # 3-2. LiveGateClock이 프레임 인덱스, 상대 시각, UTC 시각을 관리합니다.
            return self.clock.capture(frame_index, monotonic_seconds)

    # 4. 기준선을 통과한 차량 한 건을 전송 판단 흐름에 전달합니다.
    def consume(self, passage, stamp):
        with self._lock:
            # 4-1. 종료된 세션에서는 뒤늦게 들어온 이벤트도 처리하지 않습니다.
            if self._closed:
                raise ValueError("종료된 세션에서는 후보를 처리하지 않습니다.")
            # 4-2. 시각 객체가 현재 clock이 발급한 '동일 객체'인지 검사합니다.
            if not isinstance(stamp, FrameStamp) or self.clock.lookup(stamp.frame_index) is not stamp:
                raise ValueError("다른 세션의 프레임 시각입니다.")
            # 4-3. 저장 영상의 통과 자료를 실시간 자료로 위장할 수 없습니다.
            if not isinstance(passage, dict) or passage.get("record_type") != "LIVE_TRACKED_PASSAGE":
                raise ValueError("실시간 통과 자료가 필요합니다.")
            checked = public_passage({**passage, "record_type": "LOCAL_TRACKED_PASSAGE"})
            # 4-4. 통과 시각이 현재 프레임의 경과 시각과 일치하는지 확인합니다.
            if abs(checked["video_seconds"] - stamp.elapsed_seconds) > .001:
                raise ValueError("통과 프레임과 수집 시각이 다릅니다.")

            # 5. 번호판 OCR 표본 출처를 각 프레임의 실제 기록과 대조합니다.
            for sample in passage["samples"]:
                original = self.clock.lookup(sample["frame_index"])
                # 5-1. 미래 프레임이나 다른 시각의 데이터를 끼워 넣지 못하게 합니다.
                # 5-2. 통과 순간 기준 최대 2초 전의 표본만 인정합니다.
                if (sample["frame_index"] > stamp.frame_index or
                        abs(original.elapsed_seconds - sample["video_seconds"]) > .001 or
                        not stamp.elapsed_seconds - 2 <= original.elapsed_seconds <= stamp.elapsed_seconds):
                    raise ValueError("OCR 표본이 이 세션의 통과 전 2초 범위와 일치하지 않습니다.")

            # 6. 실시간 통과 기록을 후보로 만들고 중복 억제/송신 판단을 요청합니다.
            candidate = create_live_candidate(passage, self.camera_id, self.down_direction, stamp.captured_at.isoformat())
            result = self.flow.process(self.session_id, candidate)
            # 6-1. 판단 유형과 실제 요청 시도를 별도로 기록합니다.
            self._decisions[result["decision"]] += 1
            self._requests += result["request_attempted"] is True
            return result

    # 7. 카메라 실행을 종료합니다.
    def close(self):
        # 7-1. 종료 뒤 도착한 프레임 및 이벤트가 신규 요청을 만들지 못하게 합니다.
        with self._lock:
            self._closed = True

    # 8. 저장/보고서에 사용할 실행 요약을 반환합니다.
    def summary(self):
        with self._lock:
            # 8-1. capture 프레임 수와 처리된 차량 통과 수는 서로 다른 지표입니다.
            # 8-2. request_attempts는 전송 성공이 아닌 요청 시도 횟수입니다.
            return {"record_type": "LIVE_GATE_SESSION", "session_id": self.session_id, "camera_id": self.camera_id,
                    "down_direction": self.down_direction, "started_at": self.clock.started_at.isoformat(), "closed": self._closed,
                    "captured_frames": self.clock.frame_count, "processed_passages": sum(self._decisions.values()),
                    "decision_counts": dict(self._decisions), "request_attempts": self._requests,
                    "http_enabled": self.flow.client.enabled}

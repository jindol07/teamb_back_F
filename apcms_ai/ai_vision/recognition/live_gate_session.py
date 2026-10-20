# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_session.py

"""한 카메라 실행의 시각·세션 ID·후보 처리 흐름과 종료 상태를 관리합니다."""

import threading
import uuid
from collections import Counter

from ai_vision.recognition.live_gate_clock import FrameStamp, LiveGateClock
from ai_vision.recognition.result_validation import public_passage
from ai_vision.recognition.vehicle_contract import validate_camera_id
from ai_vision.recognition.vehicle_delivery_flow import VehicleDeliveryFlow
from ai_vision.recognition.vehicle_live_candidate import create_live_candidate


class LiveGateSession:
    def __init__(self, camera_id, down_direction, clock=None, flow=None):
        validate_camera_id(camera_id)
        if not isinstance(down_direction, str) or down_direction not in {"ENTRY", "EXIT"}:
            raise ValueError("DOWN의 실제 입출차 방향이 필요합니다.")
        self.camera_id, self.down_direction = camera_id, down_direction
        self.session_id = "gate_" + uuid.uuid4().hex
        self.clock = LiveGateClock() if clock is None else clock
        self.flow = VehicleDeliveryFlow() if flow is None else flow
        self._closed, self._decisions, self._requests = False, Counter(), 0
        self._lock = threading.RLock()

    def capture(self, frame_index, monotonic_seconds=None):
        with self._lock:
            if self._closed:
                raise ValueError("종료된 세션에는 프레임을 추가할 수 없습니다.")
            return self.clock.capture(frame_index, monotonic_seconds)

    def consume(self, passage, stamp):
        with self._lock:
            if self._closed:
                raise ValueError("종료된 세션에서는 후보를 처리하지 않습니다.")
            if not isinstance(stamp, FrameStamp) or self.clock.lookup(stamp.frame_index) is not stamp:
                raise ValueError("다른 세션의 프레임 시각입니다.")
            if not isinstance(passage, dict) or passage.get("record_type") != "LIVE_TRACKED_PASSAGE":
                raise ValueError("실시간 통과 자료가 필요합니다.")
            checked = public_passage({**passage, "record_type": "LOCAL_TRACKED_PASSAGE"})
            if abs(checked["video_seconds"] - stamp.elapsed_seconds) > .001:
                raise ValueError("통과 프레임과 수집 시각이 다릅니다.")
            # 1. OCR 표본이 이 카메라 실행에서 수집한 같은 프레임인지 검사합니다.
            for sample in passage["samples"]:
                original = self.clock.lookup(sample["frame_index"])
                if (sample["frame_index"] > stamp.frame_index or
                        abs(original.elapsed_seconds - sample["video_seconds"]) > .001 or
                        not stamp.elapsed_seconds - 2 <= original.elapsed_seconds <= stamp.elapsed_seconds):
                    raise ValueError("OCR 표본이 이 세션의 통과 전 2초 범위와 일치하지 않습니다.")
            candidate = create_live_candidate(passage, self.camera_id, self.down_direction, stamp.captured_at.isoformat())
            result = self.flow.process(self.session_id, candidate)
            self._decisions[result["decision"]] += 1
            self._requests += result["request_attempted"] is True
            return result

    def close(self):
        # 2. 종료 후의 늦은 결과가 새 이벤트를 만들지 못하게 합니다.
        with self._lock:
            self._closed = True

    def summary(self):
        with self._lock:
            return {"record_type": "LIVE_GATE_SESSION", "session_id": self.session_id, "camera_id": self.camera_id,
                    "down_direction": self.down_direction, "started_at": self.clock.started_at.isoformat(), "closed": self._closed,
                    "captured_frames": self.clock.frame_count, "processed_passages": sum(self._decisions.values()),
                    "decision_counts": dict(self._decisions), "request_attempts": self._requests,
                    "http_enabled": self.flow.client.enabled}

# ai_vision/recognition/vehicle_delivery_flow.py
"""실시간 차량 이벤트 후보의 중복을 검사한 뒤 전송 결과를 기록합니다.

중요: 기본 VehicleHTTPClient는 비활성화 상태입니다. 실제 송신은 외부에서
활성화된 클라이언트를 명시적으로 주입한 경우에만 시도합니다.
"""

# 1. 외부 모듈
# 1-1. 정규식으로 session_id 형식을 엄격하게 검사합니다.
import re
# 1-2. payload 규격 검사, 중복 방지 상태 관리, HTTP 전송을 담당하는 기능입니다.
from ai_vision.recognition.vehicle_contract import validate_vehicle_payload
from ai_vision.recognition.vehicle_event_guard import VehicleEventGuard
from ai_vision.recognition.vehicle_http import VehicleHTTPClient


# 2. 한 실행 동안 사용할 전송 흐름
class VehicleDeliveryFlow:
    # 2-1. client/guard를 주입하지 않으면 각각 기본 객체를 생성합니다.
    # 2-2. 같은 실행 내에서 guard를 유지해야 이미 처리한 ID를 기억할 수 있습니다.
    def __init__(self, client=None, guard=None):
        self.client = VehicleHTTPClient() if client is None else client
        self.guard = VehicleEventGuard() if guard is None else guard

    # 3. 후보를 받아 '차단 → 비활성화 → 중복 확인 → 1회 전송' 순서로 처리합니다.
    def process(self, session_id, candidate):
        # 3-1. 세션 ID는 영문/숫자로 시작하며 이후 영문, 숫자, _, -만 허용합니다.
        # 3-2. 추적 ID가 음수이거나 정수가 아니면 유효한 차량으로 보지 않습니다.
        if (not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", session_id) or
                not isinstance(candidate, dict) or candidate.get("origin") != "LIVE" or
                type(candidate.get("track_id")) is not int or candidate["track_id"] < 0):
            raise ValueError("실시간 출처·실행 ID·차량 ID를 확인해 주세요.")
        track = candidate["track_id"]
        # 3-3. 공통 결과: 요청 여부와 자동 재시도 금지는 초기 상태에서 명확히 표시합니다.
        base = {"track_id": track, "request_attempted": False, "receipt": None, "automatic_retry_allowed": False,
                "http_enabled": self.client.enabled}

        # 4. 인식 조건을 통과하지 못한 후보는 보내지 않습니다.
        # 4-1. payload가 없는 BLOCKED 후보는 정상적인 '전송 보류' 결과입니다.
        if candidate.get("status") == "BLOCKED" and candidate.get("payload") is None:
            return {**base, "decision": "BLOCKED", "receipt_state": None}
        # 4-2. 허용된 상태는 CANDIDATE_ONLY이며 차단 이유가 없어야 합니다.
        if candidate.get("status") != "CANDIDATE_ONLY" or candidate.get("reasons") != []:
            raise ValueError("실시간 후보 상태를 확인해 주세요.")
        event = validate_vehicle_payload(candidate["payload"])

        # 5. HTTP가 비활성화되어 있다면 Guard에도 후보를 예약하지 않습니다.
        # 이후 명시적으로 활성화했을 때 최초 요청이 막히지 않도록 하는 규칙입니다.
        if not self.client.enabled:
            return {**base, "decision": "DISABLED", "receipt_state": None}

        # 6. 같은 세션의 중복 이벤트인지 확인하고 새 후보를 예약합니다.
        decision = self.guard.consider(session_id, track, event)
        result = {**base, "event_id": decision["event_id"], "decision": decision["decision"],
                  "receipt_state": decision["receipt_state"]}
        # 6-1. 이미 처리/보류된 차량이면 더 전송하지 않습니다.
        if decision["decision"] != "NEW_CANDIDATE":
            return result

        # 7. 신규 후보에 대해서만 단 한 번 전송을 시도합니다.
        try:
            receipt = self.client.send(decision["payload"])
            # 7-1. 전송 계층이 결과 구조를 제대로 반환했는지 검사합니다.
            if not isinstance(receipt, dict) or type(receipt.get("request_attempted")) is not bool:
                raise ValueError("요청 시도 여부를 확인할 수 없는 전송 결과입니다.")
            # 7-2. 응답 분류를 같은 Guard에 기록해 향후 중복 요청에 사용합니다.
            recorded = self.guard.record_result(session_id, track, event["camera_id"], receipt)
        except Exception:
            # 7-3. 오류 시 실제 서버 처리 여부가 불확실할 수 있으므로 DELIVERY_UNKNOWN.
            # 이미 예약한 이벤트를 다시 열거나 자동 재전송하지 않습니다.
            receipt = {"event_id": event["event_id"], "event_type": "VEHICLE_PASSAGE", "http_status": None,
                       "state": "DELIVERY_UNKNOWN", "reason_code": "LOCAL_DELIVERY_PROCESSING_FAILED",
                       "receipt_verified": False, "automatic_retry_allowed": False, "request_attempted": None}
            recorded = self.guard.record_result(session_id, track, event["camera_id"], receipt)
        # 8. 요청 시도와 Guard의 최신 상태를 합쳐 호출자에게 반환합니다.
        return {**result, "request_attempted": receipt["request_attempted"], "receipt": receipt,
                "receipt_state": recorded["receipt_state"]}

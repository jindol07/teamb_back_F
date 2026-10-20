# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_delivery_flow.py

"""실시간 후보를 중복 억제 후 한 번 요청하고 응답 상태를 기록합니다."""

import re

from ai_vision.recognition.vehicle_contract import validate_vehicle_payload
from ai_vision.recognition.vehicle_event_guard import VehicleEventGuard
from ai_vision.recognition.vehicle_http import VehicleHTTPClient


class VehicleDeliveryFlow:
    def __init__(self, client=None, guard=None):
        self.client = VehicleHTTPClient() if client is None else client
        self.guard = VehicleEventGuard() if guard is None else guard

    def process(self, session_id, candidate):
        if (not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", session_id) or
                not isinstance(candidate, dict) or candidate.get("origin") != "LIVE" or
                type(candidate.get("track_id")) is not int or candidate["track_id"] < 0):
            raise ValueError("실시간 출처·실행 ID·차량 ID를 확인해 주세요.")
        track = candidate["track_id"]
        base = {"track_id": track, "request_attempted": False, "receipt": None, "automatic_retry_allowed": False,
                "http_enabled": self.client.enabled}
        if candidate.get("status") == "BLOCKED" and candidate.get("payload") is None:
            return {**base, "decision": "BLOCKED", "receipt_state": None}
        if candidate.get("status") != "CANDIDATE_ONLY" or candidate.get("reasons") != []:
            raise ValueError("실시간 후보 상태를 확인해 주세요.")
        event = validate_vehicle_payload(candidate["payload"])
        if not self.client.enabled:
            # 비활성 실행은 후보를 예약하지 않아 이후 명시적 활성화 때 첫 요청이 가능합니다.
            return {**base, "decision": "DISABLED", "receipt_state": None}
        decision = self.guard.consider(session_id, track, event)
        result = {**base, "event_id": decision["event_id"], "decision": decision["decision"],
                  "receipt_state": decision["receipt_state"]}
        if decision["decision"] != "NEW_CANDIDATE":
            return result
        try:
            receipt = self.client.send(decision["payload"])
            if not isinstance(receipt, dict) or type(receipt.get("request_attempted")) is not bool:
                raise ValueError("요청 시도 여부를 확인할 수 없는 전송 결과입니다.")
            recorded = self.guard.record_result(session_id, track, event["camera_id"], receipt)
        except Exception:
            # 예약 후 예외가 생겨도 후보를 다시 열거나 자동 재전송하지 않습니다.
            receipt = {"event_id": event["event_id"], "event_type": "VEHICLE_PASSAGE", "http_status": None,
                       "state": "DELIVERY_UNKNOWN", "reason_code": "LOCAL_DELIVERY_PROCESSING_FAILED",
                       "receipt_verified": False, "automatic_retry_allowed": False, "request_attempted": None}
            recorded = self.guard.record_result(session_id, track, event["camera_id"], receipt)
        return {**result, "request_attempted": receipt["request_attempted"], "receipt": receipt,
                "receipt_state": recorded["receipt_state"]}

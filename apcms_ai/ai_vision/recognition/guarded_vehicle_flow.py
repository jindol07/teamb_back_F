# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/guarded_vehicle_flow.py

"""입출차 후보·중복 억제·가짜 Boot 응답·상태 기록을 연결합니다."""

from ai_vision.recognition.simulate_event_guard import preview_candidates
from ai_vision.recognition.simulate_vehicle_exchange import SCENARIOS, simulate_payload
from ai_vision.recognition.vehicle_event_guard import VehicleEventGuard


class MockVehicleEventFlow:
    def __init__(self, guard=None):
        self.guard = VehicleEventGuard() if guard is None else guard

    def process(self, session_id, track_id, payload, scenario="processed"):
        # 1. 잘못된 모의 설정 때문에 정상 후보를 먼저 예약하지 않도록 사전 검사합니다.
        if not isinstance(scenario, str) or scenario not in SCENARIOS:
            raise ValueError("지원하지 않는 모의 응답입니다.")
        decision = self.guard.consider(session_id, track_id, payload)
        result = {"track_id": track_id, "event_id": decision["event_id"], "decision": decision["decision"],
                  "receipt_state": decision["receipt_state"], "mock_invoked": False, "receipt": None,
                  "http_enabled": False, "sendable": False, "automatic_retry_allowed": False}
        if decision["decision"] != "NEW_CANDIDATE":
            return result
        event = decision["payload"]
        result["mock_invoked"] = True
        try:
            # 2. 실제 sender 대신 순수 모의 응답 함수만 호출합니다.
            receipt = simulate_payload(event, scenario)
            recorded = self.guard.record_result(session_id, track_id, event["camera_id"], receipt)
        except Exception:
            # 후보 예약 뒤 응답 처리 중 실패해도 재생성을 허용하지 않습니다.
            # 예외 원문은 보고서에 노출하지 않고 처리 불명 상태로 고정합니다.
            receipt = {"event_id": event["event_id"], "event_type": "VEHICLE_PASSAGE", "http_status": None,
                       "state": "DELIVERY_UNKNOWN", "reason_code": "LOCAL_RESPONSE_PROCESSING_FAILED",
                       "receipt_verified": False, "automatic_retry_allowed": False}
            recorded = self.guard.record_result(session_id, track_id, event["camera_id"], receipt)
        result.update(receipt_state=recorded["receipt_state"], receipt=receipt)
        return result


def build_flow_report(preview, scenario="processed", passes=2, flow=None):
    if not isinstance(scenario, str) or scenario not in SCENARIOS or type(passes) is not int or not 1 <= passes <= 10:
        raise ValueError("모의 응답과 반복 횟수를 확인해 주세요.")
    # 3. 원본 전체를 검증한 다음에만 후보를 예약하고 모의 응답을 처리합니다.
    session, candidates, skipped = preview_candidates(preview)
    flow = MockVehicleEventFlow() if flow is None else flow
    steps = [{"pass": number + 1, **flow.process(session, track, payload, scenario)}
             for number in range(passes) for track, payload in candidates]
    return {"record_type": "LOCAL_GUARDED_MOCK_FLOW", "run_id": session, "scenario": scenario,
            "http_enabled": False, "sendable": False, "uses_synthetic_event": False,
            "passes": passes, "candidate_inputs_per_pass": len(candidates), "skipped_blocked_per_pass": skipped,
            "mock_call_count": sum(step["mock_invoked"] for step in steps), "steps": steps,
            "note": "후보 억제부터 가짜 응답 기록까지의 AI 내부 검사입니다. 실제 카메라·HTTP 전송·DB 처리는 연결하지 않았습니다."}

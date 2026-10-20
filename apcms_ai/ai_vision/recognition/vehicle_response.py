# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_response.py

"""Boot 입출차 응답을 분류합니다. HTTP 호출이나 자동 재전송은 하지 않습니다."""

import uuid
from ai_vision.recognition.local_io import decode_object
from ai_vision.recognition.vehicle_contract import validate_vehicle_payload


def assess_response(payload, status_code=None, response_body=None, transport_error=None, now=None):
    event = validate_vehicle_payload(payload, now)
    if status_code is not None and (type(status_code) is not int or not 100 <= status_code <= 599):
        raise ValueError("유효한 HTTP 상태 코드가 필요합니다.")
    if transport_error is not None and transport_error not in {"TIMEOUT", "CONNECTION_ERROR"}:
        raise ValueError("지원하지 않는 통신 오류 종류입니다.")
    if transport_error is not None and status_code is not None:
        raise ValueError("통신 오류와 HTTP 응답은 동시에 지정할 수 없습니다.")
    result = {"event_id": event["event_id"], "event_type": event["event_type"], "http_status": status_code,
              "automatic_retry_allowed": False, "receipt_verified": False}

    def decision(state, reason):
        return {**result, "state": state, "reason_code": reason}

    # 1. 타임아웃은 서버 미처리의 증거가 아닙니다. 원본 이벤트를 보존하고 확인을 기다립니다.
    if transport_error is not None:
        return decision("DELIVERY_UNKNOWN", "TRANSPORT_" + transport_error)
    if status_code is None:
        raise ValueError("HTTP 응답 또는 통신 오류가 필요합니다.")
    if status_code in {401, 403}:
        return decision("AUTH_REQUIRED", "HTTP_AUTH_REQUIRED")
    if 300 <= status_code < 400:
        return decision("REJECTED", "REDIRECT_NOT_FOLLOWED")
    if status_code in {408, 429}:
        return decision("DELIVERY_UNKNOWN", "HTTP_RETRY_NOT_SAFE")
    if 400 <= status_code < 500:
        return decision("REJECTED", "HTTP_REQUEST_REJECTED")
    if status_code >= 500:
        return decision("DELIVERY_UNKNOWN", "HTTP_SERVER_ERROR")
    if status_code != 200:
        return decision("DELIVERY_UNKNOWN", "UNEXPECTED_HTTP_STATUS")
    # 2. HTTP 200만 보고 성공 처리하지 않고 UUID·이벤트 유형·번호판을 대조합니다.
    try:
        if isinstance(response_body, bytes):
            if len(response_body) > 65536:
                raise ValueError("응답 크기 초과")
            response_body = response_body.decode("utf-8-sig")
        if not isinstance(response_body, str) or len(response_body.encode("utf-8")) > 65536:
            raise ValueError("응답 형식 오류")
        body = decode_object(response_body)
        response_id = str(uuid.UUID(body["eventId"]))
        if (response_id != event["event_id"] or body["eventType"] != event["event_type"] or
                body["plateNumber"] != event["plate_number"] or body.get("spaceCode") is not None):
            return decision("DELIVERY_UNKNOWN", "RESPONSE_IDENTITY_MISMATCH")
        usage = body.get("parkingUsageId")
        if usage is not None and (type(usage) is not int or usage < 1):
            raise ValueError("이용 기록 ID 오류")
        outcomes = {"PROCESSED": "APPLIED", "UNCHANGED": "UNCHANGED", "PENDING": "HELD"}
        outcome = body["outcome"]
        if not isinstance(outcome, str) or outcome not in outcomes:
            return decision("DELIVERY_UNKNOWN", "UNKNOWN_OUTCOME")
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        return decision("DELIVERY_UNKNOWN", "INVALID_RESPONSE")
    # detail 원문은 경로·개인정보가 포함될 수 있어 분류 결과에 복사하지 않습니다.
    result["receipt_verified"] = True
    return decision(outcomes[outcome], "BACKEND_" + outcome)

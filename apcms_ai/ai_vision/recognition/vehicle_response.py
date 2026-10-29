# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_response.py

"""Boot 입출차 응답을 분류합니다. HTTP 호출이나 자동 재전송은 하지 않습니다."""

# 1. 응답 식별 검증에 사용하는 의존 모듈
# 1-1. uuid는 서버가 돌려준 ID를 표준 문자열로 변환합니다.
import uuid
# 1-2. decode_object는 응답 JSON을 객체로 변환합니다.
from ai_vision.recognition.local_io import decode_object
# 1-3. 송신했던 원본 요청도 동일한 계약 형식으로 검사합니다.
from ai_vision.recognition.vehicle_contract import validate_vehicle_payload, validate_space_match_payload, validate_space_release_payload


# 2. HTTP 응답이나 통신 실패를 업무 처리 결과로 분류합니다.
# 2-1. 이 함수는 서버에 요청하지 않으며 재전송도 예약하지 않습니다.
# 함수 설명: assess_response() — 상태 코드와 응답 본문을 확인하여 AI 이벤트에 대한 결과 상태를 분류합니다.
def assess_response(payload, status_code=None, response_body=None, transport_error=None, now=None):
    return _assess_response(payload, status_code, response_body, transport_error, now, validate_vehicle_payload)


def assess_space_match_response(payload, status_code=None, response_body=None, transport_error=None, now=None):
    return _assess_response(payload, status_code, response_body, transport_error, now, validate_space_match_payload)


def assess_space_release_response(payload, status_code=None, response_body=None, transport_error=None, now=None):
    return _assess_response(payload, status_code, response_body, transport_error, now, validate_space_release_payload)


def _assess_response(payload, status_code, response_body, transport_error, now, validator):
# 2-2. 먼저 비교 기준이 되는 원본 이벤트를 검증합니다.
    event = validator(payload, now)
    if status_code is not None and (type(status_code) is not int or not 100 <= status_code <= 599):
        raise ValueError("유효한 HTTP 상태 코드가 필요합니다.")
    if transport_error is not None and transport_error not in {"TIMEOUT", "CONNECTION_ERROR"}:
        raise ValueError("지원하지 않는 통신 오류 종류입니다.")
    if transport_error is not None and status_code is not None:
        raise ValueError("통신 오류와 HTTP 응답은 동시에 지정할 수 없습니다.")
# 2-3. 모든 결과는 자동 재시도를 허용하지 않도록 초기 상태를 만듭니다.
    result = {"event_id": event["event_id"], "event_type": event["event_type"], "http_status": status_code,
              "automatic_retry_allowed": False, "receipt_verified": False}

# 3. 공통 메타데이터와 상태·사유 코드를 조합하는 내부 함수
    # 함수 설명: decision() — 기본 응답 식별자와 상태·사유 코드를 합쳐 반환합니다.
    def decision(state, reason):
        return {**result, "state": state, "reason_code": reason}

    # 1. 타임아웃은 서버 미처리의 증거가 아닙니다. 원본 이벤트를 보존하고 확인을 기다립니다.
    if transport_error is not None:
        return decision("DELIVERY_UNKNOWN", "TRANSPORT_" + transport_error)
# 4. HTTP 응답이 들어온 경우 상태 코드를 먼저 분류합니다.
# 4-1. 인증 실패와 일반 요청 거부, 처리 불명 상태를 서로 구분합니다.
    if status_code is None:
        raise ValueError("HTTP 응답 또는 통신 오류가 필요합니다.")
    if status_code in {401, 403}:
        return decision("AUTH_REQUIRED", "HTTP_AUTH_REQUIRED")
    if 300 <= status_code < 400:
        return decision("REJECTED", "REDIRECT_NOT_FOLLOWED")
# 4-2. 타임아웃/요청 제한은 서버 처리 여부가 불명확할 수 있습니다.
    if status_code in {408, 429}:
        return decision("DELIVERY_UNKNOWN", "HTTP_RETRY_NOT_SAFE")
    if 400 <= status_code < 500:
        return decision("REJECTED", "HTTP_REQUEST_REJECTED")
    if status_code >= 500:
        return decision("DELIVERY_UNKNOWN", "HTTP_SERVER_ERROR")
# 4-3. 200이 아닌 예상 밖 2xx 응답은 성공으로 간주하지 않습니다.
    if status_code != 200:
        return decision("DELIVERY_UNKNOWN", "UNEXPECTED_HTTP_STATUS")
    # 2. HTTP 200만 보고 성공 처리하지 않고 UUID·이벤트 유형·번호판을 대조합니다.
# 5. HTTP 200 응답의 본문을 확인합니다.
# 5-1. 크기를 제한하고 문자열·JSON·UUID·번호판을 원본 요청과 대조합니다.
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
                body["plateNumber"] != event["plate_number"] or body.get("spaceCode") != event.get('space_code')):
            return decision("DELIVERY_UNKNOWN", "RESPONSE_IDENTITY_MISMATCH")
# 5-2. 주차 이용 기록 ID는 있으면 양의 정수인지 확인합니다.
        usage = body.get("parkingUsageId")
        if usage is not None and (type(usage) is not int or usage < 1):
            raise ValueError("이용 기록 ID 오류")
# 5-3. 백엔드 상태 PROCESSED/UNCHANGED/PENDING을 내부 처리 상태로 변환합니다.
        outcomes = {"PROCESSED": "APPLIED", "UNCHANGED": "UNCHANGED", "PENDING": "HELD"}
        outcome = body["outcome"]
        if not isinstance(outcome, str) or outcome not in outcomes:
            return decision("DELIVERY_UNKNOWN", "UNKNOWN_OUTCOME")
        if event['event_type'] == 'VEHICLE_SPACE_MATCH':
            parking_decision = body.get('parkingDecision')
            if parking_decision is None:
                parking_decision = 'UNDETERMINED'  # 구형 서버 응답을 오주차로 추측하지 않습니다.
            elif (parking_decision not in ('MATCHED', 'WRONG_SPACE', 'NO_VALID_RESERVATION', 'UNDETERMINED')
                  or (outcome != 'PENDING' and parking_decision == 'UNDETERMINED')
                  or (outcome == 'PENDING' and parking_decision == 'MATCHED')):
                raise ValueError('주차 판정과 처리 결과가 일치하지 않습니다.')
            result['parking_decision'] = parking_decision
        if event['event_type'] == 'VEHICLE_PASSAGE':
            result['parking_usage_id'] = usage
        if event['event_type'] == 'VEHICLE_SPACE_MATCH' and outcome != 'PENDING' and usage is None:
            raise ValueError('구획 연결 성공 응답에는 이용 ID가 필요합니다.')
        if event['event_type'] in ('VEHICLE_SPACE_MATCH', 'VEHICLE_SPACE_RELEASE'):
            version = body.get('linkVersion')
            if version is not None and (type(version) is not int or not 0 <= version < 10**18):
                raise ValueError('연결 버전 응답 오류')
            if event['event_type'] == 'VEHICLE_SPACE_RELEASE':
                if usage != event['parking_usage_id'] or outcome == 'UNCHANGED':
                    raise ValueError('해제 이용 또는 결과 불일치')
                if outcome == 'PROCESSED' and version != event['link_version'] + 1:
                    raise ValueError('해제 이후 연결 버전 불일치')
            result.update(parking_usage_id=usage, link_version=version)

# 5-4. 손상된 응답은 완료로 인정하지 않고 DELIVERY_UNKNOWN으로 분류합니다.
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        return decision("DELIVERY_UNKNOWN", "INVALID_RESPONSE")
    # detail 원문은 경로·개인정보가 포함될 수 있어 분류 결과에 복사하지 않습니다.
# 6. 응답의 이벤트 식별이 확인된 경우만 검증 플래그를 켭니다.
# 6-1. 이는 DB 반영을 독립적으로 확인했다는 뜻은 아닙니다.
    result["receipt_verified"] = True
    return decision(outcomes[outcome], "BACKEND_" + outcome)

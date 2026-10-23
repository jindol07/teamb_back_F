# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_contract.py

"""Boot 차량 통과 요청의 AI 측 검증. 네트워크나 환경변수를 사용하지 않습니다."""

# 1. 요청 검증에 필요한 모듈
# 1-1. math는 신뢰도 점수가 유한한 숫자인지 확인합니다.
import math
# 1-2. re는 날짜·번호판 문자열이 정해진 규칙에 맞는지 확인합니다.
import re
# 1-3. unicodedata는 조합형 한글 등을 표준 Unicode 형태로 정규화합니다.
import unicodedata
# 1-4. uuid는 이벤트 고유 식별자가 올바른 UUID인지 확인합니다.
import uuid
# 1-5. datetime은 타임존·미래 감지 시각 허용 범위를 검사합니다.
from datetime import datetime, timedelta, timezone

# 2. Spring Boot와 합의된 전송 경로·인증 헤더·필수 항목
# 2-1. 이 모듈은 전송 자체를 수행하지 않고 데이터 형식만 검증합니다.
VEHICLE_ENDPOINT = "/api/parking/ai/vehicle-events"
SPACE_MATCH_ENDPOINT = "/api/parking/ai/space-match-events"
AUTH_HEADER = "X-AI-API-Key"
REQUIRED = {"event_id", "event_type", "detected_at", "camera_id", "direction", "plate_number", "confidence"}


# 3. ISO-8601 감지 시각 확인
# 3-1. 영상 재생 시각(예: 3.5초)은 실제 이벤트 날짜가 아니므로 허용하지 않습니다.
# 함수 설명: parse_detected_at() — 타임존이 명시된 감지 시각을 파싱하고 허용 오프셋을 검사합니다.
def parse_detected_at(value):
    # 1. 영상 상대 초만으로 실제 날짜를 만들지 않고 명시된 타임존을 요구합니다.
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)", value):
        raise ValueError("감지 시각은 타임존 포함 ISO-8601이어야 합니다.")
# 3-2. Z(UTC)를 +00:00으로 바꿔 파싱하고 표준 시간대 유무를 검사합니다.
    at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if at.utcoffset() is None or abs(at.utcoffset()) > timedelta(hours=18):
        raise ValueError("감지 시각의 타임존 범위가 유효하지 않습니다.")
# 3-3. 검증을 통과한 타임존 포함 datetime을 반환합니다.
    return at


# 4. 카메라 고유 ID 검증
# 4-1. 공백 문자열·제어문자·Java 문자열 길이 제한 위반을 거부합니다.
# 함수 설명: validate_camera_id() — 카메라 식별자의 길이와 제어 문자를 검증합니다.
def validate_camera_id(value):
    # Java String.length와 동일하게 UTF-16 코드 단위 60자를 제한합니다.
    if (not isinstance(value, str) or not value.strip() or len(value.encode("utf-16-le")) // 2 > 60 or
            any(ord(char) < 32 for char in value)):
        raise ValueError("camera_id는 비어 있지 않은 60자 이내 식별자여야 합니다.")
    return value


# 5. 차량 통과 이벤트 전체를 검증하고 정규화합니다.
# 5-1. 필수 7개 필드 이외의 의도하지 않은 값이 들어오는지 확인합니다.
# 함수 설명: validate_vehicle_payload() — Boot 전송 필드, 방향, UUID, 번호판, 신뢰도와 미래 시각 제한을 검사합니다.
def validate_vehicle_payload(payload, now=None):
    if not isinstance(payload, dict) or not REQUIRED <= set(payload) or set(payload) - REQUIRED - {"space_code", "method"}:
        raise ValueError("차량 통과 요청 필드를 확인해 주세요.")
# 5-2. VEHICLE_PASSAGE 유형과 실제 입차/출차 구분만 허용합니다.
    if payload["event_type"] != "VEHICLE_PASSAGE" or not isinstance(payload["direction"], str) or payload["direction"] not in {"ENTRY", "EXIT"}:
        raise ValueError("차량 통과 유형과 방향이 유효하지 않습니다.")
# 5-3. 주차구획은 별도 업무 처리이므로 통과 이벤트에서 함께 전달하지 않습니다.
    if payload.get("space_code") is not None or payload.get("method") is not None:
        raise ValueError("차량 통과 요청에는 주차구획 매칭 필드를 넣지 않습니다.")
    if not isinstance(payload["event_id"], str):
        raise ValueError("event_id는 UUID 문자열이어야 합니다.")
# 5-4. UUID 문자열을 표준 형식으로 변환합니다.
    event_id = str(uuid.UUID(payload["event_id"]))
    camera = validate_camera_id(payload["camera_id"])
    plate = payload["plate_number"]
    if not isinstance(plate, str):
        raise ValueError("차량번호는 문자열이어야 합니다.")
# 5-5. 한글을 정규화하고 공백을 제거한 뒤 한국 번호판 형식을 검사합니다.
    plate = re.sub(r"\s+", "", unicodedata.normalize("NFC", plate))
    if not re.fullmatch(r"[0-9]{2,3}[가-힣][0-9]{4}", plate):
        raise ValueError("지원하는 한국 번호판 형식이 아닙니다.")
# 5-6. confidence는 0~1 사이의 탐지 점수이며 정답률을 의미하지 않습니다.
    confidence = payload["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1 or not math.isfinite(confidence):
        raise ValueError("confidence는 유한한 0~1 숫자여야 합니다.")
    at = parse_detected_at(payload["detected_at"])
# 5-7. 60초를 넘는 미래 이벤트는 잘못된 장치 시간일 수 있어 거부합니다.
    current = datetime.now(timezone.utc) if now is None else now
    if not isinstance(current, datetime) or current.utcoffset() is None:
        raise ValueError("현재 시각에도 타임존이 필요합니다.")
    if at > current + timedelta(seconds=60):
        raise ValueError("60초를 넘는 미래 감지 시각은 허용하지 않습니다.")
    # 2. 원본 딕셔너리를 바꾸지 않고 검증된 7개 전송 필드만 반환합니다.
    return {"event_id": event_id, "event_type": "VEHICLE_PASSAGE", "detected_at": at.isoformat(),
            "camera_id": camera, "direction": payload["direction"], "plate_number": plate, "confidence": float(confidence)}


def validate_space_match_payload(payload, now=None):
    # 구획 연결을 입출차로 보내지 않고 기존 Boot 전용 계약으로 검사합니다.
    required = (REQUIRED - {'direction'}) | {'space_code', 'method'}
    if (not isinstance(payload, dict) or not required <= payload.keys()
            or payload.keys() - required - {'direction'}
            or payload.get('direction') is not None or payload.get('event_type') != 'VEHICLE_SPACE_MATCH'):
        raise ValueError('구획 연결 요청 필드를 확인하세요.')
    if (not isinstance(payload['space_code'], str)
            or not re.fullmatch(r'[1-9][0-9]*F-[A-Z][0-9]{2,}', payload['space_code'])
            or payload['method'] not in ('TRACKING', 'PLATE_OCR')):
        raise ValueError('구획 코드와 연결 방법을 확인하세요.')
    # UUID·원본 시각·카메라·번호판·점수 검증은 공통 규칙을 재사용합니다.
    common = {key: payload[key] for key in REQUIRED - {'direction', 'event_type'}}
    common.update(event_type='VEHICLE_PASSAGE', direction='ENTRY')
    event = validate_vehicle_payload(common, now)
    event.pop('direction')
    event.update(event_type='VEHICLE_SPACE_MATCH', space_code=payload['space_code'], method=payload['method'])
    return event


SPACE_RELEASE_ENDPOINT = '/api/parking/ai/space-release-events'


def validate_space_release_payload(payload, now=None):
    required = {'event_id', 'event_type', 'detected_at', 'camera_id', 'plate_number',
                'space_code', 'parking_usage_id', 'link_version', 'reason'}
    if (not isinstance(payload, dict) or set(payload) != required
            or payload.get('event_type') != 'VEHICLE_SPACE_RELEASE'
            or payload.get('reason') != 'CONFIRMED_EMPTY'
            or type(payload.get('parking_usage_id')) is not int or not 0 < payload['parking_usage_id'] <= 9223372036854775807
            or type(payload.get('link_version')) is not int or not 0 <= payload['link_version'] < 10**18 - 1):
        raise ValueError('해제 이용·버전·연속 빈자리 근거를 확인하세요.')
    event = validate_space_match_payload({key: payload[key] for key in
        ('event_id', 'detected_at', 'camera_id', 'plate_number', 'space_code')} |
        {'event_type': 'VEHICLE_SPACE_MATCH', 'confidence': 0, 'method': 'TRACKING'}, now)
    event.pop('confidence')
    event.pop('method')
    return event | {'event_type': 'VEHICLE_SPACE_RELEASE', 'parking_usage_id': payload['parking_usage_id'],
                    'link_version': payload['link_version'], 'reason': 'CONFIRMED_EMPTY'}

# D:/finalProjectB/back/apcms_ai/ai_vision/parking/parking_event_sender.py
# APCMS AI 이벤트 전송 모듈
# 1. 차량 입출차, 차량·구획 매칭, 주차면 점유 이벤트 생성
# 2. 세 종류의 이벤트를 각각 대응하는 Spring Boot API로 전송
# 3. 전송 실패 시 원본 UUID를 유지하여 재전송
# 4. PENDING 및 거부 이벤트는 별도로 보관하여 잘못된 자동 처리 방지

import json
import math
import os
import uuid
import requests
from contextlib import contextmanager
from urllib.parse import urlsplit

from datetime import datetime

from ai_vision.paths import BASE_DIR, RESULT_DIR
from ai_vision.parking.occupancy_response import validate_occupancy_response


# 1. Spring Boot 연동 환경설정

# 1-1. 프로젝트 최상위 .env에서 API 주소, 인증키, 송신 여부 로드
# 환경변수가 이미 정의되어 있다면 해당 값을 우선 사용
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent / ".env")

except ImportError:
    # dotenv 없이도 운영체제 환경변수로 설정할 수 있음
    pass


# 1-2. 세 이벤트 API가 공통으로 사용하는 서버 주소
# 팀원의 IP를 Python 소스에 직접 기록하지 않도록 환경변수로 관리
BASE_URL = os.getenv(
    "PARKING_AI_BASE_URL",
    "http://127.0.0.1:81"
).rstrip("/")

API_PATH = "/alpharking/admin/api/parking/ai"


def _validated_url(value):
    # 1-3. 비밀 정보가 포함된 주소·잘못된 포트는 실제 전송 전에 거부합니다.
    if not isinstance(value, str) or not value:
        raise ValueError("AI 이벤트 API 주소를 확인하세요.")
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or
            parsed.username is not None or parsed.password is not None or '?' in value or '#' in value or
            any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError("인증정보·쿼리 없는 HTTP(S) API 주소가 필요합니다.")
    try:
        if parsed.port == 0:
            raise ValueError()
    except ValueError:
        raise ValueError("AI 이벤트 API 포트를 확인하세요.") from None
    return value.rstrip('/'), parsed.path.rstrip('/')


def _build_event_urls(base_url, occupancy_url=None):
    # 1-4. 서버 주소만 받던 기존 설정과 관리자 경로를 포함한 현재 설정을 모두 지원합니다.
    base, path = _validated_url(base_url)
    if not path:
        root = base + API_PATH
    elif path.endswith('/api/parking/ai'):
        root = base
    else:
        root = base + '/api/parking/ai'
    urls = {"VEHICLE_PASSAGE": root + '/vehicle-events',
            "VEHICLE_SPACE_MATCH": root + '/space-match-events',
            "PARKING_OCCUPANCY": root + '/occupancy-events'}
    # 직접 지정한 점유 API 주소는 다른 두 이벤트의 주소에 영향을 주지 않습니다.
    if occupancy_url:
        _validated_url(occupancy_url)
        urls['PARKING_OCCUPANCY'] = occupancy_url
    return urls


def _configured_api_key(environment):
    # 점유 전용 키가 있으면 우선 사용하고, 비어 있으면 현재 Boot 공용 키를 사용합니다.
    return environment.get('PARKING_AI_API_KEY') or environment.get('AI_OCCUPANCY_API_KEY', '')


# 1-4. 이벤트 종류별로 요청할 API 주소 관리
# 공통 전송 함수에서 event_type만으로 전송 주소를 결정할 수 있음
API_URLS = _build_event_urls(BASE_URL, os.getenv('PARKING_AI_API_URL'))
API_URL = API_URLS['PARKING_OCCUPANCY']


# 1-5. API 인증키 및 실제 전송 활성화 여부
# SEND_ENABLED가 false이면 실제 DB를 변경하지 않고 JSON만 출력
API_KEY = _configured_api_key(os.environ)

SEND_ENABLED = (
    os.getenv(
        "PARKING_AI_SEND_ENABLED",
        "false"
    ).lower() == "true"
)


# 1-6. 전송 상태에 따라 이벤트를 보관할 파일
# pending: 재전송 가능한 미완료 이벤트
# rejected: 잘못된 요청 등 백엔드에서 거부된 이벤트
# held: PENDING 등 자동으로 재전송해서는 안 되는 이벤트
SAVE_DIR = RESULT_DIR / "parking"

PENDING_PATH = SAVE_DIR / "pending_events.json"
REJECTED_PATH = SAVE_DIR / "rejected_events.json"
HELD_PATH = SAVE_DIR / "held_events.json"


# 1-7. AI 내부에서 사용하는 구획 번호와 DB 구획 코드 연결
# 현재 웹캠 테스트의 A-01은 실제 DB의 1F-A01에 대응
# 나중에 카메라와 주차구역이 늘어나면 매핑도 확장해야 함
SPACE_CODE_MAP = {
    "A-01": "1F-A01",
    "A-02": "1F-A02",
    "A-03": "1F-A03",
    "A-04": "1F-A04"
}


@contextmanager
def scoped_space_mapping(mapping=None):
    """현재 카메라 작업에서만 구획을 연결하고 종료 시 기존 연결을 복원합니다."""
    import re
    mapping = {} if mapping is None else mapping
    if (not isinstance(mapping, dict) or
            any(not isinstance(k, str) or not isinstance(v, str) or
                not re.fullmatch(r'[1-9][0-9]*F-[A-Z][0-9]{2}', v)
                for k, v in mapping.items()) or len(set(mapping.values())) != len(mapping)):
        raise ValueError('카메라 구획 매핑을 확인하세요.')
    previous = SPACE_CODE_MAP.copy()
    try:
        SPACE_CODE_MAP.update(mapping)
        yield
    finally:
        SPACE_CODE_MAP.clear()
        SPACE_CODE_MAP.update(previous)


# 1-8. 백엔드가 처리 완료로 사용하는 outcome 값
# DUPLICATE는 이미 처리된 이벤트일 수 있으므로
# 신규 처리 성공과 구분하여 로그에 남기는 것이 중요
SUCCESS_OUTCOMES = {
    "PROCESSED",
    "UPDATED",
    "UNCHANGED",
    "DUPLICATE"
}


# 2. 이벤트 생성에 공통으로 사용하는 함수

# 2-1. 타임존이 포함된 감지 시각 생성
# Python과 Spring Boot가 다른 PC에서 실행되더라도 이벤트 발생 시각을 동일한 기준으로 해석할 수 있도록 함
def current_detected_at():

    return (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )


# 2-2. 신뢰도와 변화율 검증
def validate_ratio(value, name):

    # True, False가 숫자 1, 0으로 변환되는 것을 방지
    if isinstance(value, bool):
        raise ValueError(f"{name}은 숫자여야 합니다.")

    try:
        number = float(value)

    except (TypeError, ValueError):
        raise ValueError(f"{name}은 숫자여야 합니다.")

    # 잘못된 수치가 DB로 넘어가는 것을 이벤트 생성 단계에서 차단
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f"{name}은 0~1 사이여야 합니다.")

    return round(number, 4)


# 2-3. AI 구획 번호를 실제 백엔드 코드로 변환
# 잘못된 구획 코드를 전송하여 다른 주차면이 변경되는 것을 방지
def convert_space_code(space_id):

    if space_id in SPACE_CODE_MAP:
        return SPACE_CODE_MAP[space_id]

    # 이미 1F-A01 형식으로 전달된 경우에는 그대로 사용
    if space_id in SPACE_CODE_MAP.values():
        return space_id

    raise ValueError(
        f"등록되지 않은 주차구획 ID입니다: {space_id}"
    )


# 2-4. 차량번호 확인
# AI 결과에 plate_type이 포함되었다면 KOREAN_VALID만 통과
# REVIEW, OCR_FAILED 결과가 확정 번호판으로 전송되는 것을 방지
def validate_plate(plate_number, plate_type=None):

    if (
        not isinstance(plate_number, str)
        or not plate_number.strip()
    ):
        raise ValueError("차량번호가 필요합니다.")

    if (
        plate_type is not None
        and plate_type != "KOREAN_VALID"
    ):
        raise ValueError(
            "확정되지 않은 번호판은 전송하지 않습니다."
        )

    # 수동 테스트에서는 plate_type 없이 번호판을 직접 전달할 수 있음
    # 실제 AI 자동 연동 시에는 plate_type도 반드시 전달할 것
    return plate_number.strip()


# 3. 차량 입출차 이벤트 생성

# 입차와 출차는 같은 VEHICLE_PASSAGE API를 사용
# direction 값으로 ENTRY와 EXIT를 구분하며 주차구획은 포함하지 않음
def create_vehicle_event(
    plate_number,
    direction,
    confidence,
    camera_id="GATE_CAM_01",
    plate_type=None
):

    # 3-1. 백엔드에서 허용하는 입출차 방향인지 확인
    if direction not in {"ENTRY", "EXIT"}:
        raise ValueError(
            "direction은 ENTRY 또는 EXIT여야 합니다."
        )

    # 3-2. 차량번호와 신뢰도를 전송 가능한 값으로 검증
    plate_number = validate_plate(
        plate_number,
        plate_type
    )

    confidence = validate_ratio(
        confidence,
        "confidence"
    )

    # 이벤트 발생 카메라를 확인할 수 있도록 ID 필수 처리
    if not camera_id:
        raise ValueError("camera_id가 필요합니다.")

    # 3-3. 차량 통과 사실만 이벤트로 생성
    # 입차 직후에는 아직 어느 구획에 주차할지 알 수 없으므로
    # space_code는 넣지 않음
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "VEHICLE_PASSAGE",
        "detected_at": current_detected_at(),
        "camera_id": camera_id,
        "direction": direction,
        "plate_number": plate_number,
        "confidence": confidence
    }


# 4. 차량과 주차구획 매칭 이벤트 생성

# 차량 추적이나 주차 위치 OCR로 특정 차량의 구획을 확인했을 때 사용
# 실제 영상 기반 매칭 로직은 아직 별도 개발이 필요함
def create_space_match_event(
    plate_number,
    space_id,
    confidence,
    method,
    camera_id="PARKING_CAM_01",
    plate_type=None
):

    # 4-1. 차량과 구획을 연결한 판단 근거 확인
    # TRACKING: 차량 이동 궤적을 이용한 매칭
    # PLATE_OCR: 주차 위치에서 번호판을 재인식한 매칭
    if method not in {"TRACKING", "PLATE_OCR"}:
        raise ValueError(
            "method는 TRACKING 또는 PLATE_OCR이어야 합니다."
        )

    # 4-2. 번호판, 구획 코드, 신뢰도 검증
    plate_number = validate_plate(
        plate_number,
        plate_type
    )

    space_code = convert_space_code(space_id)

    confidence = validate_ratio(
        confidence,
        "confidence"
    )

    if not camera_id:
        raise ValueError("camera_id가 필요합니다.")

    # 4-3. 확인된 차량과 구획의 매칭 결과 생성
    # 백엔드에서는 활성 입차 기록 및 OCCUPIED 상태를 추가 검증
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "VEHICLE_SPACE_MATCH",
        "detected_at": current_detected_at(),
        "camera_id": camera_id,
        "plate_number": plate_number,
        "space_code": space_code,
        "confidence": confidence,
        "method": method
    }


# 5. 주차면 점유 이벤트 생성 (기존 함수 유지)

# OpenCV에서 확정한 주차면 상태를 백엔드 JSON 규격으로 변환
# 차량번호를 알 수 없어도 구획의 점유 여부만 전달할 수 있음
def create_occupancy_event(
    space_id,
    status,
    change_ratio
):

    # 5-1. AI 구획 번호를 DB 구획 코드로 변환
    space_code = convert_space_code(space_id)

    # 5-2. AI에서는 EMPTY, 백엔드에서는 AVAILABLE 사용
    if status == "OCCUPIED":
        api_status = "OCCUPIED"

    elif status in {"EMPTY", "AVAILABLE"}:
        api_status = "AVAILABLE"

    else:
        raise ValueError(
            f"알 수 없는 점유 상태입니다: {status}"
        )

    # 5-3. 빈 주차면 대비 변화 픽셀의 비율
    # 주차면 점유 판단에 사용한 변화율이며 OCR 신뢰도가 아님
    change_ratio = validate_ratio(
        change_ratio,
        "change_ratio"
    )

    # 5-4. 상태가 확정된 시점에 하나의 이벤트 생성
    # 같은 상태가 지속되는 동안에는 호출 측에서 중복 생성을 막아야 함
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "PARKING_OCCUPANCY",
        "detected_at": current_detected_at(),
        "space_code": space_code,
        "status": api_status,
        "change_ratio": change_ratio,
        "source": "AI"
    }


# 6. JSON 파일 읽기 및 저장 공통 함수

# 6-1. 대기, 거부, 보류 이벤트 파일을 동일한 구조로 읽음
# 파일이 없을 때는 아직 해당 이벤트가 없다는 뜻으로 빈 목록 반환
def load_event_list(path):

    if not path.is_file():
        return []

    with open(path, "r", encoding="utf-8") as file:
        events = json.load(file)

    # 예상하지 않은 JSON 구조를 조용히 덮어쓰지 않도록 확인
    if not isinstance(events, list):
        raise ValueError(
            f"이벤트 파일 형식 오류: {path}"
        )

    return events


# 6-2. 이벤트 목록을 디스크에 저장
# HTTP 전송보다 먼저 저장하는 구조이므로 프로그램이 중간에 종료되어도 미전송 이벤트를 복구할 수 있음
def save_event_list(path, events):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # 기존 파일을 직접 덮어쓰다가 중단되는 문제를 줄이기 위해 임시 파일에 기록을 마친 다음 원본 파일과 교체
    temp_path = path.with_suffix(".tmp")

    with open(
        temp_path,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            events,
            file,
            ensure_ascii=False,
            indent=4
        )

    os.replace(temp_path, path)


# 7. 기존 대기 이벤트 관리 함수 유지

# 다른 주차면 감지 코드에서 사용하던 함수명과의 호환성 유지
def load_pending_events():
    return load_event_list(PENDING_PATH)


def save_pending_events(events):
    save_event_list(PENDING_PATH, events)


# 8. 백엔드에서 거부한 이벤트 보관

# HTTP 409 등의 요청 거부는 단순 네트워크 장애와 다르므로 무한히 재전송하지 않고 별도 파일에 원본과 오류 내용을 기록
def save_rejected_event(event, response):

    rejected_events = load_event_list(REJECTED_PATH)

    rejected_events.append({
        "event": event,
        "http_status": response.status_code,
        "response_body": response.text,
        "rejected_at": current_detected_at()
    })

    save_event_list(
        REJECTED_PATH,
        rejected_events
    )


# 9. 백엔드 처리 보류 이벤트 저장

# HTTP 200이어도 outcome=PENDING이면 업무 처리가 완료되지 않은 상태
# 선행 조건이 해결되기 전까지 자동으로 반복 전송하지 않도록 별도 보관
def save_held_event(
    event,
    reason,
    response_data=None
):

    held_events = load_event_list(HELD_PATH)

    held_events.append({
        "event": event,
        "reason": reason,
        "response": response_data,
        "held_at": current_detected_at()
    })

    save_event_list(
        HELD_PATH,
        held_events
    )


# 10. 전송 대기 이벤트 처리 및 재시도

# 대기 목록의 가장 오래된 이벤트부터 순서대로 전송
# 성공한 이벤트는 제거하고, 완료되지 않은 이벤트는 상태별로 보관
def retry_pending_events():

    # 10-1. 테스트 모드에서는 대기 이벤트도 전송하지 않음
    if not SEND_ENABLED:
        print(
            "[전송 비활성화] 실제 API 요청을 보내지 않습니다."
        )
        return []

    # 10-2. 인증키가 없으면 기존 대기 목록을 유지
    if not API_KEY:
        print(
            "[전송 대기] PARKING_AI_API_KEY 또는 AI_OCCUPANCY_API_KEY가 없습니다."
        )
        return []

    events = load_pending_events()
    results = []

    while events:

        event = events[0]
        event_type = event.get("event_type")
        event_id = event.get("event_id")

        # 10-3. 이벤트 종류별로 수신 API 선택
        # 하나의 대기 파일에 세 종류의 이벤트가 섞여 있어도 각각 올바른 백엔드 URL로 전송
        api_url = API_URLS.get(event_type)

        if not api_url:
            raise ValueError(
                f"지원하지 않는 이벤트 종류: {event_type}"
            )

        headers = {
            "Content-Type": "application/json",
            "X-AI-API-Key": API_KEY
        }

        try:
            # 10-4. 백엔드 전송
            # 연결 제한 3초, 응답 대기 제한 15초
            # 서버가 오래 응답하지 않을 때 무한정 정지하지 않도록 설정
            response = requests.post(
                api_url,
                headers=headers,
                json=event,
                timeout=(3, 15),
                # 서버 이동 응답을 따라 인증키와 이벤트를 다른 주소로 전달하지 않습니다.
                allow_redirects=False
            )

        except requests.RequestException as error:

            # 10-5. 연결 실패 또는 응답 수신 실패
            # 서버가 요청을 이미 처리했을 가능성도 있으므로 새로운 UUID를 만들지 않고 원본 이벤트를 그대로 대기
            print(
                f"[통신 오류] event_id={event_id}"
            )
            print(error)
            return results

        # 10-6. 백엔드가 요청을 거부한 경우
        # 408/429를 제외한 4xx는 수정 없이 반복 전송해도 다시 거부될 가능성이 높아 rejected 파일에 기록
        if response.status_code == 409 or (
            400 <= response.status_code < 500
            and response.status_code not in {408, 429}
        ):

            save_rejected_event(
                event,
                response
            )

            print(
                f"[요청 거부] HTTP {response.status_code}, "
                f"event_id={event_id}"
            )

            # 거부 내역 저장에 성공한 뒤 대기 목록에서 제거
            events.pop(0)
            save_pending_events(events)

            results.append({
                "event_id": event_id,
                "status": "REJECTED"
            })

            return results

        # 10-7. 서버 오류나 요청 제한으로 처리 결과를 확정할 수 없는 경우
        # 이때는 대기 목록에서 삭제하지 않고 다음 재시도를 기다림
        if response.status_code in {408, 429} or (
            response.status_code >= 500
        ):
            print(
                f"[전송 보류] HTTP {response.status_code}, "
                f"event_id={event_id}"
            )
            return results

        if not 200 <= response.status_code < 300:
            print(
                f"[응답 확인 필요] HTTP {response.status_code}"
            )
            return results

        # 10-8. HTTP 성공 후 실제 백엔드 처리 결과 확인
        # 200 OK만으로 DB 반영이 완료됐다고 판단하지 않음
        try:
            response_data = response.json()

            if not isinstance(response_data, dict):
                raise ValueError(
                    "응답이 JSON 객체가 아닙니다."
                )

            outcome = response_data.get("outcome")

        except (ValueError, AttributeError):
            outcome = None
            response_data = {
                "http_status": response.status_code,
                "body": response.text
            }

        # 10-8-1. 점유 응답은 Boot 계약과 요청 ID·구획·상태를 함께 확인합니다.
        # 불일치는 처리 완료로 추정하거나 자동 재전송하지 않고 확인용으로 보관합니다.
        if event_type == 'PARKING_OCCUPANCY':
            try:
                outcome = validate_occupancy_response(event, response_data)
            except ValueError:
                save_held_event(event, 'INVALID_OCCUPANCY_RESPONSE', response_data)
                events.pop(0)
                save_pending_events(events)
                results.append({'event_id': event_id, 'status': 'HELD',
                                'reason': 'INVALID_OCCUPANCY_RESPONSE'})
                return results
            if outcome in {'SKIPPED_PROTECTED', 'SKIPPED_BEFORE_CORRECTION'}:
                # Boot가 기록은 남겼지만 상태를 반영하지 않은 결과도 별도로 남깁니다.
                save_held_event(event, outcome, response_data)
                events.pop(0)
                save_pending_events(events)
                results.append({'event_id': event_id, 'status': outcome, 'response': response_data})
                continue

        # 10-9. 선행 조건이 부족해 PENDING이 발생한 경우
        # 입차 기록, 구획 점유 등 조건을 먼저 확인해야 하므로 held 파일로 옮기고 자동 재전송은 중단
        if outcome == "PENDING":

            save_held_event(
                event,
                "BACKEND_PENDING",
                response_data
            )

            events.pop(0)
            save_pending_events(events)

            print(
                f"[PENDING 보관] event_id={event_id}"
            )

            results.append({
                "event_id": event_id,
                "status": "PENDING"
            })

            return results

        # 10-10. 정상 처리되었거나 기존 처리 이력과 중복인 경우
        # 완료된 이벤트를 대기 목록에서 제거하여 불필요한 전송 방지
        if outcome in SUCCESS_OUTCOMES:

            print(
                f"[전송 완료] {event_type}, "
                f"event_id={event_id}, outcome={outcome}"
            )

            events.pop(0)
            save_pending_events(events)

            results.append({
                "event_id": event_id,
                "status": outcome,
                "response": response_data
            })

            continue

        # 10-11. 계약에 없는 응답값은 완료로 추정하지 않음
        # 별도 보관하고 원인을 확인한 후 처리하도록 중단
        save_held_event(
            event,
            "UNKNOWN_OUTCOME",
            response_data
        )

        events.pop(0)
        save_pending_events(events)

        print(
            f"[응답 확인 필요] event_id={event_id}, "
            f"outcome={outcome}"
        )

        return results

    return results


# 11. 세 API 공통 이벤트 등록 및 전송

# 이벤트 생성 함수에서 만든 JSON을 가장 먼저 이 함수에 전달
# 실제 전송 모드에서는 파일 저장을 먼저 수행한 뒤 POST 시도
def queue_ai_event(event):

    # 11-1. 지원하는 이벤트 형식인지 확인
    event_type = event.get("event_type")

    if event_type not in API_URLS:
        raise ValueError(
            f"지원하지 않는 이벤트 종류: {event_type}"
        )

    # 11-2. 테스트 모드는 JSON 출력만 수행
    # 다른 팀원이 운영 중인 공유 DB를 실수로 변경하지 않도록 보호
    if not SEND_ENABLED:

        print("\n[API 전송 테스트 모드]")
        print(
            json.dumps(
                event,
                ensure_ascii=False,
                indent=4
            )
        )
        return []

    # 11-3. 같은 UUID의 이벤트가 대기 목록에 중복 등록되는 것 방지
    # 기존 이벤트 재전송 시에는 새 UUID를 생성하면 안 됨
    events = load_pending_events()
    event_id = event.get("event_id")

    if not event_id:
        raise ValueError("event_id가 필요합니다.")

    if any(
        item.get("event_id") == event_id
        for item in events
    ):
        print(
            f"[이미 대기 중인 이벤트] {event_id}"
        )
        return []

    # 11-4. 서버로 요청하기 전에 먼저 파일에 기록
    # 전송 도중 연결이 끊어져도 원본 이벤트를 복구할 수 있음
    events.append(event)
    save_pending_events(events)

    print(
        f"[이벤트 등록] {event_type}, "
        f"event_id={event_id}"
    )

    # 11-5. 저장된 이벤트를 실제 API로 전송
    return retry_pending_events()


# 12. 기존 주차면 이벤트 호출 코드와의 호환성 유지

# parking_realtime.py 등에서 호출하던 함수명을 변경하지 않도록 주차면 전용 함수가 공통 이벤트 등록 함수를 호출
def queue_occupancy_event(event):
    return queue_ai_event(event)

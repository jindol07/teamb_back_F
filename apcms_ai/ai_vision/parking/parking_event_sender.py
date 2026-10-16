# APCMS 주차면 점유 감지 이벤트 전송 기능
# AI가 확정한 주차면 상태를 Spring Boot REST API로 전달

# 1. 주차면 ID와 상태를 백엔드 규격으로 변환
# 2. 새로운 상태 확정 이벤트마다 UUID 생성
# 3. 타임존 정보가 포함된 감지 시각 생성
# 4. HTTP POST 방식으로 JSON 전송
# 5. 전송 실패 이벤트를 파일에 보관
# 6. 동일 UUID를 유지하여 실패 이벤트 재전송
# 7. 409 Conflict 이벤트는 별도 파일에 보관 (백엔드와 맞추기 위해 추가)

import json
import os
import uuid
import requests

from datetime import datetime

from ai_vision.paths import BASE_DIR, RESULT_DIR


# 1. .env 및 Spring Boot 연동 설정

# 1-1. .env 파일에서 환경변수 불러오기
# python-dotenv가 설치되어 있다면 apcms_ai/.env 파일의 설정을 읽어올 수 있음
# 단, 환경변수는 import 이전에 설정되어 있어야 하므로 이 파일 안에서 먼저 load_dotenv()를 실행
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent / ".env")

except ImportError:
    # python-dotenv가 설치되지 않은 경우 운영체제 환경변수만 사용
    # 현재 독립 테스트는 이 경우에도 실행 가능
    pass


# 1-2. Spring Boot 주차면 이벤트 수신 API

# 환경변수가 있으면 해당 값을 우선 사용, 없으면 테스트 주소 사용
API_URL = os.getenv(
    "PARKING_AI_API_URL",
    "http://192.168.0.7:81/alpharking/admin/api/parking/ai/occupancy-events"
)

# 1-3. Spring Boot API 인증키

# 보안을 위해 실제 키는 코드에 기록하지 않음
# 백엔드 담당자가 공유한 키를 .env 등에 설정
API_KEY = os.getenv("PARKING_AI_API_KEY", "")

# 1-4. 실제 POST 전송 활성화 여부

# false: JSON 생성 및 콘솔 출력만 수행
# true: Spring Boot로 실제 POST 요청
# 실제 전송 테스트를 진행할 때만 true로 설정
SEND_ENABLED = (
    os.getenv(
        "PARKING_AI_SEND_ENABLED",
        "false"
    ).lower() == "true"
)

# 1-5. 실제 전송에 실패한 이벤트 저장 파일
PENDING_PATH = RESULT_DIR / "parking" / "pending_events.json"

# 1-6. 테스트용 주차구획 ID와 DB 구획 코드 매핑

# AI 내부: A-01
# Spring Boot: 1F-A01
SPACE_CODE_MAP = {
    "A-01": "1F-A01",
    "A-02": "1F-A02",
    "A-03": "1F-A03",
    "A-04": "1F-A04"
}

# 1-7. 409 Conflict로 거부된 이벤트 보관 파일 (추가)
REJECTED_PATH = RESULT_DIR / "parking" / "rejected_events.json"


# 2. create_occupancy_event() - 점유 이벤트 JSON 생성

def create_occupancy_event(space_id, status, change_ratio):

    # 2-1. 주차면 식별자 변환

    # 매핑되지 않은 ID를 그대로 전송하면 Spring Boot에서 잘못된 구획으로 처리할 수 있으므로 오류 발생
    if space_id not in SPACE_CODE_MAP:
        raise ValueError(f"등록되지 않은 주차구획 ID입니다: {space_id}")

    space_code = SPACE_CODE_MAP[space_id]

    # 2-2. 점유 상태를 백엔드 규격으로 변환

    # AI 내부 상태:
    # OCCUPIED / EMPTY
    # Spring Boot 상태:
    # OCCUPIED / AVAILABLE
    if status == "OCCUPIED":
        api_status = "OCCUPIED"

    elif status == "EMPTY":
        api_status = "AVAILABLE"

    else:
        raise ValueError(f"알 수 없는 점유 상태입니다: {status}")

    # 2-3. 이벤트 UUID 생성

    # uuid4(): 새 이벤트를 식별하기 위한 UUID 생성
    # 같은 상태가 반복 감지되는 동안에는 새로운 이벤트를 만들지 않는 것이 중요
    event_id = str(uuid.uuid4())

    # 2-4. 감지 시각 생성

    detected_at = (
        datetime.now()  # 현재 시각
        .astimezone()  # 로컬 타임존 오프셋 추가
        .isoformat(timespec="seconds")  # ISO 8601 문자열로 변환
        # 예: 2026-10-15T12:05:00+09:00
    )

    # 2-5. Spring Boot API 명세에 맞춰 딕셔너리 작성

    # change_ratio:
    # 빈 주차면 기준 이미지 대비 변화한 픽셀의 비율
    # !차량이 존재할 확률이나 YOLO 신뢰도가 아님!
    event = {
        "event_id": event_id,
        "event_type": "PARKING_OCCUPANCY",
        "detected_at": detected_at,
        "space_code": space_code,
        "status": api_status,
        "change_ratio": round(float(change_ratio), 4),
        "source": "AI"
    }

    return event


# 3. load_pending_events() - 전송 대기 이벤트 읽기

def load_pending_events():

    # 3-1. 대기 파일이 없으면 빈 리스트 반환
    if not PENDING_PATH.is_file():
        return []

    # 3-2. JSON 파일 읽기
    with open(PENDING_PATH, "r", encoding="utf-8") as file:
        events = json.load(file)

    # 3-3. 이벤트 목록이 리스트인지 확인
    if not isinstance(events, list):
        raise ValueError("미전송 이벤트 JSON 형식이 올바르지 않습니다.")

    return events


# 4. save_pending_events() - 전송 대기 이벤트 저장

def save_pending_events(events):

    # 4-1. 저장 폴더 생성
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 4-2. 기존 파일을 직접 덮어쓰지 않고 임시 파일에 먼저 JSON 데이터를 기록
    temp_path = PENDING_PATH.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(
            events,
            file,
            ensure_ascii=False,  # 한글 그대로 저장
            indent=4  # 들여쓰기 4
        )

    # 4-3. 임시 파일로 실제 파일 교체
    # 기존 JSON 파일이 있으면 교체됨
    os.replace(temp_path, PENDING_PATH)


# 5. save_rejected_event() - 거부된 이벤트 보관 (추가)

def save_rejected_event(event, response):

    # 5-1. 기존 거부 이벤트 목록 읽기
    if REJECTED_PATH.is_file():
        with open(REJECTED_PATH, "r", encoding="utf-8") as file:
            rejected_events = json.load(file)

        if not isinstance(rejected_events, list):
            raise ValueError("거부 이벤트 JSON 형식이 올바르지 않습니다.")

    else:
        rejected_events = []

    # 5-2. 거부된 원본 이벤트와 HTTP 응답 기록
    rejected_events.append({
        "event": event,
        "http_status": response.status_code,
        "response_body": response.text,
        "rejected_at": datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
    })

    # 5-3. 임시 파일에 먼저 저장
    REJECTED_PATH.parent.mkdir(parents=True, exist_ok=True)

    temp_path = REJECTED_PATH.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(
            rejected_events,
            file,
            ensure_ascii=False,
            indent=4
        )

    # 5-4. 저장이 끝나면 실제 파일로 교체
    os.replace(temp_path, REJECTED_PATH)


# 6. retry_pending_events() - 전송 실패 이벤트 재시도

def retry_pending_events():

    # 6-1. 테스트 모드라면 전송하지 않음
    if not SEND_ENABLED:
        return

    # 6-2. 저장된 미전송 이벤트 가져오기
    events = load_pending_events()

    if not events:
        return

    # 6-3. 인증키 설정 여부 확인
    # API 키가 없으면 이벤트를 삭제하지 않고 대기
    if not API_KEY:
        print("[전송 대기]\nPARKING_AI_API_KEY가 설정되지 않았습니다.")
        return

    # 6-4. 가장 오래된 이벤트부터 전송

    # while문을 사용하여 성공한 이벤트만 삭제하고 실패한 이벤트는 남겨둠
    while events:

        event = events[0]

        # 6-5. HTTP 요청 헤더 구성
        headers = {
            "Content-Type": "application/json",
            "X-AI-API-Key": API_KEY
        }

        try:
            # 6-6. Spring Boot API로 POST 요청
            response = requests.post(
                API_URL,
                headers=headers,
                json=event,  # json=event : 딕셔너리를 JSON 형식으로 전송
                timeout=3  # timeout : 서버가 응답하지 않을 경우 무한 대기 방지
            )

            # 6-7. 과거 이벤트 409 Conflict 처리 (추가)

            # 백엔드에서 409로 거부한 이벤트는 반복 전송하지 않고 별도 파일에 보관
            if response.status_code == 409:

                # 거부 이력을 먼저 보관
                # 저장에 실패하면 원본 대기 이벤트는 유지됨
                save_rejected_event(event, response)

                print(
                    f'[이벤트 거부 - 409 Conflict]\n'
                    f'{event["space_code"]} : {event["status"]}\n'
                    f'event_id={event["event_id"]}'
                )

                # 거부 이력 저장 성공 후 대기 목록에서 제거
                events.pop(0)
                save_pending_events(events)

                # 다음 대기 이벤트 처리
                continue

            # 6-8. HTTP 오류 상태 코드 검사

            # 2xx: 일반적으로 성공
            # 4xx/5xx: 예외 발생
            response.raise_for_status()

            # 백엔드 처리 결과 출력 (추가)
            try:
                response_data = response.json()
                outcome = response_data.get("outcome", "UNKNOWN")
            except (ValueError, AttributeError):
                outcome = "UNKNOWN"

            print(
                f'[전송 성공]\n'
                f'{event["space_code"]} : {event["status"]}\n'
                f'event_id={event["event_id"]}\n'
                f'outcome={outcome}'
            )

        except requests.RequestException as error:

            # 6-9. 전송 실패 시 원래 이벤트를 그대로 보관

            # 이때 새로운 UUID를 생성하면 안 됨
            # 같은 event_id와 detected_at으로 재시도해야 백엔드가 중복 이벤트를 구분할 수 있음
            print(f"[전송 실패]\nerror : {error}")
            print(f'[재전송 대기]\nevent_id={event["event_id"]}')

            # 다음 재시도 시점까지 대기
            return

        # 6-10. 성공한 이벤트만 대기 목록에서 제거
        events.pop(0)

        # 6-11. 변경된 대기 목록을 파일에 저장
        save_pending_events(events)


# 7. queue_occupancy_event() - 새 이벤트 등록 및 전송

def queue_occupancy_event(event):

    # 7-1. 테스트 모드

    # 실제 Spring Boot API에는 요청하지 않음
    # JSON이 명세에 맞는지만 콘솔에 출력
    if not SEND_ENABLED:

        print("\n[API 전송 테스트 모드]")
        print(json.dumps(event, ensure_ascii=False, indent=4))

        return

    # 7-2. 실제 전송 전에 이벤트 파일 보관

    # 서버 연결 실패 시 이벤트를 복구할 수 있도록 POST 요청보다 파일 저장을 먼저 수행
    events = load_pending_events()
    events.append(event)
    save_pending_events(events)

    print(
        f'\n[이벤트 등록]\n'
        f'{event["space_code"]} : {event["status"]}, '
        f'event_id={event["event_id"]}'
    )

    # 7-3. 전송 대기 이벤트 전송 시도
    retry_pending_events()

# Spring Boot 주차면 점유 이벤트 통합 테스트

# 1. OCCUPIED 이벤트 신규 전송
# 2. 동일 UUID 이벤트 재전송
# 3. AVAILABLE 이벤트 신규 전송

# 실제 Spring Boot DB 및 React 주차현황에 반영되는 요청이므로 백엔드 담당자와 테스트 시간을 맞춰 실행할 것

import argparse
import json
import uuid
import requests

from datetime import datetime
from getpass import getpass

from ai_vision.paths import RESULT_DIR


# 2. Spring Boot API 및 테스트 설정

# 2-1. 주차면 점유 이벤트 수신 URL
API_URL = (
    "http://192.168.0.7:81"
    "/alpharking/admin/api/parking/ai/occupancy-events"
)

# 2-2. 이번 통합 테스트에서 사용할 주차면
SPACE_CODE = "1F-A01"

# 2-3. 마지막 전송 이벤트 저장 경로
# 동일 UUID 재전송을 위한 테스트용 파일
EVENT_PATH = (
    RESULT_DIR / "parking" / "integration_test_last_event.json"
)


# 3. create_test_event() - 새로운 이벤트 생성
def create_test_event(status):
    """
    새로운 UUID와 현재 감지 시각을 가진 점유 이벤트 생성.

    status:
        OCCUPIED  - 점유
        AVAILABLE - 공차
    """

    # 3-1. 감지 시각 생성
    # 현재 컴퓨터의 로컬 타임존을 포함
    detected_at = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    # 3-2. 백엔드와 합의한 JSON 형식
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "PARKING_OCCUPANCY",
        "detected_at": detected_at,
        "space_code": SPACE_CODE,
        "status": status,
        "change_ratio": 0.8 if status == "OCCUPIED" else 0.0,
        "source": "AI"
    }

    return event


# 4. save_event() - 동일 UUID 재전송용 이벤트 저장
def save_event(event):

    # 4-1. 결과 폴더 생성
    EVENT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # 4-2. 이벤트 JSON 저장
    with open(EVENT_PATH, "w", encoding="utf-8") as file:
        json.dump(
            event,
            file,
            ensure_ascii=False,
            indent=4
        )


# 5. load_event() - 기존 이벤트 불러오기
def load_event():

    # 5-1. 저장된 이벤트 존재 여부 검사
    if not EVENT_PATH.is_file():
        raise FileNotFoundError(
            f"이전 이벤트 파일이 없습니다: {EVENT_PATH}"
        )

    # 5-2. 기존 UUID와 감지 시각 그대로 불러오기
    with open(EVENT_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


# 6. send_event() - Spring Boot HTTP POST 요청
def send_event(event):

    # 6-1. API 키 입력
    # 입력한 키는 터미널 화면에 표시되지 않음
    api_key = getpass("X-AI-API-Key 입력: ")

    if not api_key.strip():
        print("API 키가 입력되지 않았습니다.")
        return

    # 6-2. 요청 헤더 설정
    headers = {
        "Content-Type": "application/json",
        "X-AI-API-Key": api_key
    }

    # 6-3. 전송 이벤트 확인
    # API 키는 출력하지 않음
    print("\n=== 요청 JSON ===")
    print(json.dumps(event, ensure_ascii=False, indent=4))

    try:
        # 6-4. HTTP POST 전송
        response = requests.post(
            API_URL,
            json=event,
            headers=headers,
            timeout=10
        )

        # 6-5. HTTP 상태 코드 출력
        print("\n=== HTTP 응답 ===")
        print("HTTP 상태 코드:", response.status_code)

        # 6-6. 서버 응답 JSON 출력
        try:
            response_data = response.json()
            print(
                json.dumps(
                    response_data,
                    ensure_ascii=False,
                    indent=4
                )
            )

        except ValueError:
            # 응답이 JSON이 아닌 경우 원본 텍스트 출력
            print(response.text)

    except requests.RequestException as error:
        print("\n[전송 실패]")
        print(type(error).__name__)
        print(str(error))
        print("이벤트는 로컬 JSON에 보관되어 있습니다.")


# 7. main() - 테스트 실행
def main():

    # 7-1. 실행 옵션 설정
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--status",
        choices=["OCCUPIED", "AVAILABLE"],
        default="OCCUPIED",
        help="새 이벤트 상태"
    )

    parser.add_argument(
        "--duplicate",
        action="store_true",
        help="마지막 이벤트를 동일 UUID로 재전송"
    )

    args = parser.parse_args()

    # 7-2. 기존 이벤트 재전송
    if args.duplicate:
        event = load_event()
        print("[테스트] 동일 UUID 재전송")

    else:
        # 7-3. 새로운 이벤트 생성
        event = create_test_event(args.status)

        # 전송 실패 시에도 같은 UUID를 사용할 수 있도록
        # POST 전에 이벤트를 로컬 파일에 저장
        save_event(event)

        print("[테스트] 새로운 이벤트 전송")

    # 7-4. 실제 HTTP POST
    send_event(event)


# 8. 프로그램 실행부
if __name__ == "__main__":
    main()

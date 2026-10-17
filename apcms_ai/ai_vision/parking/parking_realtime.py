# APCMS 실시간 주차면 점유 감지
# 빈 주차면 기준 사진과 실시간 웹캠 영상을 비교하여
# 주차면별 점유 상태를 독립적으로 판단하는 프로그램

# 1. 기준 이미지 및 주차면 좌표 불러오기
# 2. 주차면별 분석 마스크 생성
# 3. 웹캠에서 현재 프레임 읽기
# 4. 기준 이미지와 현재 이미지의 픽셀 차이 분석
# 5. 같은 상태가 5회 연속 감지되면 확정
# 6. 최초 확정 또는 상태 변경 시 Spring Boot 이벤트 생성
# 7. 모든 주차면 상태가 확정되면 결과 이미지와 JSON 저장
# 8. 실제 전송 모드에서는 실패 이벤트 재전송

# 자동차를 직접 인식하는 YOLO 방식이 아니라 기준 이미지 대비 픽셀 변화율로 점유 상태를 판단함

import json
import time
import cv2
import numpy as np

from ai_vision.paths import DATA_DIR, RESULT_DIR

from ai_vision.parking.parking_event_sender import (
    create_occupancy_event,
    queue_occupancy_event,
    retry_pending_events
)


# 1. 경로 및 설정값

# 1-1. 빈 주차면 기준 사진
REFERENCE_PATH = DATA_DIR / "parking_spaces" / "empty_reference.jpg"

# 1-2. 주차면 ID 및 다각형 좌표가 저장된 JSON
JSON_PATH = DATA_DIR / "parking_spaces" / "parking_spots.json"

# 1-3. 결과 이미지와 JSON을 저장할 폴더
SAVE_DIR = RESULT_DIR / "parking"

IMAGE_PATH = SAVE_DIR / "realtime_occupancy_result.jpg" # 결과 이미지
OUTPUT_PATH = SAVE_DIR / "realtime_occupancy_result.json" # JSON

# 1-4. 픽셀 변화 감지 임계값
# 기준 이미지와 현재 이미지 사이의 픽셀 밝기 차이가 35보다 크면 변화가 발생한 픽셀로 인정
PIXEL_THRESHOLD = 35

# 1-5. 주차면 점유 판단 임계값
# 주차면 내부 픽셀 중 5% 이상이 변하면 OCCUPIED
OCCUPANCY_THRESHOLD = 0.05

# 1-6. 웹캠 분석 간격
# 0.5초마다 주차면 점유 상태 분석
CHECK_INTERVAL = 0.5

# 1-7. 상태 확정에 필요한 연속 판정 횟수
# 같은 상태가 연속 5회 감지되어야 확정
STABLE_FRAMES = 5

# 1-8. Spring Boot 전송 실패 이벤트 재시도 간격
# 실제 전송 모드에서만 의미가 있음
RETRY_INTERVAL = 5.0


# 2. detect_spaces() - 현재 프레임의 점유 상태 분석

def detect_spaces(reference_gray, frame, spaces):

    # 2-1. 현재 웹캠 프레임 전처리

    # BGR 컬러 이미지를 흑백 이미지로 변환
    current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # GaussianBlur() : 주변 픽셀을 부드럽게 만들어 작은 노이즈 감소
    current_gray = cv2.GaussianBlur(
        current_gray,
        (5, 5),
        0
    )

    # 2-2. 기준 이미지와 현재 이미지 비교

    # absdiff() : 두 이미지의 같은 위치에 있는 픽셀값 차이 계산
    difference = cv2.absdiff(
        reference_gray,
        current_gray
    )

    # threshold() : 밝기 차이가 PIXEL_THRESHOLD보다 크면 255, 그렇지 않으면 0으로 변환
    # 예 : 기준 픽셀 = 200, 현재 픽셀 = 150 일 때 차이 : 50 -> 변화한 픽셀로 판단
    _, changed = cv2.threshold(
        difference,
        PIXEL_THRESHOLD,
        255,
        cv2.THRESH_BINARY
    )

    # 2-3. 주차면별 변화율 계산

    results = []

    for space in spaces:

        # 해당 주차면 내부만 흰색으로 표시한 마스크
        mask = space["mask"]

        # bitwise_and() : 전체 이미지 중 해당 주차면의 변화만 추출
        changed_in_space = cv2.bitwise_and(
            changed,
            changed,
            mask=mask
        )

        # 주차면 전체 픽셀 개수
        total_pixels = cv2.countNonZero(mask)

        # 실제 변화한 픽셀 개수
        changed_pixels = cv2.countNonZero(
            changed_in_space
        )

        # 주차면 마스크가 비어 있다면 계산할 수 없음
        if total_pixels == 0:
            raise ValueError(
                f'{space["id"]}: 주차면 마스크가 비어 있습니다.'
            )

        # 2-4. 주차면 내부의 픽셀 변화율 계산
        # ex) 10,000픽셀 중 600픽셀이 변경됐다면
        # change_ratio = 600 / 10000 = 0.06 (6%)
        change_ratio = changed_pixels / total_pixels

        # 2-5. 현재 순간의 점유 상태 판정

        if change_ratio >= OCCUPANCY_THRESHOLD:
            status = "OCCUPIED"
        else:
            status = "EMPTY"

        # 분석한 주차면의 결과를 리스트에 추가
        results.append({
            "space_id": space["id"],
            "status": status,
            "change_ratio": round(change_ratio, 4)
        })

    # 이 결과는 아직 확정된 상태가 아니라 현재 프레임 한 장에서 판단한 임시 상태임
    return results


# 3. save_results() - 확정된 점유 상태 저장

def save_results(frame, spaces, results):

    # 3-1. 결과 저장 폴더 생성

    SAVE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # 3-2. 결과 이미지 생성

    # copy() : 원본 웹캠 프레임을 변경하지 않고 복사
    annotated = frame.copy()

    # zip() : spaces와 results의 같은 위치 요소를 함께 처리
    for space, result in zip(spaces, results):

        # 점유 중이면 빨간색, 비어 있으면 초록색 (BGR)
        if result["status"] == "OCCUPIED":
            color = (0, 0, 255) # 빨간색
        else:
            color = (0, 255, 0) # 초록색

        # 주차면 다각형 좌표
        points = space["points"]

        # polylines() : 주차면 테두리를 결과 이미지에 표시
        cv2.polylines(
            annotated,
            [points],
            True,
            color,
            2
        )

        # 첫 번째 좌표를 텍스트 표시 기준으로 사용
        x, y = points[0]

        # putText() : 주차면 ID와 확정된 상태를 이미지에 표시
        cv2.putText(
            annotated,
            f'{space["id"]}: {result["status"]}',
            (int(x), max(int(y) - 10, 15)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1
        )

    # 3-3. 전체 주차면 현황 계산

    # OCCUPIED 상태인 주차면의 개수
    occupied_count = sum(1 for result in results if result["status"] == "OCCUPIED")

    # 기존 JSON 응답 구조를 그대로 유지
    # parking_api.py에서 이 데이터를 조회함
    output = {
        "total_spaces": len(results),
        "occupied_count": occupied_count,
        "empty_count": len(results) - occupied_count,
        "spaces": results
    }

    # 3-4. 결과 이미지 저장

    saved = cv2.imwrite(
        str(IMAGE_PATH),
        annotated
    )

    if saved:
        print("결과 이미지 저장 성공")
    else:
        print("결과 이미지 저장 실패")

    # 3-5. 결과 JSON 파일 저장

    # with open() : 파일 사용이 끝나면 자동으로 닫음
    # "w": 쓰기 모드이므로 기존 파일을 덮어씀
    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            ensure_ascii=False, # ensure_ascii=False: 한글 그대로 저장
            indent=4 # 들여쓰기 4
        )

    print("결과 JSON 저장 완료")


# 4. run_realtime() - 웹캠 실시간 감지 실행

def run_realtime():

    # 4-1. 빈 주차면 기준 이미지 읽기

    # cv2.imread() : 이미지 파일을 NumPy 배열로 읽음
    reference = cv2.imread(REFERENCE_PATH)
    
    if reference is None:
        print("빈 주차면 기준 이미지를 읽을 수 없습니다.")
        return

    # 4-2. 주차면 좌표 JSON 불러오기

    if not JSON_PATH.is_file():
        print(f"주차면 좌표 파일이 없습니다 : {JSON_PATH}")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    # 기준 이미지의 높이, 너비
    height, width = reference.shape[:2]

    # 주차면 좌표가 작성된 이미지 해상도와 실제 기준 이미지 해상도가 일치하는지 확인
    if (data["image_width"] != width or data["image_height"] != height):
        print("기준 이미지와 JSON 좌표의 해상도가 다릅니다.")
        return

    # 4-3. 등록된 주차면이 있는지 확인

    # 주차면이 0개라면 감지할 영역이 없으므로 종료
    # 빈 리스트에서 all()을 사용할 때 생기는 잘못된 상태 확정을 방지하는 목적도 있음
    if not data["spaces"]:
        print("등록된 주차면이 없습니다.")
        print("parking_spots.json의 spaces를 확인하세요.")
        return

    # 4-4. 각 주차면의 분석 마스크 생성

    spaces = []

    # 주차면 테두리 부분의 오차를 줄일 축소 커널
    kernel = np.ones((7, 7), dtype=np.uint8)

    for item in data["spaces"]:

        # 주차면의 ID와 다각형 꼭짓점
        space_id = item["id"]

        # JSON에 저장된 좌표 리스트를 정수 배열로 변환
        points = np.array(item["points"], dtype=np.int32)

        # zeros() : 기준 이미지와 같은 크기의 검은색 마스크 생성
        mask = np.zeros((height, width), dtype=np.uint8)

        # fillPoly() : 주차면 다각형 내부를 흰색으로 채움
        cv2.fillPoly(mask, [points], 255)

        # erode() : 테두리 부근을 분석에서 제외하기 위해 흰색 영역을 조금 축소
        mask = cv2.erode(mask, kernel)

        # 축소 후에도 분석할 영역이 남아 있는지 확인
        if cv2.countNonZero(mask) == 0:
            print(f"{space_id} : 주차면 영역 오류")
            return

        # 주차면별 ID, 좌표, 마스크 저장
        spaces.append({
            "id": space_id,
            "points": points,
            "mask": mask
        })

    # 4-5. 기준 이미지 전처리

    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    reference_gray = cv2.GaussianBlur(reference_gray, (5, 5), 0)

    # 4-6. 웹캠 연결

    # 0: 기본 웹캠
    # CAP_DSHOW: Windows의 DirectShow 백엔드
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("웹캠을 연결할 수 없습니다.")
        return

    try:
        # 4-7. 웹캠 초기 안정화

        # 웹캠 연결 직후에는 자동 노출 및 밝기 조절이 진행될 수 있어 처음 30프레임을 읽고 지나감
        for _ in range(30):
            ret, frame = cap.read()

            if not ret:
                print("웹캠 초기 촬영에 실패했습니다.")
                return

        print("실시간 점유 감지를 시작합니다. 종료 : Ctrl+C")

        # 4-8. 주차면별 상태 관리 딕셔너리 생성

        states = {}

        for space in spaces:

            states[space["id"]] = {
                "previous": None, # 직전 프레임에서 판단한 임시 상태
                "same_count": 0, # 동일 임시 상태가 연속 등장한 횟수
                "confirmed": None, # 5회 연속 판정 후 확정한 상태
                "change_ratio": 0.0 # 확정 시점의 픽셀 변화율
            }

        # 4-9. 분석 및 재시도 시간 초기화

        # time.monotonic() : 단조 시계, 시스템 시계가 바뀌어도 경과 시간 측정에 적합
        last_check = 0.0
        last_retry = time.monotonic()

        # 4-10. 웹캠 프레임 반복 읽기

        while True:

            ret, frame = cap.read()

            if not ret:
                print("웹캠 프레임을 읽지 못했습니다.")
                break

            # 기준 이미지와 웹캠 해상도가 달라지면 같은 위치의 픽셀을 비교할 수 없으므로 종료
            if frame.shape != reference.shape:
                print("웹캠 이미지와 기준 이미지의 크기가 다릅니다.")
                break

            # 4-11. 분석 간격 확인

            now = time.monotonic()

            # 아직 0.5초가 지나지 않았다면 현재 프레임은 분석하지 않고 다음 프레임 읽기
            if now - last_check < CHECK_INTERVAL:
                continue

            last_check = now

            # 4-12. 현재 프레임 점유 상태 분석

            # 결과는 아직 확정되지 않은 임시 상태
            results = detect_spaces(reference_gray, frame, spaces)

            # 이번 분석에서 확정 상태 변경이 있었는지 확인
            state_changed = False

            # 4-13. 주차면별 연속 판정

            for result in results:

                space_id = result["space_id"]
                status = result["status"]

                # 해당 주차면의 상태 관리 정보
                state = states[space_id]

                # 직전 임시 상태와 같다면 횟수 증가
                if status == state["previous"]:
                    state["same_count"] += 1

                # 상태가 다르면 새로운 연속 판정 시작
                else:
                    state["previous"] = status
                    state["same_count"] = 1

                # 4-14. 동일 상태 5회 연속 확인

                if state["same_count"] < STABLE_FRAMES:
                    continue

                # 이미 확정한 상태와 같다면 새로운 이벤트를 만들지 않음
                if status == state["confirmed"]:
                    continue

                # 4-15. 최초 상태 확정 또는 상태 변경

                old_status = state["confirmed"]

                state["confirmed"] = status
                state["change_ratio"] = result["change_ratio"]

                state_changed = True

                if old_status is None:
                    print(
                        f"[초기 확정] {space_id} : {status}"
                        f"({result["change_ratio"]:.2%})"
                    )

                else:
                    print(
                        f"[상태 변경] {space_id}: "
                        f"{old_status} -> {status} "
                        f'({result["change_ratio"]:.2%})'
                    )

                # 4-16. Spring Boot 전송용 이벤트 생성

                # parking_event_sender.py 의 create_occupancy_event() 함수
                # 같은 확정 상태가 반복되는 동안에는 이 코드가 다시 실행되지 않음
                event = create_occupancy_event(
                    space_id, # AI의 A-01 같은 ID를 1F-A01 등으로 변환
                    status, # EMPTY는 AVAILABLE로 변환
                    result["change_ratio"] # 이벤트별 UUID와 감지 시각 생성
                )

                # 4-17. 생성된 이벤트 등록

                # parking_event_sender.py 의 queue_occupancy_event() 함수
                # 기본 테스트 모드 : JSON만 콘솔에 출력하며 외부 전송하지 않음
                # 실제 전송 모드 : 대기 파일에 저장하고 POST 시도
                queue_occupancy_event(event)

            # 4-18. 모든 주차면 상태가 확정됐는지 확인

            # all() : 모든 주차면의 confirmed가 None이 아니면 True
            all_confirmed = all(state["confirmed"] is not None for state in states.values())

            # 4-19. 결과 이미지 및 JSON 갱신

            # 모든 주차면의 최초 확정이 완료됐고 이번 분석에서 상태 변경이 발생했을 때만 저장
            # 주차면별 API 이벤트 생성은 위에서 이미 수행
            if all_confirmed and state_changed:

                confirmed_results = []

                for space in spaces:

                    space_id = space["id"]
                    state = states[space_id]

                    confirmed_results.append({
                        "space_id": space_id,
                        "status": state["confirmed"],
                        "change_ratio": state["change_ratio"]
                    })

                save_results(frame, spaces, confirmed_results)

            # 4-20. 전송 실패 이벤트 재시도

            # 현재 점유 상태가 변경되지 않더라도 RETRY_INTERVAL마다 대기 이벤트 전송 시도
            # 테스트 모드에서는 함수가 바로 종료되어 실제 HTTP 요청이 발생하지 않음
            if now - last_retry >= RETRY_INTERVAL:
                retry_pending_events()
                last_retry = time.monotonic()

    # 4-21. 사용자가 Ctrl+C로 종료한 경우
    except KeyboardInterrupt:

        print("\n실시간 점유 감지를 종료합니다.")
        print(f"결과 이미지 경로: {IMAGE_PATH}")
        print(f"결과 JSON 경로: {OUTPUT_PATH}")

    # 4-22. 프로그램 종료 시 웹캠 해제
    finally:
        # release() : 카메라 장치를 해제하여 다른 프로그램에서도 웹캠을 사용할 수 있도록 함
        cap.release()


# 5. 프로그램 실행부

# python -m ai_vision.parking.parking_realtime
if __name__ == "__main__":
    run_realtime()

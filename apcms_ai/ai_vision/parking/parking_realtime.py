
# OpenCV를 이용해 빈 주차장 기준 사진과 실시간 웹캠 영상을 비교하여
# 주차면별 점유 상태를 독립적으로 판단하는 프로그램
#
# 1. 기준 이미지와 주차면 좌표 불러오기
# 2. 주차면별 마스크 생성
# 3. 실시간 웹캠 프레임 분석
# 4. 주차면마다 같은 판정이 5회 연속 나오면 상태 확정
# 5. 확정된 상태가 바뀌면 결과 이미지와 JSON 갱신
#
# 자동차 자체를 인식하는 것이 아니라 이미지의 변화를 감지하는 방식

import json
import os
import sys
import time
import cv2
import numpy as np

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paths import DATA_DIR, RESULT_DIR


# 1. 경로 및 설정값

# 1-1. 파일 경로
SAVE_DIR = RESULT_DIR / "parking"
REFERENCE_PATH = DATA_DIR / "parking_spaces" / "empty_reference.jpg"
JSON_PATH = DATA_DIR / "parking_spaces" / "parking_spots.json"

# 1-2. 점유 감지 임계값
PIXEL_THRESHOLD = 35  # 픽셀 밝기 차이 기준
OCCUPANCY_THRESHOLD = 0.05  # 주차면 변화율 5%

# 1-3. 실시간 분석 설정값
CHECK_INTERVAL = 0.5  # 분석 간격(초)
STABLE_FRAMES = 5  # 상태 확정에 필요한 연속 판정 횟수

# 1-4. 저장할 이미지 / JSON 경로
image_path = SAVE_DIR / "realtime_occupancy_result.jpg"
output_path = SAVE_DIR / "realtime_occupancy_result.json"


# 2. detect_spaces() - 현재 프레임의 주차면 점유 분석
def detect_spaces(reference_gray, frame, spaces):

    # 2-1. 현재 프레임 전처리
    current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    current_gray = cv2.GaussianBlur(current_gray, (5, 5), 0)

    # 2-2. 기준 이미지와 현재 프레임 비교
    difference = cv2.absdiff(reference_gray, current_gray)

    # 픽셀 밝기 차이가 35를 초과하면 255(흰색), 아니면 0(검은색)
    # 예) 기준 200, 현재 150 → 차이 50 → 변화한 픽셀로 인정
    _, changed = cv2.threshold(
        difference, PIXEL_THRESHOLD, 255, cv2.THRESH_BINARY
    )

    # 2-3. 주차면별 변화율 계산
    results = []

    for space in spaces:
        mask = space["mask"]

        # 해당 주차면 내부의 변화만 추출
        changed_in_space = cv2.bitwise_and(
            changed, changed, mask=mask
        )

        total_pixels = cv2.countNonZero(mask)
        changed_pixels = cv2.countNonZero(changed_in_space)
        change_ratio = changed_pixels / total_pixels

        # 2-4. 점유 상태 판정
        # 예) 10,000픽셀 중 600픽셀 변화 → 6% → OCCUPIED
        if change_ratio >= OCCUPANCY_THRESHOLD:
            status = "OCCUPIED"
        else:
            status = "EMPTY"

        results.append({
            "space_id": space["id"],
            "status": status,
            "change_ratio": round(change_ratio, 4)
        })

    return results


# 3. save_results() - 확정된 점유 상태 저장
def save_results(frame, spaces, results):

    # 3-1. 결과 이미지에 주차면 표시
    os.makedirs(SAVE_DIR, exist_ok=True)
    annotated = frame.copy()

    # zip() : 두 리스트의 같은 순서에 있는 요소를 함께 가져옴
    for space, result in zip(spaces, results):

        if result["status"] == "OCCUPIED":
            color = (0, 0, 255)  # 빨간색
        else:
            color = (0, 255, 0)  # 초록색

        points = space["points"]

        cv2.polylines(annotated, [points], True, color, 2)

        x, y = points[0]

        cv2.putText(
            annotated,
            f'{space["id"]}: {result["status"]}',
            (int(x), max(int(y) - 10, 15)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1
        )

    # 3-2. 전체 주차면 현황 계산
    occupied_count = sum(
        1 for result in results
        if result["status"] == "OCCUPIED"
    )

    output = {
        "total_spaces": len(results),
        "occupied_count": occupied_count,
        "empty_count": len(results) - occupied_count,
        "spaces": results
    }

    # 3-3. 이미지와 JSON 저장

    if cv2.imwrite(str(image_path), annotated):
        print("결과 이미지 저장 성공")
    else:
        print("결과 이미지 저장 실패")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print("결과 JSON 저장 완료")


# 4. run_realtime() - 실시간 감지 실행
def run_realtime():

    # 4-1. 기준 이미지 읽기
    reference = cv2.imread(str(REFERENCE_PATH))

    if reference is None:
        print("빈 주차면 기준 이미지를 읽을 수 없습니다.")
        return

    # 4-2. 주차면 좌표 가져오기
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    height, width = reference.shape[:2]

    if data["image_width"] != width or data["image_height"] != height:
        print("기준 이미지와 JSON 좌표의 해상도가 다릅니다.")
        return

    # 4-3. 주차면별 마스크 생성
    spaces = []

    for item in data["spaces"]:
        space_id = item["id"]
        points = np.array(item["points"], dtype=np.int32)

        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(mask, [points], 255)

        # 주차면의 테두리 부근을 분석에서 제외하기 위해 영역 축소
        kernel = np.ones((7, 7), dtype=np.uint8)
        mask = cv2.erode(mask, kernel)

        if cv2.countNonZero(mask) == 0:
            print(f"{space_id}: 주차면 영역 오류")
            return

        spaces.append({
            "id": space_id,
            "points": points,
            "mask": mask
        })

    # 4-4. 기준 이미지 전처리
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    reference_gray = cv2.GaussianBlur(reference_gray, (5, 5), 0)

    # 4-5. 웹캠 연결
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("웹캠을 연결할 수 없습니다.")
        return

    try:
        # 웹캠이 안정화되도록 초기 30프레임 읽기
        for _ in range(30):
            ret, frame = cap.read()

            if not ret:
                print("웹캠 초기 촬영에 실패했습니다.")
                return

        print("실시간 점유 감지를 시작합니다. 종료: Ctrl+C")

        # 4-6. 주차면별 상태 관리 변수 초기화
        # 기존에는 previous, same_count, confirmed를 전체 주차면에
        # 공통으로 사용했지만 이제는 주차면마다 별도로 관리함
        states = {}

        for space in spaces:
            states[space["id"]] = {
                "previous": None,
                "same_count": 0,
                "confirmed": None,
                "change_ratio": 0.0
            }

        last_check = 0.0

        # 4-7. 웹캠 프레임 반복 읽기
        while True:
            ret, frame = cap.read()

            if not ret:
                print("웹캠 프레임을 읽지 못했습니다.")
                break

            if frame.shape != reference.shape:
                print("웹캠 이미지와 기준 이미지의 크기가 다릅니다.")
                break

            # 4-8. 일정 시간 간격으로만 분석
            now = time.monotonic()

            if now - last_check < CHECK_INTERVAL:
                continue

            last_check = now

            # 4-9. 현재 프레임의 점유 상태 분석
            results = detect_spaces(reference_gray, frame, spaces)

            # 이번 분석에서 확정된 상태 변경이 있는지 확인
            state_changed = False

            # 4-10. 주차면별 독립적인 연속 판정
            for result in results:
                space_id = result["space_id"]
                status = result["status"]

                # 해당 주차면의 상태 관리 딕셔너리 가져오기
                state = states[space_id]

                # 이전 판정과 같으면 연속 횟수 증가
                # 다르면 횟수를 1부터 다시 시작
                if status == state["previous"]:
                    state["same_count"] += 1
                else:
                    state["previous"] = status
                    state["same_count"] = 1

                # 4-11. 해당 주차면의 최종 상태 확정
                # 예) A-01이 5회 연속 OCCUPIED면 A-01만 확정
                if state["same_count"] < STABLE_FRAMES:
                    continue

                # 이미 확정한 상태와 같다면 변경할 필요 없음
                if status == state["confirmed"]:
                    continue

                old_status = state["confirmed"]

                state["confirmed"] = status
                state["change_ratio"] = result["change_ratio"]
                state_changed = True

                # 최초 확정과 이후 상태 변경 구분
                if old_status is None:
                    print(
                        f'[초기 확정] {space_id}: {status} '
                        f'({result["change_ratio"]:.2%})'
                    )
                else:
                    print(
                        f'[상태 변경] {space_id}: '
                        f'{old_status} → {status} '
                        f'({result["change_ratio"]:.2%})'
                    )

            # 4-12. 확정된 상태가 변경됐을 때 결과 저장

            # 모든 주차면의 최초 상태가 확정됐는지 확인
            all_confirmed = all(
                state["confirmed"] is not None
                for state in states.values()
            )

            if not all_confirmed or not state_changed:
                continue

            # 확정 상태를 이용해 전체 결과 생성
            # 아직 확정되지 않은 순간적인 판정은 포함하지 않음
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

    except KeyboardInterrupt: # 사용자가 직접 종료
        print("\n실시간 점유 감지를 종료합니다.")
        print(f"결과 이미지 경로 - {image_path}")
        print(f"결과 JSON 경로 - {output_path}")

    finally:
        cap.release()


# 5. 프로그램 실행부
if __name__ == "__main__":
    run_realtime()

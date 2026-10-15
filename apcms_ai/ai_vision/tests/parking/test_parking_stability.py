# 기준 이미지와 현재 웹캠 영상을 비교하여 주차면별 변화율을 측정
# 카메라 흔들림이나 그림자에 의한 오탐 가능성 확인

# 1. 기준 이미지와 주차면 좌표 불러오기
# 2. 주차면별 마스크 생성
# 3. 일정 시간 동안 웹캠 이미지 비교
# 4. 변화율을 CSV 파일로 저장
# 5. 평균, 최대 변화율 및 연속 점유 판정 횟수 분석

import csv
import json
import os
import sys
import time
import cv2
import numpy as np

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from paths import DATA_DIR, RESULT_DIR


# 1. 파일 경로 및 설정값

# 1-1. 파일 경로
REFERENCE_PATH = DATA_DIR / "parking_spaces" / "empty_reference.jpg"  # 빈 주차면 기준 이미지
JSON_PATH = DATA_DIR / "parking_spaces" / "parking_spots.json"  # 주차면 꼭짓점 좌표
SAVE_DIR = RESULT_DIR / "parking"  # 테스트 결과 저장 폴더
CSV_PATH = SAVE_DIR / "stability_result.csv"  # 시간별 변화율을 저장할 CSV 파일

# 1-2. 이미지 비교 임계값
PIXEL_THRESHOLD = 35  # 픽셀 하나의 밝기 차이를 변화로 인정하는 기준
OCCUPANCY_THRESHOLD = 0.05  # 주차면 내부의 변화율이 5% 이상이면 점유로 판단

# 1-3. 측정 시간 및 연속 판정 설정
TEST_DURATION = 60  # 전체 측정 시간(초)
CHECK_INTERVAL = 0.5  # 변화율을 계산할 시간 간격(초)
STABLE_FRAMES = 5  # 실시간 감지와 같은 연속 판정 기준

# 2. test_stability() - 빈 주차면의 변화율 측정
def test_stability():

    # 2-1. 기준 이미지 읽기 및 오류 확인

    # cv2.imread() : 이미지 파일을 읽어 NumPy 배열로 반환
    # 컬러 이미지의 shape는 (높이, 너비, 채널 개수) 형태
    reference = cv2.imread(REFERENCE_PATH)
    
    if reference is None:
        print("기준 이미지를 읽을 수 없습니다.")
        return


    # 2-2. JSON 파일에서 주차면 좌표 가져오기

    # parking_space_annotation.ipynb에서 저장한 주차면 좌표 읽기
    # json.load() : JSON 데이터를 Python 딕셔너리로 변환
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # 이미지의 shape에서 높이와 너비만 가져오기
    # 예) (480, 640, 3) → height=480, width=640
    height, width = reference.shape[:2]

    # JSON 좌표가 현재 기준 이미지와 같은 해상도에서 작성됐는지 확인
    # 단, 크기가 같아도 카메라 위치와 촬영 구도가 같다는 뜻은 아님
    if data["image_width"] != width or data["image_height"] != height:
        print("기준 이미지와 JSON 좌표의 해상도가 다릅니다.")
        return


    # 2-3. 주차면별 마스크 생성

    # 주차면 ID, 마스크, 전체 픽셀 수를 저장할 리스트
    spaces = []

    # JSON에 저장된 A-01, A-02 등의 주차면을 하나씩 가져옴
    for item in data["spaces"]:
        
        # 다각형을 구성하는 꼭짓점 좌표를 정수형 NumPy 배열로 변환
        # OpenCV에서 다각형 좌표를 처리할 때 int32 자료형 사용
        points = np.array(item["points"], dtype=np.int32)

        # 기준 이미지와 동일한 크기의 검은색 배열 생성
        # NumPy의 2차원 uint8 배열을 흑백 이미지처럼 사용
        # 0은 검은색, 255는 흰색
        mask = np.zeros((height, width), dtype=np.uint8)

        # cv2.fillPoly() : 꼭짓점을 연결한 다각형 내부를 지정한 값으로 채움
        # [points] : 다각형 여러 개를 받을 수 있는 함수이므로 리스트에 담아 전달
        # 결과적으로 해당 주차면 내부만 255(흰색)가 됨
        cv2.fillPoly(mask, [points], 255)

        # 주차면의 테두리 부근을 분석 대상에서 조금 제외
        # np.ones() : 모든 요소가 1인 7x7 커널 생성
        # cv2.erode() : 커널을 이용해 마스크의 흰색 영역을 침식
        # 일반적인 직선 경계에서 약 3px 정도 안쪽으로 축소
        # 주차선의 위치가 조금 달라졌을 때 발생하는 오탐을 줄이기 위함
        kernel = np.ones((7, 7), dtype=np.uint8)
        mask = cv2.erode(mask, kernel)

        # cv2.countNonZero() : 배열에서 0이 아닌 픽셀의 개수를 반환
        # 현재 마스크는 흰색 영역이 주차면이므로
        # 흰색 픽셀 수가 해당 주차면의 전체 분석 대상 픽셀 수가 됨
        total_pixels = cv2.countNonZero(mask)

        # 주차면의 크기가 0이면 변화율 계산 시 0으로 나누는 오류 발생
        if total_pixels == 0:
            print(f'{item["id"]} : 주차면 영역 오류')
            return

        # 이후 반복 측정에서 같은 마스크를 계속 재사용하기 위해 저장
        # 주차면 좌표는 테스트 중 바뀌지 않으므로 한 번만 생성하면 됨
        spaces.append({
            "id": item["id"],
            "mask": mask,
            "total_pixels": total_pixels
        })


    # 2-4. 기준 이미지 전처리

    # cv2.cvtColor() : 컬러 이미지를 흑백 이미지로 변환
    # BGR 이미지는 픽셀당 3개 채널, GRAY 이미지는 밝기 값 1개 사용
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)

    # cv2.GaussianBlur() : 주변 픽셀을 고려해 작은 노이즈를 완화
    # (5, 5) : 5x5 크기의 커널 사용
    # 0 : 표준편차를 OpenCV가 자동 계산
    # 기준 이미지와 현재 이미지 모두 같은 방식으로 전처리해야 함
    reference_gray = cv2.GaussianBlur(reference_gray, (5, 5), 0)


    # 2-5. 웹캠 연결

    # cv2.VideoCapture() : 웹캠 장치를 연결
    # 0 : 첫 번째 카메라
    # cv2.CAP_DSHOW : Windows의 DirectShow 방식으로 연결
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    # isOpened() : 웹캠 연결 성공 여부 확인
    if not cap.isOpened():
        print("웹캠을 연결할 수 없습니다.")
        return
    
    # 측정 결과를 시간 순서대로 저장할 리스트
    measurements = []

    try:
        # 웹캠 연결 직후 자동 노출 등이 안정화되도록 30프레임 읽기
        for _ in range(30):
            
            # cap.read()는 성공 여부(ret)와 현재 프레임(frame)을 반환
            ret, frame = cap.read()

            if not ret:
                print("웹캠 초기 촬영 실패")
                return
            
        print(f"빈 주차면 변화율 측정 시작 ({TEST_DURATION}초)")
        print("측정 중 물체를 올려놓지 마세요.\n")


        # 2-6. 측정 시작 시각 저장

        # time.monotonic() : 시간 간격을 측정하기 위한 시계 값 반환
        # 컴퓨터의 날짜나 시간이 바뀌어도 경과 시간을 측정하는 데 적합
        start_time = time.monotonic()

        # 시작 직후 첫 번째 측정이 가능하도록 설정
        # 예) start_time이 100이라면 last_check는 99.5
        #     첫 반복에서 100 - 99.5 = 0.5이므로 바로 분석
        last_check = start_time - CHECK_INTERVAL


        # 2-7. 지정한 시간 동안 웹캠 프레임 읽기

        # 측정 시작 후 TEST_DURATION(60초)이 지나면 반복 종료
        while time.monotonic() - start_time < TEST_DURATION:
            
            ret, frame = cap.read()

            if not ret:
                print("웹캠 프레임 읽기 실패")
                break

            # 기준 이미지와 현재 프레임의 높이, 너비, 채널 수 비교
            # 카메라 구도가 바뀌어도 shape는 같을 수 있음
            if frame.shape != reference.shape:
                print("웹캠과 기준 이미지의 크기가 다릅니다.")
                break


            # 2-8. 일정한 시간 간격으로만 분석

            now = time.monotonic()

            # 마지막 측정으로부터 0.5초가 지나지 않았으면 건너뜀
            # continue : 현재 반복문의 나머지 코드를 실행하지 않고 다음 반복으로 이동
            # 예) 0.2초 경과 → 측정 생략
            #     0.5초 이상 경과 → 측정 진행
            if now - last_check < CHECK_INTERVAL:
                continue
                
            # 현재 시각을 마지막 측정 시각으로 갱신
            last_check = now


            # 2-9. 현재 프레임 전처리

            # 기준 이미지와 동일하게 흑백 변환과 블러 처리
            current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            current_gray = cv2.GaussianBlur(current_gray, (5, 5), 0)


            # 2-10. 기준 이미지와 현재 프레임 비교

            # cv2.absdiff() : 두 이미지의 동일한 좌표에서 밝기 차이의 절댓값 계산
            # 예) 기준 픽셀 200, 현재 픽셀 150 → |200-150| = 50
            difference = cv2.absdiff(reference_gray, current_gray)

            # cv2.threshold() : 차이 이미지를 임계값을 기준으로 이진화
            # 차이값이 35 초과 → 255(흰색), 35 이하 → 0(검은색)
            # 따라서 밝기 변화가 큰 픽셀만 흰색으로 남게 됨
            _, changed = cv2.threshold(
                difference, PIXEL_THRESHOLD, 255, cv2.THRESH_BINARY
            )


            # 2-11. 주차면별 변화율 측정

            # 측정 시작 후 경과한 시간을 소수점 첫째 자리까지 반올림
            elapsed = round(now - start_time, 1)

            # 한 번 측정한 시각과 주차면별 변화율을 저장할 딕셔너리
            row = {"elapsed_seconds": elapsed}

            for space in spaces:
                
                # cv2.bitwise_and() : 마스크로 지정한 영역의 픽셀만 추출
                # 같은 changed 이미지를 두 번 전달하여 값은 유지
                # mask가 0인 위치는 제외하고 주차면 내부 변화만 남김
                changed_in_space = cv2.bitwise_and(
                    changed, changed, mask=space["mask"]
                )

                # 주차면 내부에서 변화한 픽셀의 개수
                changed_pixels = cv2.countNonZero(changed_in_space)

                # 해당 주차면에서 변화한 픽셀의 비율
                # 예) 전체 10,000픽셀 중 400픽셀 변화 → 400/10000 = 0.04 (4%)
                change_ratio = changed_pixels / space["total_pixels"]

                # 주차면 ID를 키로 하여 변화율 저장
                # 예) row["A-01"] = 0.04
                row[space["id"]] = round(change_ratio, 4)

            # 한 번 측정한 모든 주차면 결과를 리스트에 추가
            measurements.append(row)

            # 각 주차면의 변화율을 출력하기 위한 문자열 생성
            # join() : 여러 문자열을 구분자로 연결
            # :.2% : 비율을 백분율로 변환하고 소수점 둘째 자리까지 표시
            values = " | ".join(
                f'{space["id"]} : {row[space["id"]]:.2%}'
                for space in spaces
            )

            print(f"{elapsed:5.1f}초 | {values}")

    except KeyboardInterrupt:
        # Ctrl+C를 눌러 중단한 경우
        print("\n사용자가 측정을 중단했습니다.")

    finally:
        # 정상 종료 또는 오류가 발생한 경우에도 웹캠 연결 해제
        cap.release()


    # 2-12. 측정 데이터 존재 여부 확인

    # 웹캠 촬영 실패 등으로 측정 결과가 하나도 없을 수 있으므로 확인
    if not measurements:
        print("측정된 데이터가 없습니다.")
        return


    # 2-13. 결과 CSV 파일 저장

    # 결과 폴더가 없으면 새로 만들고, 이미 있으면 그대로 사용
    os.makedirs(SAVE_DIR, exist_ok=True)

    # CSV 열 이름 지정
    # 예) elapsed_seconds, A-01, A-02, A-03, A-04
    fieldnames = ["elapsed_seconds"] + [
        space["id"] for space in spaces
    ]

    # csv.DictWriter() : 딕셔너리 데이터를 CSV 형식으로 저장
    # newline="" : Windows에서 불필요한 빈 줄이 생기는 현상 방지
    # utf-8-sig : Excel에서 한글을 읽기 쉽게 BOM 포함 UTF-8 사용
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # 첫 행에 열 이름 기록
        writer.writeheader()

        # measurements 리스트에 담긴 각 딕셔너리를 CSV 행으로 기록
        writer.writerows(measurements)


    # 2-14. 주차면별 변화율 통계 계산 및 출력

    print("\n=== 빈 주차면 변화율 통계 ===")
    print("측정 횟수 :", len(measurements))

    for space in spaces:
        space_id = space["id"]

        # 전체 측정 데이터에서 현재 주차면의 변화율만 가져오기
        # 예) A-01 → [0.01, 0.03, 0.04, ...]
        ratios = [row[space_id] for row in measurements]

        # 평균 변화율 = 변화율 합계 / 측정 횟수
        avg_ratio = sum(ratios) / len(ratios)

        # 측정한 변화율 중 가장 높은 값
        max_ratio = max(ratios)
        
        # 전체 측정 중 5% 이상이었던 횟수 계산
        # 예) [0.02, 0.06, 0.04, 0.07]이라면 2회
        threshold_count = sum(
            1 for ratio in ratios
            if ratio >= OCCUPANCY_THRESHOLD
        )
        
        
        # 2-15. 최대 연속 초과 횟수 계산
        
        # consecutive_count : 현재까지 연속으로 5% 이상 나온 횟수
        # max_consecutive_count : 측정 전체에서 가장 길었던 연속 횟수
        consecutive_count = 0
        max_consecutive_count = 0

        # 변화율을 측정된 시간 순서대로 확인
        for ratio in ratios:
            
            if ratio >= OCCUPANCY_THRESHOLD:
                # 5% 이상이면 연속 횟수 증가
                consecutive_count += 1

                # 지금까지의 최대 연속 횟수보다 크면 갱신
                if consecutive_count > max_consecutive_count:
                    max_consecutive_count = consecutive_count

            else:
                # 5% 미만이면 연속 기록이 끊겼으므로 0으로 초기화
                consecutive_count = 0

        # 2-16. 실시간 점유 확정 조건 충족 여부 (추가)

        # 예) 최대 연속 횟수가 3회이면 5회 조건을 충족하지 못함
        #     최대 연속 횟수가 6회이면 5회 조건을 충족함
        if max_consecutive_count >= STABLE_FRAMES:
            stable_result = "예"
        else:
            stable_result = "아니요"


        # 2-17. 통계 출력
        
        print(f"\n{space_id}")
        print(f"  평균 변화율: {avg_ratio:.2%}")
        print(f"  최대 변화율: {max_ratio:.2%}")
        print(f"  5% 이상 횟수: {threshold_count}회")
        print(f"  최대 연속 초과 횟수: {max_consecutive_count}회")
        print(f"  5회 연속 점유 조건 충족: {stable_result}")

    print("\nCSV 저장 위치 :", CSV_PATH)


# 3. 프로그램 실행부
if __name__ == "__main__":
    test_stability()
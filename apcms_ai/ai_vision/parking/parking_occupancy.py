# OpenCV를 이용해 빈 주차장 사진과 현재 웹캠 사진을 비교하고, 주차면에 변화가 발생했는지 판단

# 1. 기준 이미지
# empty_reference.jpg - 아무것도 없는 주차장

# 2. 현재 이미지
# webcam_frame.jpg - 현재 웹캠 사진

# 3. 이미지 전처리 후 차이 계산
# cv2.absdiff() + cv2.threshold() : 아래 코드 내에서 주석으로 설명

# 4. 주차면별 변화율 계산
# parking_spots.json에 저장된 다각형 좌표 사용

# 5. 상태 판별 - 5%는 실험용 임계값
# EMPTY : 변화율 5% 미만
# OCCUPIED : 변화율 5% 이상
import json
import os
import cv2
import numpy as np

from ai_vision.paths import DATA_DIR, RESULT_DIR

SAVE_DIR = RESULT_DIR / "parking" # 결과를 저장할 폴더
REFERENCE_PATH = DATA_DIR / "parking_spaces" / "empty_reference.jpg" # 빈 주차장 기준 사진
CURRENT_PATH = SAVE_DIR / "webcam_frame.jpg" # 현재 웹캠 사진(물건 올려두고 새로 찍은 사진)
JSON_PATH = DATA_DIR / "parking_spaces" / "parking_spots.json" # 주차면 네 모서리 좌표

# 두 임계값
PIXEL_THRESHOLD = 35 # 픽셀 하나가 얼마나 달라져야 변화로 인정할지 결정
OCCUPANCY_THRESHOLD = 0.05 # 주차면 내부 픽셀 중 얼마나 많은 픽셀이 변해야 점유로 인정할지 결정


def detect_occupancy():
    
    # 1. 이미지 읽기와 오류 검사
    
    # (높이, 너비, 채널 개수)
    reference = cv2.imread(REFERENCE_PATH) # 기준 이미지 (empty_reference.jpg)
    current = cv2.imread(CURRENT_PATH) # 현재 이미지 (webcam_frame.jpg)
    
    # 두 이미지가 존재하는지 확인
    if reference is None or current is None: 
        print("기준 이미지 또는 현재 이미지를 읽을 수 없습니다.")
        return

    # 이미지의 높이, 너비, 채널 개수가 같은지 확인
    # 이미지 크기가 같더라도 카메라 위치나 촬영 구도가 달라지면 비교 결과가 부정확해질 수 있음
    if reference.shape != current.shape:
        print("두 이미지의 크기가 다릅니다.")
        return


    # 2. JSON에서 주차면 좌표 가져오기
    
    # parking_space_annotation.ipynb 에서 만든 json 파일(parking_spots.json) 읽어오기
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f) # JSON 파일의 내용을 Python 딕셔너리로 변환(역직렬화)

    height, width = current.shape[:2] # (높이, 너비, 채널 개수) 에서 높이, 너비 까지 가져옴

    # 기준 데이터와 현재 데이터의 검증
    if data["image_width"] != width or data["image_height"] != height:
        print("JSON 좌표와 현재 이미지의 해상도가 다릅니다.")
        return


    # 3. 이미지를 흑백으로 변환하고 노이즈 제거
    
    # 흑백 변환 
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    current_gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    
    # 노이즈 완화
    reference_gray = cv2.GaussianBlur(reference_gray, (5, 5), 0)
    current_gray = cv2.GaussianBlur(current_gray, (5, 5), 0)
    
    
    # 4. 이미지 차이 계산

    # 기준 이미지와 현재 이미지의 차이 계산
    # cv2.absdiff() : 두 이미지의 같은 위치에 있는 픽셀값을 비교(픽셀 밝기 차이)
    difference = cv2.absdiff(reference_gray, current_gray)

    # cv2.threshold( : 각 픽셀값을 임계값과 비교하여 이진화(이 코드에서는 변화한 픽셀만 선택 하기 위해 사용)
    #     입력 이미지, 기준 임계값(35), 임계값을 넘었거나 만족할 때 적용할 최대값, 픽셀 값을 어떤 규칙으로 변환할 것인가 
    # )
    # 조건에 따라 결과를 0 또는 255 로 바꿈 (검정색과 흰색으로 이분화됨)
    # 예) 기준 픽셀값 200, 현재 픽셀값 150
    # cv2.absdiff() 결과 → |200 - 150| = 50
    # 50 > 35이므로 변화한 픽셀로 인정하여 255(흰색)로 변환
    # 반대로 차이가 35 이하라면 0(검은색)으로 변환
    _, changed = cv2.threshold( # _ : 사용된 임계값(필요 없어서 _로 받음), changed : 결과 이미지
        difference, PIXEL_THRESHOLD, 255, cv2.THRESH_BINARY # cv2.THRESH_BINARY : 기준값보다 크면 지정한 최대값, 작거나 같으면 0
    )
    # 이미지 전체에서 변화가 발생한 픽셀을 흰색으로
    
    
    # 5. 주차면별 다각형 마스크 생성

    annotated = current.copy() # 현재 이미지 복사
    results = [] # 결과를 담을 리스트

    print("=== 주차면 점유 감지 결과 ===")

    # json 파일(parking_spots.json)에 있는 주차면(data["spaces"])을 하나씩 가져오자
    for space in data["spaces"]:
        space_id = space["id"] # 주차면 id (A01, A02 같은)
        points = np.array(space["points"], dtype=np.int32) # 주차면을 구성하는 4개의 꼭짓점 좌표(X, Y)

        # 주차면 내부 영역 선택 - 전체 이미지가 아니라 A-01, A-02 등의 주차면 내부만 분석하기 위해
        mask = np.zeros((height, width), dtype=np.uint8) # 우리 이미지 크기와 동일한 검정색 배열을 만들어서
        
        cv2.fillPoly(mask, [points], 255) # 앞에 저장한 네 모서리를 연결하여 주차면 부분만 흰색(255)으로 채우기
        
        # Q. points 는 이미 배열인데 왜 대괄호를 씌우나?
        # A. cv2.polylines() 함수는 여러 개의 다각형(윤곽선 그룹)을 한꺼번에 그릴 수 있는 3차원 구조을 요구함.
        # points 는 2차원 배열이기 때문에 []를 씌움
        
        # Q. mask 는 넘파이 배열인데 어떻게 이미지처럼 사용할 수 있는가?
        # A. OpenCV는 이미지를 NumPy 배열로 표현하기 때문에
        # np.zeros()로 만들어진 2차원 배열 = 흑백 이미지 처럼 쓸 수 있음
        # Q. 그렇다면 왜 이미지 파일을 불러와서 쓰는 것이 아닌 굳이 배열을 만들어서 쓰는가?
        # A. 사진에서 내가 원하는 모양의 다각형 영역(분석할 영역)을 정확하고 편하게 지정하기 위해

        # 마스크의 흰색 영역(주차면)을 가장자리에서 조금 깎아냄
        # 주차면 테두리 쪽의 작은 변화로 인한 오인식을 줄이기 위해 사용
        kernel = np.ones((7, 7), dtype=np.uint8) # 요소가 1인 7x7 행렬 생성 (커널)
        mask = cv2.erode(mask, kernel) # 커널을 이용해 mask의 흰색 영역을 약 3px 침식 (오인식 방지)


        # 6. 주차면 내부의 변화율 계산
        
        
        changed_in_space = cv2.bitwise_and( # cv2.bitwise_and() : 두개의 이미지(배열)를 겹쳐서 and 연산을 하는 함수
            changed, changed, mask=mask
        ) # 같은 이미지를 두 번 전달했으므로 픽셀값 자체는 유지하면서 mask가 0인 부분은 제외하는 효과 
        # A-01 주차면 외 다른 주차면의 변화는 A-01 주차면의 점유율에 포함되지 않음
        # mask가 255인 위치에서는 changed의 픽셀값을 유지, mask가 0인 위치에서는 결과가 0이 됨
        # 따라서 전체 변화 이미지 중 해당 주차면 내부의 변화만 추출

        # 분석 대상 주차면의 전체 픽셀 수
        total_pixels = cv2.countNonZero(mask) # cv2.countNonZero() : 배열에서 0이 아닌 픽셀의 개수를 세는 함수
        # mask 는 흰색(255, 0이 아님)이 주차면이기 때문에 total_pixels이 주차면의 전체 픽셀 수가 됨
        
        if total_pixels == 0:
            print(f"{space_id} : 주차면 영역 확인 불가")
            continue
        
        # 주차면 내부에서 변화가 발생한 픽셀 수
        changed_pixels = cv2.countNonZero(changed_in_space)
        # 주차면 내부에서 변화가 발생한 픽셀의 비율 (변화율)
        change_ratio = changed_pixels / total_pixels


        # 7. 점유 상태 판정
        
        # OCCUPANCY_THRESHOLD = 0.05 (5%)
        # 예) 주차면 전체 픽셀이 10,000개이고 변화한 픽셀이 600개라면
        #     change_ratio = 600 / 10000 = 0.06 (6%)
        #     0.06 >= 0.05이므로 OCCUPIED 판정
        if change_ratio >= OCCUPANCY_THRESHOLD: # 변화율이 설정한 임계값 이상이면
            status = "OCCUPIED"
            color = (0, 0, 255) # BGR - 빨간색
        else: # 아니라면
            status = "EMPTY"
            color = (0, 255, 0) # BGR - 초록색

        results.append({ # 결과 저장
            "space_id": space_id,
            "status": status,
            "change_ratio": round(change_ratio, 4) # 소수점 이하 네 자리까지 반올림
        })

        print(f"{space_id}: {status} (변화율: {change_ratio:.2%})")
        
        
        # 8. 결과 이미지에 주차면 표시

        # cv2.polylines(결과를 그릴 이미지, 다각형 좌표 배열, 시작점 끝점 이을지True 말지False, 선 색, 선 두께) : 다각형 테두리를 그림
        cv2.polylines(annotated, [points], True, color, 2)

        x, y = points[0] # 첫번째 모서리의 좌표

        cv2.putText(
            annotated,
            f"{space_id} : {status}",
            (int(x), max(int(y) - 10, 15)), # 주차면 꼭짓점보다 살짝 위(y - 10)에 글자를 쓸건데 텍스트가 화면 위쪽으로 벗어나지 않도록 최소 Y좌표를 15로 제한
            cv2.FONT_HERSHEY_SIMPLEX, # 폰트
            0.4, # 글자 크기
            color, # 글자 색상
            1 # 글자 두께
        )


    # 9. 전체 점유 현황 계산
    
    occupied_count = sum( # 리스트에서 OCCUPIED 상태인 주차면의 총 개수
        1 for result in results
        if result["status"] == "OCCUPIED"
    )

    output = { # 최종 결과
        "total_spaces": len(results),
        "occupied_count": occupied_count,
        "empty_count": len(results) - occupied_count,
        "spaces": results
    }
    
    
    # 10. 결과 파일 저장

    # 결과 폴더 및 파일 생성
    os.makedirs(SAVE_DIR, exist_ok=True)

    image_path = SAVE_DIR / "occupancy_result.jpg"
    output_path = SAVE_DIR / "occupancy_result.json"

    if cv2.imwrite(image_path, annotated):
        print("결과 이미지 저장 성공")
    else:
        print("결과 이미지 저장 실패")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print("\n=== 전체 주차면 현황 ===")
    print(f"전체: {output['total_spaces']}개")
    print(f"점유: {output['occupied_count']}개")
    print(f"빈자리: {output['empty_count']}개")

    print("\n결과 이미지:", image_path)
    print("결과 JSON:", output_path)


# 실행부
if __name__ == "__main__":
    detect_occupancy()
import sys

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from paths import TEST_IMAGE_DIR
from safety.fire_smoke_detector import detect_fire_smoke


# 1. 화재·연기 감지 테스트 이미지 경로 설정

# paths.py에 정의된 TEST_IMAGE_DIR 사용
# 현재 경로: ai_vision/test_images
#
# / 연산자는 Path 객체에서 하위 경로를 연결하는 역할
# 최종 경로:
# ai_vision/test_images/safety/fire_test.jpg
IMAGE_PATH = TEST_IMAGE_DIR / "safety" / "fire_test.jpg"


# 2. main() - 화재·연기 감지 테스트 실행

def main():


    # 2-1. 화재·연기 탐지 함수 호출

    # detect_fire_smoke()에 테스트 이미지 경로를 전달
    # 해당 함수 내부에서 이미지 읽기, 모델 로딩,
    # YOLO 추론, 결과 파일 저장까지 수행
    # 반환받은 탐지 정보는 result 딕셔너리에 저장
    result = detect_fire_smoke(IMAGE_PATH)


    # 2-2. 연기와 불꽃 탐지 개수 출력

    print("\n[화재·연기 탐지 결과]")

    # 딕셔너리의 키를 사용하여 탐지 개수 가져오기
    # result["smoke_count"]: 연기 탐지 박스 개수
    # result["fire_count"]: 불꽃 탐지 박스 개수
    print(f"연기 탐지 개수 : {result['smoke_count']}")
    print(f"불꽃 탐지 개수 : {result['fire_count']}")


    # 2-3. 탐지된 객체별 상세 정보 출력

    # result["detections"]는 탐지 정보 딕셔너리의 리스트
    # for문으로 각각의 탐지 객체를 하나씩 가져옴
    for item in result["detections"]:

        # item["class_name"]: FIRE 또는 SMOKE
        # item["confidence"]: 0~1 범위의 신뢰도 값
        # item["bbox"]: 사각형 위치 좌표
        # :.2% 는 실수를 백분율로 표시하고 소수점 둘째 자리까지 출력하는 형식
        # 예: 0.3448 -> 34.48%
        print(
            f"객체 : {item['class_name']} | "
            f"신뢰도 : {item['confidence']:.2%} | "
            f"위치 : {item['bbox']}"
        )


    # 2-4. 탐지 결과가 없는 경우 메시지 출력

    # not: True/False를 반대로 바꾸는 연산자
    # detected가 False일 때 아래 문장이 실행됨
    if not result["detected"]:
        print("탐지된 연기 또는 불꽃이 없습니다.")


    # 2-5. YOLO 모델 로딩 시간 및 추론 시간 출력

    print("\n[처리 시간]")

    # 모델 파일을 메모리에 불러오는 데 걸린 시간
    print(
        f"모델 로딩 : "
        f"{result['model_load_time_ms']:.2f} ms"
    )

    # YOLO가 이미지 한 장을 분석하는 데 걸린 시간
    # 현재 CPU를 사용하므로 CPU 추론 시간에 해당
    print(
        f"이미지 추론 : "
        f"{result['inference_time_ms']:.2f} ms"
    )


    # 2-6. 결과 파일 저장 위치 안내

    # 실제 파일 저장은 detect_fire_smoke()에서 수행
    # 여기서는 테스트 완료 메시지만 출력
    print("\n결과 저장 완료 : results/safety/")


# 3. 실행부
if __name__ == "__main__":
    main()

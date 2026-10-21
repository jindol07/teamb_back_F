# D:/finalProjectB/back/apcms_ai/ai_vision/safety/test_fire_smoke_speed.py
import time
import cv2


from ai_vision.paths import MODEL_DIR, TEST_IMAGE_DIR


# 1. CPU 추론 속도 테스트 설정

# 기존 화재·연기 감지에 사용했던 YOLO 모델
MODEL_PATH = MODEL_DIR / "fire_smoke.pt"

# 기존 테스트에서 사용했던 화재 이미지
IMAGE_PATH = TEST_IMAGE_DIR / "safety" / "fire_test.jpg"

# YOLO가 이미지를 분석할 때 사용할 입력 크기
# 기존 fire_smoke_detector.py와 동일한 설정
IMAGE_SIZE = 640

# 모델이 반환할 최소 탐지 신뢰도
# 0.15 = 15% 이상인 탐지 결과만 사용
CONF_THRESHOLD = 0.15

# 추론을 반복할 횟수
# 첫 번째 추론은 초기화 시간이 포함될 수 있으므로 별도로 처리하고, 나머지 10회로 평균을 계산
TEST_COUNT = 10


# 2. test_fire_smoke_speed() - CPU 추론 속도 측정

def test_fire_smoke_speed():
    # 측정을 요청할 때에만 모델 라이브러리를 불러옵니다.
    from ultralytics import YOLO
    # 2-1. 모델 파일과 테스트 이미지 존재 여부 확인

    # is_file(): 해당 경로에 실제 파일이 존재하는지 확인
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"YOLO 모델 파일이 없습니다: {MODEL_PATH}"
        )

    if not IMAGE_PATH.is_file():
        raise FileNotFoundError(
            f"테스트 이미지가 없습니다: {IMAGE_PATH}"
        )

    # 2-2. 테스트 이미지 읽기

    # 이미지는 모델을 테스트하는 동안 계속 재사용하므로 반복할 때마다 파일을 다시 읽지 않음
    image = cv2.imread(IMAGE_PATH)

    if image is None:
        raise ValueError(
            f"이미지를 읽을 수 없습니다: {IMAGE_PATH}"
        )

    # 2-3. YOLO 모델 로딩 시간 측정

    # perf_counter(): 짧은 처리 시간 측정에 적합한 타이머
    # 초 단위로 경과 시간을 계산할 수 있음
    load_start = time.perf_counter()

    # 학습된 YOLO 모델을 메모리에 한 번만 불러옴
    # 반복 측정 중에는 같은 model 객체를 재사용
    model = YOLO(MODEL_PATH)

    # 경과 시간(초)에 1000을 곱해 ms로 변환
    load_time_ms = (
        time.perf_counter() - load_start
    ) * 1000

    # 2-4. 첫 번째 추론으로 모델 준비

    # 첫 번째 predict() 실행에는 모델 초기화, 내부 연산 준비 등이 포함될 수 있음
    # 따라서 이후 평균 계산에서는 제외
    warmup_start = time.perf_counter()

    model.predict(
        source=image,
        conf=CONF_THRESHOLD,
        imgsz=IMAGE_SIZE,
        device="cpu",
        verbose=False
    )

    warmup_time_ms = (
        time.perf_counter() - warmup_start
    ) * 1000

    # 2-5. 동일한 이미지로 10회 반복 추론

    # 각 추론 시간을 저장할 빈 리스트
    inference_times = []

    # range(TEST_COUNT):
    # TEST_COUNT가 10이라면 0부터 9까지 반복
    for i in range(TEST_COUNT):

        # 현재 추론의 시작 시간 기록
        start = time.perf_counter()

        # 모델을 새로 불러오지 않고 기존 모델 재사용
        results = model.predict(
            source=image,
            conf=CONF_THRESHOLD,
            imgsz=IMAGE_SIZE,
            device="cpu",
            verbose=False
        )

        # 현재 추론에 걸린 시간 계산
        elapsed_ms = (
            time.perf_counter() - start
        ) * 1000

        # append(): 리스트의 마지막에 값 추가
        # 10회 반복 후에는 추론 시간 10개가 저장됨
        inference_times.append(elapsed_ms)

        # 현재 이미지에서 탐지된 박스 개수
        # results[0]: 첫 번째 이미지의 탐지 결과
        # boxes: 탐지된 사각형 정보
        detection_count = len(results[0].boxes)

        print(
            f"{i + 1:2d}회차 | "
            f"추론 시간: {elapsed_ms:8.2f} ms | "
            f"탐지 박스: {detection_count}개"
        )

    # 2-6. 반복 측정 결과 계산

    # sum(): 모든 추론 시간을 더함
    # len(): 측정 횟수 계산
    # 평균 = 총 추론 시간 / 측정 횟수
    avg_time_ms = (
        sum(inference_times) / len(inference_times)
    )

    # min(): 가장 짧았던 추론 시간
    min_time_ms = min(inference_times)

    # max(): 가장 길었던 추론 시간
    max_time_ms = max(inference_times)

    # FPS(Frames Per Second): 1초에 처리 가능한 이미지 수
    # 1000ms = 1초이므로 1000 / 평균 추론 시간
    # 이는 이미지 추론만 고려한 추정 FPS
    # 카메라 입력, 결과 저장, API 전송 시간은 포함하지 않음
    estimated_fps = (
        1000 / avg_time_ms
        if avg_time_ms > 0
        else 0
    )

    # 2-7. 최종 측정 결과 출력

    print("\n[CPU 추론 속도 측정 결과]")

    print(f"모델 로딩 시간 : {load_time_ms:.2f} ms")
    print(f"첫 추론 시간   : {warmup_time_ms:.2f} ms")
    print(f"반복 측정 횟수 : {TEST_COUNT}회")

    print(f"평균 추론 시간 : {avg_time_ms:.2f} ms")
    print(f"최소 추론 시간 : {min_time_ms:.2f} ms")
    print(f"최대 추론 시간 : {max_time_ms:.2f} ms")

    print(f"추정 처리 속도 : {estimated_fps:.2f} FPS")

    # 2-8. 목표 분석 간격과 비교

    # 실시간 화재 감지를 0.5초마다 1회 수행한다면
    # 한 번 분석하는 데 걸리는 시간은 500ms보다 짧아야 해당 간격을 유지하기 쉬움
    # 단, 실제 실시간 처리에서는 웹캠 읽기 및 후처리 시간도 추가로 고려해야 함
    target_interval_ms = 500

    print("\n[0.5초 간격 분석 가능성]")

    if avg_time_ms <= target_interval_ms:
        print("평균 추론 시간 기준으로 0.5초 간격 분석 가능성이 있습니다.")
    else:
        print("평균 추론 시간이 0.5초를 초과합니다.")
        print("분석 간격 조정이나 모델 최적화를 검토해야 합니다.")


# 3. 실행부

if __name__ == "__main__":
    test_fire_smoke_speed()

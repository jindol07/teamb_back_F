import cv2
import json
import sys
import time

from ultralytics import YOLO

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paths import MODEL_DIR, RESULT_DIR


# 1. 화재·연기 감지에 사용할 경로와 설정값

# paths.py의 MODEL_DIR을 기준으로 학습된 모델 파일 지정
MODEL_PATH = MODEL_DIR / "fire_smoke.pt"

# 탐지 결과 이미지와 JSON을 저장할 폴더
SAVE_DIR = RESULT_DIR / "safety"

# YOLO 탐지 결과를 인정할 최소 신뢰도
# 0.15 = 15% 이상인 탐지 결과만 반환
# 현재는 모델 성능을 확인하기 위한 테스트용 설정
CONF_THRESHOLD = 0.15

# YOLO가 이미지를 분석할 때 사용할 입력 크기
# 원본 이미지 크기와 반드시 같을 필요는 없음
# 640은 일반적인 YOLO 입력 크기 설정
IMAGE_SIZE = 640


# 2. detect_fire_smoke() - 이미지에서 불꽃과 연기 탐지

def detect_fire_smoke(image_path):


    # 2-1. 입력 이미지와 모델 파일 경로 확인

    # Path(): 전달받은 이미지 경로를 Path 객체로 변환
    # 문자열뿐 아니라 이미 Path 객체인 경우도 처리 가능
    image_path = Path(image_path)

    # is_file(): 경로에 실제 파일이 있는지 확인
    # 파일이 없다면 원인을 알 수 있도록 예외 발생
    if not image_path.is_file():
        raise FileNotFoundError(
            f"테스트 이미지가 없습니다: {image_path}"
        )

    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"YOLO 모델 파일이 없습니다: {MODEL_PATH}"
        )


    # 2-2. 결과 저장 폴더 생성

    # parents=True: 필요한 상위 폴더도 함께 생성
    # exist_ok=True: 폴더가 이미 있어도 오류 없이 진행
    SAVE_DIR.mkdir(parents=True, exist_ok=True)


    # 2-3. OpenCV로 테스트 이미지 읽기

    # OpenCV는 기본적으로 색상 순서를 BGR로 사용
    # YOLO는 이 NumPy 이미지 배열을 입력받을 수 있음
    image = cv2.imread(image_path)

    # 파일은 존재하지만 이미지가 손상되었거나
    # 지원하지 않는 형식이면 None이 반환될 수 있음
    if image is None:
        raise ValueError(
            f"이미지를 읽을 수 없습니다: {image_path}"
        )


    # 2-4. YOLO를 사용하여 이미지 분석
    
    model = YOLO(MODEL_PATH)

    # perf_counter(): 짧은 처리 시간을 측정하는 함수
    # 현재 시각이 아니라 경과 시간을 계산할 때 사용
    load_start = time.perf_counter() # 모델 로드 시작 시간

    # 모델 로드에 걸린 시간
    # 종료 시각 - 시작 시각 = 경과 시간(초)
    # 1000을 곱해서 밀리초(ms) 단위로 변환
    load_time_ms = (
        time.perf_counter() - load_start
    ) * 1000

    inference_start = time.perf_counter() # 추론 시작 시간

    # predict(): 입력 이미지에서 학습된 객체를 탐지
    results = model.predict(
        source=image, # source: 분석할 이미지
        conf=CONF_THRESHOLD, # conf: 최소 신뢰도 (0.15 = 15%)
        imgsz=IMAGE_SIZE, # imgsz: 모델에 전달할 이미지 크기
        device="cpu", # device="cpu": GPU가 아닌 CPU에서 계산
        verbose=False # verbose=False: YOLO의 상세 진행 로그 생략
    )

    # 모델 추론에 걸린 시간
    inference_time_ms = (
        time.perf_counter() - inference_start
    ) * 1000

    # 이미지 한 장의 YOLO 결과 선택
    # predict()는 여러 이미지도 분석할 수 있으므로 결과를 리스트와 비슷한 형태로 반환
    # 현재는 이미지 한 장만 분석했으므로 results[0]으로 첫 번째 결과를 선택
    result = results[0]


    # 2-5. 탐지 객체의 상세 정보 추출

    # 탐지된 객체를 하나씩 저장할 리스트
    # 탐지된 객체가 없다면 빈 리스트 []로 유지
    detections = []

    # result.boxes: YOLO가 탐지한 사각형 정보
    # for문으로 각각의 탐지 박스를 하나씩 처리
    for box in result.boxes:

        # cls: 객체 종류를 숫자로 나타낸 클래스 번호
        # item(): PyTorch 텐서의 값을 Python 숫자로 변환
        class_id = box.cls[0].item()

        # model.names: 클래스 번호와 이름을 연결한 정보(대문자)
        # 현재 모델은 0=smoke, 1=fire
        class_name = model.names[class_id].upper()

        # conf: 해당 박스의 탐지 신뢰도
        # 예: 0.3448 = 약 34.48%
        confidence = box.conf[0].item()

        # xyxy : 탐지 영역의 사각형 좌표
        # x1, y1: 왼쪽 위 좌표
        # x2, y2: 오른쪽 아래 좌표
        # 변수 4개에 값을 순서대로 나누어 리스트로 저장
        x1, y1, x2, y2 = box.xyxy[0].tolist()

        # 탐지 객체 하나의 정보를 딕셔너리로 정리
        # round(반올림할수, 자릿수) : 숫자만 쓰면 정수로 반올림
        detections.append({
            "class_name": class_name,
            "confidence": round(confidence, 4),
            "bbox": [
                round(x1),
                round(y1),
                round(x2),
                round(y2)
            ]
        })

    # 2-6. 연기와 불꽃 탐지 개수 계산

    # SMOKE 개수
    smoke_count = sum(
        1 for item in detections
        if item["class_name"] == "SMOKE"
    )

    # FIRE 개수
    fire_count = sum(
        1 for item in detections
        if item["class_name"] == "FIRE"
    )

    # 탐지 객체가 하나 이상이면 True, 탐지 객체가 없으면 False
    detected = len(detections) > 0

    # 주의 : fire_count는 서로 다른 화재 사건의 수가 아니라 FIRE로 분류된 탐지 박스의 개수임
    # 하나의 불꽃에서 여러 박스가 나올 수도 있음

    # 2-7. 탐지 결과를 이미지에 표시하고 저장

    # 표시 내용 : 사각형, 클래스 이름, 신뢰도
    # 반환값은 OpenCV에서 저장 가능한 이미지 배열
    annotated_image = result.plot()

    # 최종 이미지 저장 경로
    image_output = SAVE_DIR / "fire_smoke_result.jpg"

    # 이미지를 파일로 저장
    # 저장 성공 시 True, 실패 시 False 반환
    saved = cv2.imwrite(
        image_output,
        annotated_image
    )

    if not saved:
        raise OSError(f"탐지 결과 이미지 저장 실패: {image_output}")


    # 2-8. 탐지 결과를 JSON 데이터로 정리

    # json
    output = {
        "image_name": image_path.name,
        "detected": detected,
        "smoke_count": smoke_count,
        "fire_count": fire_count,
        "detections": detections,
        "model_load_time_ms": round(load_time_ms, 2),
        "inference_time_ms": round(inference_time_ms, 2)
    }

    json_output = SAVE_DIR / "fire_smoke_result.json"

    # with open(): 파일을 열어 작업한 뒤 자동으로 닫음
    # "w": 쓰기 모드 (기존 파일이 있으면 덮어씀)
    # encoding="utf-8": 한글 저장 지원
    with open(json_output, "w", encoding="utf-8") as file:

        json.dump( # json.dump(): Python 딕셔너리를 JSON 파일로 저장
            output,
            file,
            ensure_ascii=False, # ensure_ascii=False: 한글을 그대로 저장
            indent=4 # indent=4: 들여쓰기 4
        )


    # 2-9. 탐지 결과를 호출한 코드에 반환

    return output

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/recognizer.py
# APCMS 차량 및 번호판 인식 기능

# 1. YOLO 차량 탐지
# 2. 탐지된 차량 이미지에서 번호판 탐지
# 3. 원본 이미지에서 번호판 영역 추출
# 4. PaddleOCR로 번호판 문자 인식
# 5. 필요하면 이미지 전처리 후 OCR 재시도
# 6. 차량 및 번호판 인식 결과 반환

import os
import re
import tempfile
import unicodedata
import cv2
import numpy as np
from functools import wraps

from ai_vision.recognition.recognition_models import RecognitionModels
from ai_vision.recognition.ocr_image_policy import retry_image_size
from ai_vision.recognition.plate_review import KOREAN_PLATE_PATTERN, plate_review_reasons


# 2. 차량 탐지 클래스 설정

# YOLO의 일반 객체 중 차량에 해당하는 클래스만 사용
VEHICLE_CLASSES = {
    "car",
    "truck",
    "bus",
    "motorcycle"
}


# 3. 모델은 각 기능의 최초 호출에서 역할별로 생성하고 이후 재사용합니다.
# 번호판 crop만 읽는 실시간 경로에서는 별도의 차량 탐지 모델을 만들지 않습니다.
_models = RecognitionModels()


def _serialize_inference(role):
    # 같은 역할의 모델은 결과 순회·fallback까지 한 번에 보호합니다.
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with _models.inference_lock(role):
                return function(*args, **kwargs)
        return wrapped
    return decorate


# 4. normalize_plate_text() - OCR 문자열 정규화

def normalize_plate_text(text):
    """
    OCR이 인식한 문자열의 공백 및 문자 형태를 정리한다.
    """

    # 4-1. 인식된 문자열이 없다면 빈 문자열 반환
    if not text:
        return ""

    # 4-2. 유니코드 문자열 정규화
    # NFC는 조합형 한글 등을 표준적인 형태로 정리
    text = unicodedata.normalize("NFC", text)

    # 4-3. 문자열 앞뒤 공백 제거
    text = text.strip()

    # 4-4. 문자열 중간의 공백까지 제거
    # \s+는 공백, 탭, 줄바꿈 등이 하나 이상인 경우
    text = re.sub(r"\s+", "", text)

    # 4-5. 영문자가 있다면 대문자로 통일
    text = text.upper()

    return text


# 5. classify_plate_format() - 번호판 형식 분류

def classify_plate_format(text):
    """
    인식된 번호판 문자열의 형식을 분류한다.

    KOREAN_VALID : 한국 번호판 형식
    FOREIGN_OR_OTHER : 영문·숫자 형식
    REVIEW : 문자를 읽었지만 형식 불확실
    OCR_FAILED : 인식 문자열 없음
    """

    # 5-1. OCR 결과가 없는 경우
    if not text:
        return "OCR_FAILED"

    # 5-2. 한국 번호판 검사
    # \d{2,3}: 숫자 2~3자리
    # [가-힣]: 한글 1자리
    # \d{4}: 숫자 4자리
    korean_pattern = KOREAN_PLATE_PATTERN

    # fullmatch(): 문자열 전체가 정규식에 맞는지 확인
    if re.fullmatch(korean_pattern, text):
        return "KOREAN_VALID"

    # 5-3. 영문·숫자 번호판 검사
    # (?=.*[A-Z]): 영문 대문자가 최소 한 개 포함
    # [A-Z0-9]{4,10}: 영문·숫자 총 4~10자리
    foreign_pattern = r"^(?=.*[A-Z])[A-Z0-9]{4,10}$"

    if re.fullmatch(foreign_pattern, text):
        return "FOREIGN_OR_OTHER"

    # 5-4. 위 조건에 해당하지 않으면 추가 확인 필요
    return "REVIEW"


# 6. cleanup_plate_text() - OCR 문자열 후처리

def cleanup_plate_text(text):
    """
    OCR 결과에 포함된 일부 특수문자를 제거한다.
    
    단, 특수문자를 제거한 결과가 한국 번호판 형식에
    맞는 경우에만 수정한 문자열을 최종 사용한다.
    """

    # 6-1. 문자열이 없다면 빈 문자열 반환
    if not text:
        return ""

    # 6-2. 원본 OCR 문자열 정규화
    original_text = normalize_plate_text(text)

    # 6-3. 번호판 사이에 잘못 인식된 일부 특수문자 제거
    # 예: 52누·7764 -> 52누7764
    cleaned_text = re.sub(
        r"[·•ㆍ:.\-_]",
        "",
        original_text
    )

    # 6-4. 수정 결과가 정상 한국 번호판인지 검사
    korean_pattern = KOREAN_PLATE_PATTERN

    if re.fullmatch(korean_pattern, cleaned_text):
        return cleaned_text

    # 6-5. 정상 번호판이 아니라면 원래 문자열 유지
    return original_text


# 7. run_paddleocr() - 번호판 OCR 실행

def _join_plate_ocr(texts, polygons):
    # 7-1. 번호판 아래의 작은 영문 장식만 구분합니다. 번호 일부를 추측해서 복원하지 않습니다.
    original = normalize_plate_text("".join(texts))
    if len(texts) != len(polygons) or not texts:
        return original
    # 7-1-1. 두 줄이 각각 한 조각이고 세로 위치가 분리된 경우만 위→아래로 연결합니다.
    # 문자 자체를 고치거나 지역명 등 추가 조각을 버리지는 않습니다.
    if len(texts) == 2:
        try:
            boxes = [np.asarray(p, dtype=float) for p in polygons]
            if all(p.shape == (4, 2) and np.isfinite(p).all() for p in boxes):
                upper, lower = sorted(range(2), key=lambda i: boxes[i][:, 1].mean())
                a, b = boxes[upper], boxes[lower]
                heights = [p[:, 1].max() - p[:, 1].min() for p in boxes]
                separated = (min(heights) > 0 and
                             b[:, 1].mean() - a[:, 1].mean() > max(heights) * .5)
                overlap = min(a[:, 0].max(), b[:, 0].max()) - max(a[:, 0].min(), b[:, 0].min())
                if separated and overlap > 0:
                    return normalize_plate_text(texts[upper] + texts[lower])
        except (TypeError, ValueError):
            return original
    normalized = [normalize_plate_text(text) for text in texts]
    decorations = [i for i, text in enumerate(normalized) if re.fullmatch(r"[A-Z]{3,}", text)]
    main = [i for i in range(len(texts)) if i not in decorations]
    candidate = cleanup_plate_text("".join(normalized[i] for i in main))
    if not decorations or not main or classify_plate_format(candidate) != "KOREAN_VALID":
        return original
    # 7-2. 좌표가 없거나 잘못되면 문자를 버리지 않고 원래 결과를 유지합니다.
    bounds = []
    for polygon in polygons:
        try:
            points = np.asarray(polygon, dtype=float)
        except (TypeError, ValueError):
            return original
        if points.shape != (4, 2) or not np.isfinite(points).all():
            return original
        top, bottom = float(points[:, 1].min()), float(points[:, 1].max())
        if bottom <= top:
            return original
        bounds.append((bottom - top, (top + bottom) / 2))
    height = min(bounds[i][0] for i in main)
    center = max(bounds[i][1] for i in main)
    # 7-3. 본문보다 충분히 작고 아래에 있는 영문만 제외합니다. 큰 글자·같은 줄은 유지합니다.
    if all(bounds[i][0] <= height * .4 and bounds[i][1] > center + height * .5
           for i in decorations):
        return candidate
    return original

@_serialize_inference("ocr")
def run_paddleocr(image):
    """
    OpenCV 이미지에서 문자를 인식한다.
    
    기존 코드와 동일하게 임시 이미지 파일을 생성한 뒤
    PaddleOCR에 전달한다.
    """

    # 7-1. 이미지가 없거나 비어 있으면 실행하지 않음
    if image is None or image.size == 0:
        return ""

    # 7-2. 임시 폴더 생성
    # with문이 끝나면 임시 폴더와 파일이 자동 삭제됨
    with tempfile.TemporaryDirectory() as temp_dir:

        temp_path = os.path.join(
            temp_dir,
            "ocr_input.png"
        )

        # 7-3. JPEG 재압축 손실이 생기지 않도록 PNG로 임시 저장합니다.
        saved = cv2.imwrite(temp_path, image)

        if not saved:
            raise OSError(
                f"OCR 입력 이미지 저장 실패: {temp_path}"
            )

        # 7-4. PaddleOCR 실행
        # 결과에는 인식 문자열 등 여러 정보가 포함됨
        results = _models.ocr().predict(temp_path)

        texts = []
        polygons = []

        # 7-5. 인식된 문자열만 추출
        # rec_texts: PaddleOCR가 인식한 문자 목록
        for item in results:
            texts.extend(item["rec_texts"])
            polygons.extend(item.get("rec_polys", []))

        # 7-6. 여러 문자열을 하나의 번호판 문자열로 연결
        text = _join_plate_ocr(texts, polygons)

    # 7-7. 공백 등을 정리한 문자열 반환
    return normalize_plate_text(text)


# 8. crop_plate_from_original() - 원본 번호판 이미지 추출

def crop_plate_from_original(
    original_image,
    vehicle_box,
    plate_box,
    margin_ratio=0.10
):
    """
    차량 내부에서 찾은 번호판 좌표를
    원본 이미지 좌표로 변환한 뒤 번호판을 잘라낸다.

    JPEG로 저장한 차량 이미지를 다시 자르는 대신
    원본에서 직접 추출하여 화질 손실을 줄인다.
    """

    # 8-1. 차량의 원본 이미지 좌표
    vx1, vy1, vx2, vy2 = vehicle_box

    # 8-2. 차량 내부에서 찾은 번호판 좌표
    px1, py1, px2, py2 = plate_box

    # 8-3. 차량 내부 좌표를 원본 좌표로 변환
    gx1 = vx1 + px1
    gy1 = vy1 + py1
    gx2 = vx1 + px2
    gy2 = vy1 + py2

    # 8-4. 번호판 영역의 가로·세로 크기 계산
    plate_width = gx2 - gx1
    plate_height = gy2 - gy1

    # 8-5. 번호판 주변 여백 계산
    # 기본값은 번호판 가로·세로 크기의 10%
    margin_x = int(plate_width * margin_ratio)
    margin_y = int(plate_height * margin_ratio)

    # 8-6. 원본 이미지 해상도 확인
    image_height, image_width = original_image.shape[:2]

    # 8-7. 이미지 범위를 벗어나지 않도록 좌표 제한
    gx1 = max(0, gx1 - margin_x)
    gy1 = max(0, gy1 - margin_y)
    gx2 = min(image_width, gx2 + margin_x)
    gy2 = min(image_height, gy2 + margin_y)

    # 8-8. NumPy 배열 슬라이싱으로 번호판 영역 추출
    # image[y1:y2, x1:x2] 순서에 주의
    return original_image[gy1:gy2, gx1:gx2]


# 9. retry_ocr() - 번호판 OCR 재시도

def retry_ocr(plate_crop):
    """
    1차 OCR 결과가 불확실할 때 번호판 이미지를
    확대하고 대비를 향상시킨 뒤 재인식한다.
    """

    # 9-1. 번호판 이미지 존재 여부 확인
    if plate_crop is None or plate_crop.size == 0:
        return "", "OCR_FAILED"

    height, width = plate_crop.shape[:2]

    # 9-2. 최대 4배 확대하되 4096px 변 길이·4백만 픽셀 안으로 제한합니다.
    # INTER_CUBIC: 확대할 때 사용하는 보간 방식
    enlarged = cv2.resize(
        plate_crop,
        retry_image_size(width, height),
        interpolation=cv2.INTER_CUBIC
    )

    # 9-3. 흑백 변환
    gray = cv2.cvtColor(
        enlarged,
        cv2.COLOR_BGR2GRAY
    )

    # 9-4. CLAHE로 글자와 배경의 대비 향상
    # 이미지 전체가 아닌 작은 영역별로 대비를 조절
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    enhanced = clahe.apply(gray)

    # 9-5. 전처리한 이미지로 OCR 재실행
    retry_text = run_paddleocr(enhanced)

    # 9-6. 재인식된 문자열 형식 검사
    retry_type = classify_plate_format(retry_text)

    return retry_text, retry_type


# 10. detect_vehicles() - 이미지에서 차량 탐지

@_serialize_inference("vehicle")
def detect_vehicles(image):
    """
    YOLO를 사용하여 차량을 탐지한다.

    1차 탐지: 신뢰도 0.5 이상
    차량이 없다면 2차 탐지: 신뢰도 0.3 이상

    반환값:
        vehicles: 탐지된 차량 정보 리스트
        fallback_used: 낮은 임계값으로 재시도했는지
    """

    # 10-1. 전체 이미지 인식에서만 차량 탐지 모델을 요청합니다.
    vehicle_model = _models.vehicle()
    # 신뢰도 0.5 기준으로 차량 탐지
    results = vehicle_model(
        image,
        conf=0.5,
        verbose=False
    )

    vehicles = []

    # 10-2. YOLO 결과에서 차량 클래스만 추출
    for result in results:
        for box in result.boxes:

            # 탐지 객체의 클래스 번호를 Python 정수로 변환
            class_id = int(box.cls[0].item())

            # 클래스 번호를 이름으로 변환
            class_name = vehicle_model.names[class_id]

            # 차량이 아닌 객체는 건너뜀
            if class_name not in VEHICLE_CLASSES:
                continue

            # 탐지 사각형 좌표: 왼쪽 위, 오른쪽 아래
            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0].tolist()
            )

            # 탐지 신뢰도
            confidence = float(box.conf[0].item())

            vehicles.append({
                "class_name": class_name,
                "confidence": confidence,
                "box": (x1, y1, x2, y2)
            })

    # 10-3. 첫 번째 탐지에서 차량을 찾았는지 확인
    fallback_used = False

    if len(vehicles) == 0:

        # 차량이 하나도 없을 때만 임계값을 낮춤
        fallback_used = True

        results = vehicle_model(
            image,
            conf=0.3,
            verbose=False
        )

        # 10-4. 재탐지 결과에서 차량 클래스 추출
        for result in results:
            for box in result.boxes:

                class_id = int(box.cls[0].item())
                class_name = vehicle_model.names[class_id]

                if class_name not in VEHICLE_CLASSES:
                    continue

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0].tolist()
                )

                confidence = float(box.conf[0].item())

                vehicles.append({
                    "class_name": class_name,
                    "confidence": confidence,
                    "box": (x1, y1, x2, y2)
                })

    return vehicles, fallback_used


# 11. detect_best_plate() - 차량 내부 번호판 탐지

@_serialize_inference("plate")
def detect_best_plate(vehicle_crop):
    """
    차량을 잘라낸 이미지에서 번호판을 탐지한다.

    여러 번호판 후보가 탐지되면
    신뢰도가 가장 높은 번호판 하나를 사용한다.
    """

    # 11-1. 번호판 탐지가 필요할 때만 해당 YOLO를 생성·재사용합니다.
    plate_model = _models.plate()
    results = plate_model(
        vehicle_crop,
        conf=0.25,
        verbose=False
    )

    # 11-2. 번호판 후보를 리스트에 저장
    candidates = []

    for result in results:
        for box in result.boxes:
            # 11-2-1. 보닛 통풍구처럼 지나치게 납작한 후보는 문자 인식으로 넘기지 않습니다.
            # 높은 탐지 점수만으로 선택하지 않으며, 비스듬한 번호판은 추가 미탐지가 될 수 있습니다.
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            if x2 > x1 and y2 > y1 and (x2 - x1) / (y2 - y1) <= 6:
                candidates.append(box)

    # 11-3. 번호판이 탐지되지 않은 경우
    if len(candidates) == 0:
        return None

    # 11-4. 가장 높은 신뢰도의 번호판 선택
    # max()의 key에 비교할 값을 지정
    best_box = max(
        candidates,
        key=lambda box: float(box.conf[0].item())
    )

    # 11-5. 번호판 좌표 및 신뢰도 추출
    x1, y1, x2, y2 = map(
        int,
        best_box.xyxy[0].tolist()
    )

    confidence = float(best_box.conf[0].item())

    return {
        "confidence": confidence,
        "box": (x1, y1, x2, y2)
    }


# 12. recognize_plate() - 번호판 문자 인식

def _has_yellow_plate_background(image):
    # 12-0. 지역 번호판 전체를 지원하기 전에는 노란 배경 후보를 보수적으로 보류합니다.
    # 색으로 지역명을 추측하지 않습니다. 조명·퇴색에 따라 놓치거나 추가 보류할 수 있습니다.
    if image is None or image.size == 0 or image.ndim != 3 or image.shape[2] != 3:
        return False
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, (15, 90, 70), (40, 255, 255))
    return float(np.count_nonzero(yellow)) / yellow.size >= .25


def recognize_plate(plate_crop):
    """
    하나의 번호판 이미지를 OCR로 인식한다.

    1차 OCR을 수행한 뒤 결과가 불확실한 경우에만
    전처리를 적용하여 2차 OCR을 수행한다.
    """

    # 12-1. 원본 번호판 이미지로 1차 OCR
    first_text = run_paddleocr(plate_crop)
    first_type = classify_plate_format(first_text)

    # 12-2. 재시도 결과 변수 초기화
    retry_text = ""
    retry_type = ""

    # 우선 1차 인식 결과를 최종 후보로 설정
    # 삭제 가능한 구분자만으로 완성되는 번호는 재시도로 덮어쓰지 않습니다.
    # 원본 OCR 필드는 그대로 남기며, 빠진 한글을 추측해 채우지는 않습니다.
    final_text = cleanup_plate_text(first_text)
    final_type = classify_plate_format(final_text)

    # 12-3. 1차 OCR 결과가 불확실하면 이미지 전처리 후 재인식
    if final_type in {"REVIEW", "OCR_FAILED"}:

        # 번호판 이미지를 확대하고 대비를 조정하여 OCR 재시도
        retry_text, retry_type = retry_ocr(plate_crop)

        # 재인식 문자열의 특수문자를 정리하고 형식을 다시 판정
        retry_text = cleanup_plate_text(retry_text)
        retry_type = classify_plate_format(retry_text)

        # 12-4. 재인식 결과가 유효한 형식이면 채택
        if retry_type in {
            "KOREAN_VALID",
            "FOREIGN_OR_OTHER"
        }:
            final_text = retry_text
            final_type = retry_type

    # 12-5. 최종 문자열 후처리
    final_text = cleanup_plate_text(final_text)

    # 특수문자 제거 후 번호판 형식을 다시 검사
    final_type = classify_plate_format(final_text)

    # 12-5-1. 지역명이 OCR에서 통째로 빠져도 정상 형식으로 확정되는 것을 막습니다.
    # 원문과 1·2차 결과는 보존하고 최종 형식만 검토 대상으로 남깁니다.
    if final_type == "KOREAN_VALID" and _has_yellow_plate_background(plate_crop):
        final_type = "REVIEW"

    # 12-6. 1차·2차 OCR 정보를 모두 반환
    return {
        "first_ocr": first_text,
        "first_type": first_type,
        "retry_ocr": retry_text,
        "retry_type": retry_type,
        "plate_number": final_text,
        "plate_type": final_type,
        # 기존 필드는 유지하고 검토 원인만 추가합니다. 전송 허용 플래그가 아닙니다.
        "review_reasons": plate_review_reasons(final_text, final_type)
    }


# 13. recognize_image() - 전체 차량번호 인식 실행

def recognize_image(image):
    """
    FastAPI에서 호출하는 차량번호 인식 핵심 함수.

    입력:
        OpenCV 이미지(NumPy 배열)

    반환:
        차량 종류, 위치, 신뢰도, 번호판 OCR 정보를
        포함한 Python 딕셔너리
    """

    # 13-1. 입력 이미지 확인
    if image is None:
        return {
            "success": False,
            "message": "이미지가 없습니다.",
            "vehicle_count": 0,
            "vehicles": []
        }

    # 13-2. 차량 탐지 실행
    vehicles, fallback_used = detect_vehicles(image)

    # 13-3. 차량이 탐지되지 않았다면 종료
    if len(vehicles) == 0:
        return {
            "success": False,
            "message": "차량을 찾지 못했습니다.",
            "vehicle_fallback_used": fallback_used,
            "vehicle_count": 0,
            "vehicles": []
        }

    # 13-4. 차량별 번호판 인식 결과 저장
    vehicle_results = []

    # enumerate(start=1):
    # 차량 리스트에 1부터 시작하는 번호를 붙여 반복
    for index, vehicle in enumerate(vehicles, start=1):

        # 탐지된 차량 영역 좌표
        vx1, vy1, vx2, vy2 = vehicle["box"]

        # 13-5. 원본 이미지에서 차량 영역 추출
        vehicle_crop = image[vy1:vy2, vx1:vx2]

        # 13-6. 결과 딕셔너리 기본값 설정
        # 번호판을 찾지 못하더라도 차량 정보는 반환
        vehicle_data = {
            "vehicle_index": index,
            "vehicle_type": vehicle["class_name"],
            "vehicle_confidence": round(
                vehicle["confidence"], 4
            ),
            "vehicle_box": {
                "x1": vx1,
                "y1": vy1,
                "x2": vx2,
                "y2": vy2
            },
            "plate_detected": False,
            "plate_confidence": None,
            "plate_number": "",
            "plate_type": "NOT_DETECTED",
            "first_ocr": "",
            "first_type": "",
            "retry_ocr": "",
            "retry_type": "",
            "review_reasons": plate_review_reasons("", "NOT_DETECTED")
        }

        # 13-7. 차량 영역 추출에 실패하면 다음 차량 처리
        if vehicle_crop.size == 0:
            vehicle_results.append(vehicle_data)
            continue

        # 13-8. 차량 내부에서 번호판 탐지
        plate = detect_best_plate(vehicle_crop)

        # 번호판이 없으면 기본 결과를 저장
        if plate is None:
            vehicle_results.append(vehicle_data)
            continue

        # 번호판 탐지 성공 여부 및 신뢰도 저장
        vehicle_data["plate_detected"] = True
        vehicle_data["plate_confidence"] = round(
            plate["confidence"], 4
        )

        # 13-9. 원본 이미지에서 번호판 영역 추출
        plate_crop = crop_plate_from_original(
            image,
            vehicle["box"],
            plate["box"],
            margin_ratio=0.10
        )

        # 번호판 영역을 잘라내지 못한 경우
        if plate_crop.size == 0:
            vehicle_data["plate_type"] = "CROP_FAILED"
            vehicle_data["review_reasons"] = plate_review_reasons("", "CROP_FAILED")
            vehicle_results.append(vehicle_data)
            continue

        # 13-10. 번호판 OCR 수행
        ocr_result = recognize_plate(plate_crop)

        # 13-11. OCR 결과를 차량 정보에 추가
        # update(): 다른 딕셔너리의 항목을 현재 딕셔너리에 병합
        # 기존 코드와 동일한 6개 OCR 필드가 추가됨
        vehicle_data.update(ocr_result)

        vehicle_results.append(vehicle_data)

    # 13-12. 모든 차량의 결과 반환
    return {
        "success": True,
        "message": "차량 인식 처리가 완료되었습니다.",
        "vehicle_fallback_used": fallback_used,
        "vehicle_count": len(vehicle_results),
        "vehicles": vehicle_results
    }

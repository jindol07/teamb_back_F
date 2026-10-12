# AI 담당 코드
# 함수를 분리하는 이유 : 책임 분리

from ultralytics import YOLO
from paddleocr import PaddleOCR

import cv2
import os
import re
import tempfile
import unicodedata


# =========================================================
# 1. 모델 경로
# =========================================================

VEHICLE_MODEL_PATH = "models/yolo11n.pt"

PLATE_MODEL_PATH = (
    "models/license_plate_yolov8n.pt"
)


# =========================================================
# 2. 차량 클래스
# =========================================================

VEHICLE_CLASSES = {
    "car",
    "truck",
    "bus",
    "motorcycle"
}


# =========================================================
# 3. 모델 로딩
# =========================================================
# 
# API 요청이 올 때마다 모델을 새로 로딩하면
# 너무 느립니다.
#
# recognizer.py가 처음 import될 때 딱 한 번만
# 모델을 메모리에 올립니다.
#
# =========================================================

print("=== AI 모델 로딩 시작 ===")


vehicle_model = YOLO(
    VEHICLE_MODEL_PATH
)


plate_model = YOLO(
    PLATE_MODEL_PATH
)


paddle_ocr = PaddleOCR(
    lang="korean",

    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,

    enable_mkldnn=False
)


print("=== AI 모델 로딩 완료 ===")


# =========================================================
# 4. 번호판 문자열 정규화
# =========================================================

def normalize_plate_text(text):
    """
    OCR 결과를 비교하거나 반환하기 좋은 형태로 정리한다.
    """

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFC",
        text
    )

    text = text.strip()

    text = re.sub(
        r"\s+",
        "",
        text
    )

    text = text.upper()

    return text


# =========================================================
# 5. 번호판 형식 판정
# =========================================================

def classify_plate_format(text):
    """
    OCR 결과를 번호판 형태에 따라 분류한다.

    KOREAN_VALID
        일반적인 한국 번호판 형식

    FOREIGN_OR_OTHER
        영문자가 포함된 외국/기타 번호판

    REVIEW
        읽기는 했지만 형식이 불확실

    OCR_FAILED
        OCR 자체 실패
    """

    if not text:
        return "OCR_FAILED"


    korean_pattern = (
        r"^\d{2,3}[가-힣]\d{4}$"
    )


    if re.fullmatch(
        korean_pattern,
        text
    ):
        return "KOREAN_VALID"


    foreign_pattern = (
        r"^(?=.*[A-Z])[A-Z0-9]{4,10}$"
    )


    if re.fullmatch(
        foreign_pattern,
        text
    ):
        return "FOREIGN_OR_OTHER"


    return "REVIEW"


# =========================================================
# 6. OCR 결과 후처리
# =========================================================

def cleanup_plate_text(text):
    """
    OCR이 번호판 사이에 잘못 넣은
    일부 특수문자를 안전하게 제거한다.

    예:
    52누·7764
        ↓
    52누7764

    단, 제거 결과가 정상적인 한국 번호판 형식일 때만
    수정 결과를 사용한다.
    """

    if not text:
        return ""

    original_text = normalize_plate_text(
        text
    )


    cleaned_text = re.sub(
        r"[·•ㆍ:.\-_]",
        "",
        original_text
    )


    korean_pattern = (
        r"^\d{2,3}[가-힣]\d{4}$"
    )


    if re.fullmatch(
        korean_pattern,
        cleaned_text
    ):
        return cleaned_text


    return original_text


# =========================================================
# 7. PaddleOCR 실행 함수
# =========================================================

def run_paddleocr(image):
    """
    OpenCV 이미지(numpy 배열)를 받아 PaddleOCR을 실행한다.

    현재 환경에서 이미 검증된 방식대로
    임시 이미지 파일을 만들어 PaddleOCR에 전달한다.

    API에서는 요청 이미지마다 영구 파일을 만들 필요가
    없으므로 TemporaryDirectory를 사용한다.
    """

    if image is None or image.size == 0:
        return ""


    with tempfile.TemporaryDirectory() as temp_dir:

        temp_path = os.path.join(
            temp_dir,
            "ocr_input.jpg"
        )


        cv2.imwrite(
            temp_path,
            image
        )


        results = paddle_ocr.predict(
            temp_path
        )


        texts = []


        for item in results:

            texts.extend(
                item["rec_texts"]
            )


        text = "".join(
            texts
        )


    return normalize_plate_text(
        text
    )


# =========================================================
# 8. 원본 이미지 기준 번호판 Crop
# =========================================================

def crop_plate_from_original(
    original_image,
    vehicle_box,
    plate_box,
    margin_ratio=0.10
):
    """
    차량 Crop 안에서 구한 번호판 좌표를
    다시 원본 이미지 좌표로 바꿔서 번호판을 자른다.

    중간에 저장된 차량 JPEG에서 다시 Crop하지 않고
    원본 이미지에서 바로 잘라 화질 손실을 줄인다.
    """

    vx1, vy1, vx2, vy2 = vehicle_box

    px1, py1, px2, py2 = plate_box


    # 차량 내부 좌표
    # →
    # 원본 이미지 좌표
    gx1 = vx1 + px1
    gy1 = vy1 + py1

    gx2 = vx1 + px2
    gy2 = vy1 + py2


    plate_width = gx2 - gx1
    plate_height = gy2 - gy1


    margin_x = int(
        plate_width * margin_ratio
    )

    margin_y = int(
        plate_height * margin_ratio
    )


    image_height, image_width = (
        original_image.shape[:2]
    )


    gx1 = max(
        0,
        gx1 - margin_x
    )

    gy1 = max(
        0,
        gy1 - margin_y
    )

    gx2 = min(
        image_width,
        gx2 + margin_x
    )

    gy2 = min(
        image_height,
        gy2 + margin_y
    )


    return original_image[
        gy1:gy2,
        gx1:gx2
    ]


# =========================================================
# 9. 2차 OCR 함수
# =========================================================

def retry_ocr(plate_crop):
    """
    첫 OCR 결과가 REVIEW/OCR_FAILED이면
    번호판 이미지를 전처리한 뒤 OCR을 다시 실행한다.
    """

    if plate_crop is None:
        return "", "OCR_FAILED"


    if plate_crop.size == 0:
        return "", "OCR_FAILED"


    height, width = (
        plate_crop.shape[:2]
    )


    # 4배 확대
    enlarged = cv2.resize(
        plate_crop,
        (
            width * 4,
            height * 4
        ),
        interpolation=cv2.INTER_CUBIC
    )


    # 흑백 변환
    gray = cv2.cvtColor(
        enlarged,
        cv2.COLOR_BGR2GRAY
    )


    # 대비 향상
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )


    enhanced = clahe.apply(
        gray
    )


    retry_text = run_paddleocr(
        enhanced
    )


    retry_type = classify_plate_format(
        retry_text
    )


    return retry_text, retry_type


# =========================================================
# 10. 차량 탐지 함수
# =========================================================

def detect_vehicles(image):
    """
    이미지에서 차량을 찾는다.

    1차:
        conf=0.5

    차량이 하나도 없다면:
        conf=0.3으로 한 번 더 탐지

    반환:
        차량 정보 리스트
    """

    results = vehicle_model(
        image,
        conf=0.5,
        verbose=False
    )


    vehicles = []


    # -----------------------------------------------------
    # 결과를 차량 리스트로 변환
    # -----------------------------------------------------

    for result in results:

        for box in result.boxes:

            class_id = int(
                box.cls[0]
            )


            class_name = vehicle_model.names[
                class_id
            ]


            if class_name not in VEHICLE_CLASSES:
                continue


            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0]
            )


            confidence = float(
                box.conf[0]
            )


            vehicles.append(
                {
                    "class_name": class_name,
                    "confidence": confidence,

                    "box": (
                        x1,
                        y1,
                        x2,
                        y2
                    )
                }
            )


    # -----------------------------------------------------
    # 차량을 하나도 못 찾았으면
    # confidence를 낮춰 재탐지
    # -----------------------------------------------------

    fallback_used = False


    if len(vehicles) == 0:

        fallback_used = True


        results = vehicle_model(
            image,
            conf=0.3,
            verbose=False
        )


        for result in results:

            for box in result.boxes:

                class_id = int(
                    box.cls[0]
                )


                class_name = (
                    vehicle_model.names[
                        class_id
                    ]
                )


                if (
                    class_name
                    not in VEHICLE_CLASSES
                ):
                    continue


                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0]
                )


                confidence = float(
                    box.conf[0]
                )


                vehicles.append(
                    {
                        "class_name":
                            class_name,

                        "confidence":
                            confidence,

                        "box": (
                            x1,
                            y1,
                            x2,
                            y2
                        )
                    }
                )


    return vehicles, fallback_used


# =========================================================
# 11. 번호판 탐지 함수
# =========================================================

def detect_best_plate(vehicle_crop):
    """
    차량 이미지에서 번호판을 탐지한다.

    여러 후보가 나오면 confidence가 가장 높은
    번호판 하나만 반환한다.
    """

    results = plate_model(
        vehicle_crop,
        conf=0.25,
        verbose=False
    )


    candidates = []


    for result in results:

        for box in result.boxes:

            candidates.append(
                box
            )


    if len(candidates) == 0:
        return None


    best_box = max(
        candidates,
        key=lambda box: float(
            box.conf[0]
        )
    )


    x1, y1, x2, y2 = map(
        int,
        best_box.xyxy[0]
    )


    confidence = float(
        best_box.conf[0]
    )


    return {
        "confidence": confidence,

        "box": (
            x1,
            y1,
            x2,
            y2
        )
    }


# =========================================================
# 12. 번호판 OCR 전체 처리 함수
# =========================================================

def recognize_plate(plate_crop):
    """
    하나의 번호판 이미지를 받아서:

    1차 PaddleOCR
        ↓
    필요하면 2차 PaddleOCR
        ↓
    문자열 후처리
        ↓
    최종 번호판 반환
    """

    # -----------------------------------------------------
    # 1차 OCR
    # -----------------------------------------------------

    first_text = run_paddleocr(
        plate_crop
    )


    first_type = classify_plate_format(
        first_text
    )


    retry_text = ""
    retry_type = ""


    # -----------------------------------------------------
    # 기본적으로 1차 결과를 최종 후보로 둔다.
    # -----------------------------------------------------

    final_text = first_text
    final_type = first_type


    # -----------------------------------------------------
    # REVIEW / OCR_FAILED만 2차 OCR
    # -----------------------------------------------------

    if first_type in {
        "REVIEW",
        "OCR_FAILED"
    }:

        (
            retry_text,
            retry_type
        ) = retry_ocr(
            plate_crop
        )


        # 2차 결과가 정상 번호판 형태라면 채택
        if retry_type in {
            "KOREAN_VALID",
            "FOREIGN_OR_OTHER"
        }:

            final_text = retry_text
            final_type = retry_type


    # -----------------------------------------------------
    # 문자열 후처리
    # -----------------------------------------------------

    final_text = cleanup_plate_text(
        final_text
    )


    final_type = classify_plate_format(
        final_text
    )


    return {
        "first_ocr": first_text,
        "first_type": first_type,

        "retry_ocr": retry_text,
        "retry_type": retry_type,

        "plate_number": final_text,
        "plate_type": final_type
    }


# =========================================================
# 13. 전체 차량 번호판 인식 함수
# =========================================================

def recognize_image(image):
    """
    FastAPI가 호출하게 될 핵심 함수.

    입력:
        OpenCV 이미지

    출력:
        차량/번호판 인식 결과 Dictionary
    """

    if image is None:

        return {
            "success": False,
            "message": "이미지가 없습니다.",
            "vehicle_count": 0,
            "vehicles": []
        }


    # =====================================================
    # 차량 탐지
    # =====================================================

    (
        vehicles,
        fallback_used
    ) = detect_vehicles(
        image
    )


    # 차량 자체를 못 찾은 경우
    if len(vehicles) == 0:

        return {
            "success": False,

            "message":
                "차량을 찾지 못했습니다.",

            "vehicle_fallback_used":
                fallback_used,

            "vehicle_count": 0,

            "vehicles": []
        }


    vehicle_results = []


    # =====================================================
    # 탐지 차량별 번호판 처리
    # =====================================================

    for index, vehicle in enumerate(
        vehicles,
        start=1
    ):

        vx1, vy1, vx2, vy2 = (
            vehicle["box"]
        )


        vehicle_crop = image[
            vy1:vy2,
            vx1:vx2
        ]


        vehicle_data = {
            "vehicle_index": index,

            "vehicle_type":
                vehicle["class_name"],

            "vehicle_confidence":
                round(
                    vehicle["confidence"],
                    4
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
            "retry_type": ""
        }


        # -------------------------------------------------
        # 차량 Crop 실패
        # -------------------------------------------------

        if vehicle_crop.size == 0:

            vehicle_results.append(
                vehicle_data
            )

            continue


        # =================================================
        # 번호판 탐지
        # =================================================

        plate = detect_best_plate(
            vehicle_crop
        )


        if plate is None:

            vehicle_results.append(
                vehicle_data
            )

            continue


        vehicle_data[
            "plate_detected"
        ] = True


        vehicle_data[
            "plate_confidence"
        ] = round(
            plate["confidence"],
            4
        )


        # =================================================
        # 원본에서 번호판 Crop
        # =================================================

        plate_crop = crop_plate_from_original(
            image,

            vehicle["box"],

            plate["box"],

            margin_ratio=0.10
        )


        if plate_crop.size == 0:

            vehicle_data[
                "plate_type"
            ] = "CROP_FAILED"


            vehicle_results.append(
                vehicle_data
            )

            continue


        # =================================================
        # OCR
        # =================================================

        ocr_result = recognize_plate(
            plate_crop
        )


        vehicle_data[
            "first_ocr"
        ] = ocr_result[
            "first_ocr"
        ]


        vehicle_data[
            "first_type"
        ] = ocr_result[
            "first_type"
        ]


        vehicle_data[
            "retry_ocr"
        ] = ocr_result[
            "retry_ocr"
        ]


        vehicle_data[
            "retry_type"
        ] = ocr_result[
            "retry_type"
        ]


        vehicle_data[
            "plate_number"
        ] = ocr_result[
            "plate_number"
        ]


        vehicle_data[
            "plate_type"
        ] = ocr_result[
            "plate_type"
        ]


        vehicle_results.append(
            vehicle_data
        )


    # =====================================================
    # 최종 반환
    # =====================================================

    return {
        "success": True,

        "message":
            "차량 인식 처리가 완료되었습니다.",

        "vehicle_fallback_used":
            fallback_used,

        "vehicle_count":
            len(vehicle_results),

        "vehicles":
            vehicle_results
    }
from ultralytics import YOLO
from paddleocr import PaddleOCR

import cv2
import os
import glob
import re
import unicodedata
import pandas as pd


# =========================================================
# 1. 모델 경로
# =========================================================

VEHICLE_MODEL_PATH = "models/yolo11n.pt"
PLATE_MODEL_PATH = "models/license_plate_yolov8n.pt"


# =========================================================
# 2. 테스트 이미지 정답
# =========================================================
#
# key   : 이미지 파일명에서 확장자를 제외한 이름
# value : 실제 번호판
#
# 예:
# car6.png → "car6"
#
# =========================================================

GROUND_TRUTH = {
    "car": "10누1557",
    "car2": "32부5178",
    "car3": "1146NMC",
    "car4": "97소3698",
    "car5": "10호8904",
    "car6": "12가3456",
    "car7": "123나4567",
    "car8": "28부9345",
    "car9": "52누7764",
    "car10": "41모2489",
    "car11": "67다9812",
    "car12": "91소6408",
    "car13": "7BC3941",
    "car14": "1146NMC",
    "car15": "ABC1234",
    "car16": "45루1234",
    "car17": "83가6201",
    "car18": "56허9082",
    "car19": "8BC2147",
    "car20": "203저7715",
    "car21": "7NM4281",
}


# =========================================================
# 3. 각 이미지에서 평가 대상 차량 번호
# =========================================================
#
# YOLO가 찾은 차량 중 몇 번째 차량을
# 해당 이미지의 정답 차량으로 볼 것인지 지정한다.
#
# 예:
# car.jpg에서 정답 차량은 두 번째 탐지 차량 → 2
#
# car17은 실제 번호판 차량이 3번째 탐지 차량 → 3
#
# =========================================================

TARGET_VEHICLE = {
    "car": 2,
    "car2": 2,
    "car3": 1,
    "car4": 1,
    "car5": 1,
    "car6": 1,
    "car7": 1,
    "car8": 1,
    "car9": 1,
    "car10": 1,
    "car11": 1,
    "car12": 1,
    "car13": 1,
    "car14": 1,
    "car15": 1,
    "car16": 1,
    "car17": 3,
    "car18": 1,
    "car19": 1,
    "car20": 1,
    "car21": 1,
}


# =========================================================
# 4. YOLO 차량 클래스
# =========================================================

VEHICLE_CLASSES = {
    "car",
    "truck",
    "bus",
    "motorcycle"
}


# =========================================================
# 5. 모델 로딩
# =========================================================

print("=== 모델 로딩 시작 ===")


# 차량 탐지용 YOLO11
vehicle_model = YOLO(
    VEHICLE_MODEL_PATH
)


# 번호판 탐지용 YOLO 모델
plate_model = YOLO(
    PLATE_MODEL_PATH
)


# 번호판 OCR용 PaddleOCR
paddle_ocr = PaddleOCR(
    lang="korean",

    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,

    # 이전에 현재 PC 환경에서
    # oneDNN 오류가 발생했기 때문에 False 유지
    enable_mkldnn=False
)


print("=== 모델 로딩 완료 ===")


# =========================================================
# 6. OCR 문자열 정규화
# =========================================================

def normalize_plate_text(text):
    """
    OCR 결과를 비교하기 좋은 형태로 정리한다.

    1. 한글 Unicode NFC 정규화
    2. 앞뒤 공백 제거
    3. 문자열 안의 모든 공백 제거
    4. 영문은 대문자로 통일
    """

    if not text:
        return ""

    # 한글 자모 정규화
    text = unicodedata.normalize(
        "NFC",
        text
    )

    # 양쪽 공백 제거
    text = text.strip()

    # 문자열 내부 공백 모두 제거
    text = re.sub(
        r"\s+",
        "",
        text
    )

    # 영문 대문자 통일
    text = text.upper()

    return text


# =========================================================
# 7. 번호판 형식 분류
# =========================================================

def classify_plate_format(text):
    """
    OCR 문자열의 형태를 분류한다.

    반환값

    KOREAN_VALID
        일반적인 한국 번호판 형식

    FOREIGN_OR_OTHER
        영문자가 포함된 외국/기타 번호판 후보

    REVIEW
        OCR 결과는 있으나 형식이 불확실

    OCR_FAILED
        문자 인식 자체 실패
    """

    if not text:
        return "OCR_FAILED"


    # -----------------------------------------------------
    # 일반적인 한국 번호판
    #
    # 예:
    # 12가3456
    # 123나4567
    # 97소3698
    #
    # -----------------------------------------------------

    korean_pattern = (
        r"^\d{2,3}[가-힣]\d{4}$"
    )

    if re.fullmatch(
        korean_pattern,
        text
    ):
        return "KOREAN_VALID"


    # -----------------------------------------------------
    # 외국/기타 번호판
    #
    # 영문자가 최소 하나는 포함되어야 한다.
    #
    # ABC1234 → 가능
    # 7NM4281 → 가능
    # 1234567 → 불가
    #
    # -----------------------------------------------------

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
# 8. OCR 결과 후처리
# =========================================================

def cleanup_plate_text(text):
    """
    OCR 결과에 잘못 삽입된 특수문자를 제거해 본다.

    단, 특수문자를 제거한 결과가
    정상적인 한국 번호판 형식이 될 때만
    보정 결과를 채택한다.

    예:

    52누·7764
        ↓
    52누7764
        ↓
    KOREAN_VALID

    반면

    10-15574
        ↓
    1015574

    는 한국 번호판 형식이 아니므로
    원래 OCR 결과를 유지한다.
    """

    if not text:
        return ""

    original_text = normalize_plate_text(
        text
    )


    # OCR에서 번호판 중간에 잘못 생성될 수 있는
    # 일부 특수문자 제거
    cleaned_text = re.sub(
        r"[·•ㆍ:.\-_]",
        "",
        original_text
    )


    korean_pattern = (
        r"^\d{2,3}[가-힣]\d{4}$"
    )


    # 특수문자 제거 결과가 정상적인
    # 한국 번호판일 때만 채택
    if re.fullmatch(
        korean_pattern,
        cleaned_text
    ):
        return cleaned_text


    # 그렇지 않으면 원본 OCR 결과 유지
    return original_text


# =========================================================
# 9. 원본 이미지 기준 번호판 Crop
# =========================================================

def crop_plate_from_original(
    original_image,
    vehicle_box,
    plate_box,
    margin_ratio=0.10
):
    """
    차량 Crop에서 얻은 번호판 좌표를
    원본 이미지 좌표로 다시 변환한다.

    그리고 원본 이미지에서 번호판을 직접 Crop한다.

    margin_ratio=0.10
        번호판 주변에 약 10% 여백 추가
    """

    vx1, vy1, vx2, vy2 = vehicle_box
    px1, py1, px2, py2 = plate_box


    # -----------------------------------------------------
    # 차량 내부 좌표 → 원본 이미지 좌표
    # -----------------------------------------------------

    gx1 = vx1 + px1
    gy1 = vy1 + py1

    gx2 = vx1 + px2
    gy2 = vy1 + py2


    # 번호판 원래 크기
    plate_width = gx2 - gx1
    plate_height = gy2 - gy1


    # -----------------------------------------------------
    # 여백 계산
    # -----------------------------------------------------

    margin_x = int(
        plate_width * margin_ratio
    )

    margin_y = int(
        plate_height * margin_ratio
    )


    # 원본 이미지 크기
    image_height, image_width = (
        original_image.shape[:2]
    )


    # -----------------------------------------------------
    # 번호판 주변에 여백 적용
    #
    # max/min을 사용하는 이유:
    # 이미지 밖으로 좌표가 넘어가지 않도록 한다.
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # 원본 이미지에서 번호판 직접 Crop
    # -----------------------------------------------------

    plate_crop = original_image[
        gy1:gy2,
        gx1:gx2
    ]

    return plate_crop


# =========================================================
# 10. PaddleOCR 실행 함수
# =========================================================

def run_paddleocr(image_path):
    """
    번호판 이미지를 PaddleOCR로 인식한다.
    """

    results = paddle_ocr.predict(
        image_path
    )

    texts = []


    for item in results:

        texts.extend(
            item["rec_texts"]
        )


    # 한 번호판에서 여러 문자 영역이 나온 경우
    # 하나의 문자열로 결합
    text = "".join(
        texts
    )


    return normalize_plate_text(
        text
    )


# =========================================================
# 11. 2차 OCR
# =========================================================

def retry_ocr(
    plate_crop,
    result_dir,
    vehicle_count,
    plate_count
):
    """
    1차 OCR이 REVIEW 또는 OCR_FAILED인 경우 실행한다.

    처리 순서:

    번호판
      ↓
    4배 확대
      ↓
    GrayScale
      ↓
    CLAHE 대비 강화
      ↓
    PaddleOCR 재실행
    """

    height, width = (
        plate_crop.shape[:2]
    )


    # -----------------------------------------------------
    # 4배 확대
    # -----------------------------------------------------

    enlarged = cv2.resize(
        plate_crop,
        (
            width * 4,
            height * 4
        ),
        interpolation=cv2.INTER_CUBIC
    )


    # -----------------------------------------------------
    # GrayScale
    # -----------------------------------------------------

    gray = cv2.cvtColor(
        enlarged,
        cv2.COLOR_BGR2GRAY
    )


    # -----------------------------------------------------
    # CLAHE
    #
    # 이미지 전체를 똑같이 밝게 하는 것이 아니라
    # 지역별 대비를 강화한다.
    # -----------------------------------------------------

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )


    enhanced = clahe.apply(
        gray
    )


    # -----------------------------------------------------
    # 전처리 결과 저장
    # -----------------------------------------------------

    retry_path = os.path.join(
        result_dir,
        f"plate_{vehicle_count}_{plate_count}_retry.jpg"
    )


    cv2.imwrite(
        retry_path,
        enhanced
    )


    # -----------------------------------------------------
    # OCR 재실행
    # -----------------------------------------------------

    retry_text = run_paddleocr(
        retry_path
    )


    retry_type = classify_plate_format(
        retry_text
    )


    return (
        retry_text,
        retry_type,
        retry_path
    )


# =========================================================
# 12. 테스트 이미지 가져오기
# =========================================================

image_paths = []

image_paths.extend(
    glob.glob(
        "test_images/*.jpg"
    )
)

image_paths.extend(
    glob.glob(
        "test_images/*.jpeg"
    )
)

image_paths.extend(
    glob.glob(
        "test_images/*.png"
    )
)


# =========================================================
# 13. 자연스러운 파일명 순서 정렬
# =========================================================
#
# 일반 sort()를 사용하면:
#
# car
# car10
# car11
# ...
# car2
#
# 순서가 될 수 있다.
#
# 아래 함수는 숫자를 숫자로 인식해서:
#
# car
# car2
# car3
# ...
# car10
#
# 순서로 정렬한다.
#
# =========================================================

def natural_sort_key(path):

    file_name = os.path.basename(
        path
    )

    return [
        int(text)
        if text.isdigit()
        else text.lower()

        for text in re.split(
            r"(\d+)",
            file_name
        )
    ]


image_paths.sort(
    key=natural_sort_key
)


if len(image_paths) == 0:

    raise FileNotFoundError(
        "test_images 폴더에 테스트 이미지가 없습니다."
    )


print(
    f"\n테스트 이미지 개수: "
    f"{len(image_paths)}"
)


# =========================================================
# 14. 평가 결과 저장 리스트
# =========================================================

evaluation_results = []


# =========================================================
# 15. 이미지 하나씩 처리
# =========================================================

for image_path in image_paths:

    print(
        "\n==================================="
    )

    print(
        f"처리 이미지: {image_path}"
    )

    print(
        "==================================="
    )


    # -----------------------------------------------------
    # 이미지 이름
    #
    # test_images/car6.png
    # → car6
    # -----------------------------------------------------

    image_name = os.path.splitext(
        os.path.basename(
            image_path
        )
    )[0]


    # -----------------------------------------------------
    # 해당 이미지 정답
    # -----------------------------------------------------

    ground_truth = GROUND_TRUTH.get(
        image_name
    )


    # -----------------------------------------------------
    # 평가 대상 차량 번호
    # -----------------------------------------------------

    target_vehicle = TARGET_VEHICLE.get(
        image_name
    )


    # -----------------------------------------------------
    # 이미지별 평가 상태 초기화
    # -----------------------------------------------------

    target_vehicle_found = False
    target_plate_found = False

    first_ocr_correct = False
    final_ocr_correct = False


    # -----------------------------------------------------
    # 평가 결과 기본값
    #
    # 중간 단계에서 실패해도
    # 반드시 Excel에 한 행을 남기기 위해 만든다.
    # -----------------------------------------------------

    evaluation_record = {
        "이미지": image_name,

        "대상차량번호": (
            target_vehicle
            if target_vehicle is not None
            else ""
        ),

        "차량종류": "",

        "차량탐지성공": "FAIL",
        "번호판탐지성공": "FAIL",

        "차량신뢰도": "",
        "번호판신뢰도": "",

        "번호판너비": "",
        "번호판높이": "",

        "정답번호판": (
            normalize_plate_text(
                ground_truth
            )
            if ground_truth
            else ""
        ),

        "1차OCR": "",
        "1차판정": "",
        "1차OCR정답여부": "FAIL",

        "2차OCR": "",
        "2차판정": "",

        "최종OCR": "",
        "최종판정": "",

        "최종OCR정답여부": "FAIL",

        "전체파이프라인": "FAIL"
    }


    # -----------------------------------------------------
    # 결과 저장 폴더
    # -----------------------------------------------------

    result_dir = os.path.join(
        "results",
        "pipeline",
        image_name
    )


    os.makedirs(
        result_dir,
        exist_ok=True
    )


    # -----------------------------------------------------
    # 원본 이미지 읽기
    # -----------------------------------------------------

    original_image = cv2.imread(
        image_path
    )


    if original_image is None:

        print(
            "이미지를 읽을 수 없습니다."
        )

        evaluation_record[
            "최종판정"
        ] = "IMAGE_READ_FAILED"

        evaluation_results.append(
            evaluation_record
        )

        continue


    # =====================================================
    # 16. 차량 탐지 - 1차 conf=0.5
    # =====================================================

    vehicle_results = vehicle_model(
        image_path,
        conf=0.5
    )


    # -----------------------------------------------------
    # 실제 차량 클래스 개수 확인
    # -----------------------------------------------------

    detected_vehicle_count = 0


    for result in vehicle_results:

        for box in result.boxes:

            class_id = int(
                box.cls[0]
            )

            class_name = vehicle_model.names[
                class_id
            ]


            if class_name in VEHICLE_CLASSES:

                detected_vehicle_count += 1


    # =====================================================
    # 17. 차량 미탐지 시 conf=0.3 fallback
    # =====================================================

    if detected_vehicle_count == 0:

        print(
            "1차 차량 탐지 실패 "
            "→ conf=0.3으로 재탐지"
        )


        vehicle_results = vehicle_model(
            image_path,
            conf=0.3
        )


    # =====================================================
    # 18. 차량 탐지 결과 처리
    # =====================================================

    vehicle_count = 0


    for vehicle_result in vehicle_results:

        for vehicle_box in vehicle_result.boxes:


            class_id = int(
                vehicle_box.cls[0]
            )


            class_name = vehicle_model.names[
                class_id
            ]


            # 차량 클래스가 아니면 무시
            if class_name not in VEHICLE_CLASSES:
                continue


            vehicle_count += 1


            vehicle_confidence = float(
                vehicle_box.conf[0]
            )


            vx1, vy1, vx2, vy2 = map(
                int,
                vehicle_box.xyxy[0]
            )


            print(
                f"\n차량 {vehicle_count}"
            )

            print(
                f"종류: {class_name}"
            )

            print(
                f"차량 신뢰도: "
                f"{vehicle_confidence:.4f}"
            )


            # -------------------------------------------------
            # 현재 차량이 평가 대상 차량인지 확인
            # -------------------------------------------------

            is_target_vehicle = (
                ground_truth is not None
                and target_vehicle == vehicle_count
            )


            if is_target_vehicle:

                target_vehicle_found = True

                evaluation_record[
                    "차량탐지성공"
                ] = "PASS"

                evaluation_record[
                    "차량종류"
                ] = class_name

                evaluation_record[
                    "차량신뢰도"
                ] = round(
                    vehicle_confidence,
                    4
                )


            # =================================================
            # 19. 차량 Crop
            # =================================================

            vehicle_crop = original_image[
                vy1:vy2,
                vx1:vx2
            ]


            if vehicle_crop.size == 0:

                print(
                    "차량 Crop 실패"
                )

                continue


            vehicle_crop_path = os.path.join(
                result_dir,
                f"vehicle_{vehicle_count}.jpg"
            )


            cv2.imwrite(
                vehicle_crop_path,
                vehicle_crop
            )


            # =================================================
            # 20. 번호판 탐지
            # =================================================

            plate_results = plate_model(
                vehicle_crop,
                conf=0.25
            )


            # -------------------------------------------------
            # 모든 번호판 후보를 리스트로 모은다.
            # -------------------------------------------------

            plate_candidates = []


            for plate_result in plate_results:

                for plate_box in plate_result.boxes:

                    plate_candidates.append(
                        plate_box
                    )


            # -------------------------------------------------
            # 번호판 후보가 없다면
            # -------------------------------------------------

            if len(plate_candidates) == 0:

                print(
                    "번호판을 찾지 못했습니다."
                )

                # 평가 대상 차량인데 번호판을 못 찾은 경우
                if is_target_vehicle:

                    evaluation_record[
                        "최종판정"
                    ] = "PLATE_NOT_DETECTED"

                continue


            # -------------------------------------------------
            # 한 차량에서 여러 번호판 후보가 발견되는 경우
            # 가장 신뢰도가 높은 번호판 하나만 사용한다.
            #
            # 이전 합성 이미지에서
            # 다른 글자를 번호판으로 오탐한 사례를 줄이기 위함.
            # -------------------------------------------------

            best_plate_box = max(
                plate_candidates,
                key=lambda box: float(
                    box.conf[0]
                )
            )


            plate_count = 1


            plate_confidence = float(
                best_plate_box.conf[0]
            )


            px1, py1, px2, py2 = map(
                int,
                best_plate_box.xyxy[0]
            )


            print(
                f"번호판 {plate_count}"
            )

            print(
                f"번호판 신뢰도: "
                f"{plate_confidence:.4f}"
            )


            # -------------------------------------------------
            # 평가 대상 차량에서 번호판 탐지 성공
            # -------------------------------------------------

            if is_target_vehicle:

                target_plate_found = True

                evaluation_record[
                    "번호판탐지성공"
                ] = "PASS"

                evaluation_record[
                    "번호판신뢰도"
                ] = round(
                    plate_confidence,
                    4
                )


            # =================================================
            # 21. 원본 이미지에서 번호판 Crop
            # =================================================

            plate_crop = crop_plate_from_original(
                original_image,

                (
                    vx1,
                    vy1,
                    vx2,
                    vy2
                ),

                (
                    px1,
                    py1,
                    px2,
                    py2
                ),

                margin_ratio=0.10
            )


            if plate_crop.size == 0:

                print(
                    "번호판 Crop 실패"
                )

                if is_target_vehicle:

                    evaluation_record[
                        "최종판정"
                    ] = "PLATE_CROP_FAILED"

                continue


            plate_height, plate_width = (
                plate_crop.shape[:2]
            )


            print(
                f"번호판 크기: "
                f"{plate_width} x {plate_height}"
            )


            # -------------------------------------------------
            # 번호판 이미지 저장
            # -------------------------------------------------

            plate_crop_path = os.path.join(
                result_dir,
                f"plate_{vehicle_count}_{plate_count}.jpg"
            )


            cv2.imwrite(
                plate_crop_path,
                plate_crop
            )


            # =================================================
            # 22. 1차 OCR
            # =================================================

            recognized_text = run_paddleocr(
                plate_crop_path
            )


            plate_type = classify_plate_format(
                recognized_text
            )


            if recognized_text:

                print(
                    f"1차 OCR 결과: "
                    f"{recognized_text}"
                )

            else:

                print(
                    "1차 OCR 결과: 인식 실패"
                )


            print(
                f"1차 번호판 형식: "
                f"{plate_type}"
            )


            # -------------------------------------------------
            # 2차 OCR 기본값
            # -------------------------------------------------

            retry_text = ""
            retry_type = ""


            # =================================================
            # 23. REVIEW / OCR_FAILED → 2차 OCR
            # =================================================

            if plate_type in {
                "REVIEW",
                "OCR_FAILED"
            }:

                print(
                    "→ 2차 OCR 재시도"
                )


                (
                    retry_text,
                    retry_type,
                    retry_path
                ) = retry_ocr(
                    plate_crop,
                    result_dir,
                    vehicle_count,
                    plate_count
                )


                if retry_text:

                    print(
                        f"2차 OCR 결과: "
                        f"{retry_text}"
                    )

                else:

                    print(
                        "2차 OCR 결과: "
                        "인식 실패"
                    )


                print(
                    f"2차 번호판 형식: "
                    f"{retry_type}"
                )


                # -------------------------------------------------
                # 2차 OCR 결과가 정상 형식이면 채택
                # -------------------------------------------------

                if retry_type in {
                    "KOREAN_VALID",
                    "FOREIGN_OR_OTHER"
                }:

                    final_text = retry_text
                    final_type = retry_type

                else:

                    final_text = recognized_text
                    final_type = plate_type


            else:

                final_text = recognized_text
                final_type = plate_type


            # =================================================
            # 24. OCR 후처리
            # =================================================

            cleaned_final_text = cleanup_plate_text(
                final_text
            )


            if (
                cleaned_final_text
                != final_text
            ):

                print(
                    f"후처리 보정: "
                    f"{final_text} "
                    f"→ {cleaned_final_text}"
                )


            final_text = cleaned_final_text


            # 후처리 후 형식을 다시 판정해야 한다.
            final_type = classify_plate_format(
                final_text
            )


            # =================================================
            # 25. 최종 OCR 출력
            # =================================================

            print(
                f"최종 OCR 결과: "
                f"{final_text if final_text else '인식 실패'}"
            )


            print(
                f"최종 번호판 형식: "
                f"{final_type}"
            )


            # =================================================
            # 26. 평가 대상 차량만 성능 평가
            # =================================================

            if is_target_vehicle:

                normalized_ground_truth = (
                    normalize_plate_text(
                        ground_truth
                    )
                )


                normalized_first_text = (
                    normalize_plate_text(
                        recognized_text
                    )
                )


                normalized_final_text = (
                    normalize_plate_text(
                        final_text
                    )
                )


                # -------------------------------------------------
                # 1차 OCR 완전일치
                # -------------------------------------------------

                first_ocr_correct = (
                    normalized_first_text
                    == normalized_ground_truth
                )


                # -------------------------------------------------
                # 최종 OCR 완전일치
                # -------------------------------------------------

                final_ocr_correct = (
                    normalized_final_text
                    == normalized_ground_truth
                )


                print(
                    f"정답 번호판: "
                    f"{normalized_ground_truth}"
                )


                print(
                    f"1차 OCR 정답 여부: "
                    f"{'PASS' if first_ocr_correct else 'FAIL'}"
                )


                print(
                    f"최종 정답 여부: "
                    f"{'PASS' if final_ocr_correct else 'FAIL'}"
                )


                # -------------------------------------------------
                # 평가 레코드 업데이트
                # -------------------------------------------------

                evaluation_record[
                    "번호판너비"
                ] = plate_width


                evaluation_record[
                    "번호판높이"
                ] = plate_height


                evaluation_record[
                    "1차OCR"
                ] = recognized_text


                evaluation_record[
                    "1차판정"
                ] = plate_type


                evaluation_record[
                    "1차OCR정답여부"
                ] = (
                    "PASS"
                    if first_ocr_correct
                    else "FAIL"
                )


                evaluation_record[
                    "2차OCR"
                ] = retry_text


                evaluation_record[
                    "2차판정"
                ] = retry_type


                evaluation_record[
                    "최종OCR"
                ] = final_text


                evaluation_record[
                    "최종판정"
                ] = final_type


                evaluation_record[
                    "최종OCR정답여부"
                ] = (
                    "PASS"
                    if final_ocr_correct
                    else "FAIL"
                )


                # -------------------------------------------------
                # 전체 파이프라인 성공
                #
                # 차량 탐지
                # AND
                # 번호판 탐지
                # AND
                # OCR 최종 정답
                # -------------------------------------------------

                pipeline_success = (
                    target_vehicle_found
                    and target_plate_found
                    and final_ocr_correct
                )


                evaluation_record[
                    "전체파이프라인"
                ] = (
                    "PASS"
                    if pipeline_success
                    else "FAIL"
                )


    # =====================================================
    # 27. 이미지 단위 평가 결과 마무리
    # =====================================================

    # 차량 자체를 못 찾은 경우
    if not target_vehicle_found:

        print(
            "평가 대상 차량을 찾지 못했습니다."
        )

        evaluation_record[
            "최종판정"
        ] = "VEHICLE_NOT_DETECTED"


    # 차량은 찾았는데 번호판이 없었던 경우
    elif not target_plate_found:

        evaluation_record[
            "최종판정"
        ] = "PLATE_NOT_DETECTED"


    # -----------------------------------------------------
    # 정답이 등록된 이미지만 평가 결과에 추가
    # -----------------------------------------------------

    if ground_truth is not None:

        evaluation_results.append(
            evaluation_record
        )


# =========================================================
# 28. 평가 DataFrame 생성
# =========================================================

df = pd.DataFrame(
    evaluation_results
)


# 결과 폴더 생성
os.makedirs(
    "results",
    exist_ok=True
)


# =========================================================
# 29. 단계별 성공 수 계산
# =========================================================

total_count = len(
    evaluation_results
)


vehicle_success_count = sum(
    1
    for result in evaluation_results
    if result["차량탐지성공"] == "PASS"
)


plate_success_count = sum(
    1
    for result in evaluation_results
    if result["번호판탐지성공"] == "PASS"
)


first_ocr_success_count = sum(
    1
    for result in evaluation_results
    if result["1차OCR정답여부"] == "PASS"
)


final_ocr_success_count = sum(
    1
    for result in evaluation_results
    if result["최종OCR정답여부"] == "PASS"
)


pipeline_success_count = sum(
    1
    for result in evaluation_results
    if result["전체파이프라인"] == "PASS"
)


# =========================================================
# 30. 단계별 성공률 계산
# =========================================================

if total_count > 0:

    vehicle_accuracy = (
        vehicle_success_count
        / total_count
        * 100
    )


    plate_accuracy = (
        plate_success_count
        / total_count
        * 100
    )


    first_ocr_accuracy = (
        first_ocr_success_count
        / total_count
        * 100
    )


    final_ocr_accuracy = (
        final_ocr_success_count
        / total_count
        * 100
    )


    pipeline_accuracy = (
        pipeline_success_count
        / total_count
        * 100
    )


else:

    vehicle_accuracy = 0.0
    plate_accuracy = 0.0
    first_ocr_accuracy = 0.0
    final_ocr_accuracy = 0.0
    pipeline_accuracy = 0.0


# =========================================================
# 31. CSV 저장
# =========================================================

csv_path = os.path.join(
    "results",
    "ocr_evaluation.csv"
)


df.to_csv(
    csv_path,
    index=False,

    # Windows Excel 한글 깨짐 방지
    encoding="utf-8-sig"
)


# =========================================================
# 32. Excel 평가 요약
# =========================================================

summary_df = pd.DataFrame(
    [
        {
            "평가항목": "총 평가 이미지",
            "성공수": total_count,
            "전체수": total_count,
            "성공률": "-"
        },

        {
            "평가항목": "차량 탐지",
            "성공수": vehicle_success_count,
            "전체수": total_count,
            "성공률": f"{vehicle_accuracy:.1f}%"
        },

        {
            "평가항목": "번호판 탐지",
            "성공수": plate_success_count,
            "전체수": total_count,
            "성공률": f"{plate_accuracy:.1f}%"
        },

        {
            "평가항목": "1차 OCR 완전일치",
            "성공수": first_ocr_success_count,
            "전체수": total_count,
            "성공률": f"{first_ocr_accuracy:.1f}%"
        },

        {
            "평가항목": "최종 OCR 완전일치",
            "성공수": final_ocr_success_count,
            "전체수": total_count,
            "성공률": f"{final_ocr_accuracy:.1f}%"
        },

        {
            "평가항목": "전체 파이프라인",
            "성공수": pipeline_success_count,
            "전체수": total_count,
            "성공률": f"{pipeline_accuracy:.1f}%"
        }
    ]
)


# =========================================================
# 33. Excel 저장
# =========================================================

excel_path = os.path.join(
    "results",
    "ocr_evaluation.xlsx"
)


with pd.ExcelWriter(
    excel_path,
    engine="openpyxl"
) as writer:


    # -----------------------------------------------------
    # 상세 결과
    # -----------------------------------------------------

    df.to_excel(
        writer,
        sheet_name="상세결과",
        index=False
    )


    # -----------------------------------------------------
    # 평가 요약
    # -----------------------------------------------------

    summary_df.to_excel(
        writer,
        sheet_name="평가요약",
        index=False
    )


    # =====================================================
    # Excel 가독성 개선
    # =====================================================

    workbook = writer.book


    # -----------------------------------------------------
    # 상세 결과 시트
    # -----------------------------------------------------

    detail_sheet = workbook[
        "상세결과"
    ]


    # 첫 행 고정
    detail_sheet.freeze_panes = "A2"


    # 필터 사용 가능
    detail_sheet.auto_filter.ref = (
        detail_sheet.dimensions
    )


    # 열 너비
    detail_widths = {
        "A": 12,   # 이미지
        "B": 14,   # 대상차량번호
        "C": 14,   # 차량종류
        "D": 16,   # 차량탐지성공
        "E": 18,   # 번호판탐지성공
        "F": 14,   # 차량신뢰도
        "G": 16,   # 번호판신뢰도
        "H": 14,   # 번호판너비
        "I": 14,   # 번호판높이
        "J": 18,   # 정답번호판
        "K": 18,   # 1차OCR
        "L": 20,   # 1차판정
        "M": 18,   # 1차OCR정답여부
        "N": 18,   # 2차OCR
        "O": 20,   # 2차판정
        "P": 18,   # 최종OCR
        "Q": 22,   # 최종판정
        "R": 20,   # 최종OCR정답여부
        "S": 18,   # 전체파이프라인
    }


    for column, width in detail_widths.items():

        detail_sheet.column_dimensions[
            column
        ].width = width


    # -----------------------------------------------------
    # 평가 요약 시트
    # -----------------------------------------------------

    summary_sheet = workbook[
        "평가요약"
    ]


    summary_sheet.column_dimensions[
        "A"
    ].width = 24


    summary_sheet.column_dimensions[
        "B"
    ].width = 12


    summary_sheet.column_dimensions[
        "C"
    ].width = 12


    summary_sheet.column_dimensions[
        "D"
    ].width = 14


# =========================================================
# 34. 터미널 최종 결과 출력
# =========================================================

print(
    "\n==================================="
)

print(
    "        AI 성능 평가 결과"
)

print(
    "==================================="
)


print(
    f"총 평가 이미지 수: "
    f"{total_count}"
)


print(
    f"차량 탐지: "
    f"{vehicle_success_count}/{total_count} "
    f"({vehicle_accuracy:.1f}%)"
)


print(
    f"번호판 탐지: "
    f"{plate_success_count}/{total_count} "
    f"({plate_accuracy:.1f}%)"
)


print(
    f"1차 OCR 완전일치: "
    f"{first_ocr_success_count}/{total_count} "
    f"({first_ocr_accuracy:.1f}%)"
)


print(
    f"최종 OCR 완전일치: "
    f"{final_ocr_success_count}/{total_count} "
    f"({final_ocr_accuracy:.1f}%)"
)


print(
    f"전체 파이프라인: "
    f"{pipeline_success_count}/{total_count} "
    f"({pipeline_accuracy:.1f}%)"
)


print(
    "\n결과 파일"
)


print(
    f"CSV   : {csv_path}"
)


print(
    f"Excel : {excel_path}"
)


print(
    "\n=== 전체 테스트 완료 ==="
)
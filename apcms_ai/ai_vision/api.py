# HTTP 통신 담당 코드

from fastapi import APIRouter
from fastapi import UploadFile
from fastapi import File
from fastapi import HTTPException

import cv2
import numpy as np

from ai_vision.recognizer import recognize_image


# =========================================================
# FastAPI 애플리케이션 생성
# =========================================================

router = APIRouter(tags=["YOLO / OCR"])


# =========================================================
# 서버 확인용 API
# =========================================================

@router.get("/vision")
def root():

    return {
        "message":
            "APCMS AI Server is running"
    }


# =========================================================
# Health Check
# =========================================================

@router.get("/vision/health")
def health():

    return {
        "status": "ok"
    }


# =========================================================
# 차량 + 번호판 인식 API
# =========================================================

@router.post("/recognize")
async def recognize(
    file: UploadFile = File(...)
):

    # -----------------------------------------------------
    # 1. 업로드 파일 종류 확인
    # -----------------------------------------------------

    if (
        file.content_type is None
        or not file.content_type.startswith(
            "image/"
        )
    ):

        raise HTTPException(
            status_code=400,
            detail="이미지 파일만 업로드할 수 있습니다."
        )


    # -----------------------------------------------------
    # 2. 업로드된 파일을 bytes로 읽는다.
    # -----------------------------------------------------

    image_bytes = await file.read()


    if not image_bytes:

        raise HTTPException(
            status_code=400,
            detail="빈 이미지 파일입니다."
        )


    # -----------------------------------------------------
    # 3. bytes → numpy 배열
    # -----------------------------------------------------

    np_array = np.frombuffer(
        image_bytes,
        dtype=np.uint8
    )


    # -----------------------------------------------------
    # 4. numpy 배열 → OpenCV 이미지
    # -----------------------------------------------------

    image = cv2.imdecode(
        np_array,
        cv2.IMREAD_COLOR
    )


    if image is None:

        raise HTTPException(
            status_code=400,
            detail=(
                "이미지를 읽을 수 없습니다."
            )
        )


    # -----------------------------------------------------
    # 5. AI 파이프라인 실행
    # -----------------------------------------------------

    try:

        result = recognize_image(
            image
        )

    except Exception as e:

        print(
            f"AI 처리 오류: {e}"
        )


        raise HTTPException(
            status_code=500,
            detail=(
                "AI 처리 중 오류가 발생했습니다."
            )
        )


    # -----------------------------------------------------
    # 6. JSON 반환
    # -----------------------------------------------------

    return result

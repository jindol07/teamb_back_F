# 차량번호 인식 및 주차면 점유 현황 조회를 담당하는
# APCMS 비전 AI 통합 라우터

import cv2
import numpy as np

from fastapi import APIRouter, UploadFile, File, HTTPException

# ai_vision/recognition/recognizer.py에 파일이 있는 경우
from .recognition.recognizer import recognize_image

# 기존 주차면 점유 조회 라우터
from .parking.parking_api import router as parking_router


# 1. 비전 AI 라우터 생성

# APIRouter(): 관련 API들을 하나로 묶는 객체
# 이 router를 상위 main.py에서 include_router()로 등록
router = APIRouter(tags=["Vision"])


# 2. 차량번호 인식 API 등록

# 기존 API 경로 /recognize 유지
# React 또는 Spring Boot에서 기존 경로로 호출 가능
@router.post("/recognize")
async def recognize(file: UploadFile = File(...)):

    # 2-1. 업로드 파일 종류 확인

    # file.content_type:
    # 업로드된 파일의 MIME 타입
    # 예: image/jpeg, image/png
    # startswith("image/"):
    # 이미지 형식으로 전달된 파일인지 확인
    if (
        file.content_type is None
        or not file.content_type.startswith("image/")
    ):
        raise HTTPException(
            status_code=400,
            detail="이미지 파일만 업로드할 수 있습니다."
        )

    # 2-2. 업로드 파일 읽기

    # await file.read():
    # 업로드된 파일 내용을 bytes로 읽음
    image_bytes = await file.read()

    # 파일 내용이 비어 있으면 오류 반환
    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="빈 이미지 파일입니다."
        )

    # 2-3. bytes를 NumPy 배열로 변환

    # np.frombuffer():
    # 이미지 파일의 바이트 데이터를 배열로 변환
    #
    # uint8:
    # 0~255 범위의 8비트 정수 자료형
    np_array = np.frombuffer(
        image_bytes,
        dtype=np.uint8
    )

    # 2-4. NumPy 배열을 OpenCV 이미지로 변환

    # imdecode():
    # JPEG/PNG 등의 압축된 이미지 데이터를 해석
    #
    # IMREAD_COLOR:
    # 3채널 BGR 컬러 이미지로 읽음
    image = cv2.imdecode(
        np_array,
        cv2.IMREAD_COLOR
    )

    # 이미지 파일이 손상되었거나
    # OpenCV에서 해석할 수 없는 형식인 경우
    if image is None:
        raise HTTPException(
            status_code=400,
            detail="이미지를 읽을 수 없습니다."
        )

    # 2-5. 차량번호 인식 AI 파이프라인 실행

    try:
        # 기존 recognizer.py에서 구현된 함수 사용
        # 차량 및 번호판 탐지 → OCR → 결과 생성
        result = recognize_image(image)

    except Exception as error:

        # 서버 콘솔에 오류 출력
        # 외부 사용자에게는 내부 오류 내용을 노출하지 않음
        print(f"AI 처리 오류: {error}")

        raise HTTPException(
            status_code=500,
            detail="AI 처리 중 오류가 발생했습니다."
        ) from error

    # 2-6. 차량번호 인식 결과 반환

    # FastAPI는 Python 딕셔너리를 JSON 응답으로 변환
    return result


# 3. 주차면 점유 현황 API 연결

# parking_api.py에 이미 구현된
# GET /parking/occupancy 라우터 재사용
#
# 주차면의 최신 결과 JSON을 읽어 반환하며
# 이 요청 자체가 웹캠 감지를 시작하지는 않음
router.include_router(parking_router)
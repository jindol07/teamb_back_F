# D:/finalProjectB/back/apcms_ai/ai_vision/main.py

# 차량번호 인식 및 주차면 점유 현황 조회를 담당하는
# APCMS 비전 AI 통합 라우터

from fastapi import APIRouter, UploadFile, File, HTTPException
from starlette.concurrency import run_in_threadpool

# ai_vision/recognition/recognizer.py에 파일이 있는 경우
from .recognition.recognizer import recognize_image
from .recognition.image_upload import MAX_UPLOAD_BYTES, ImageUploadError, process_uploaded_image
from .recognition.recognition_admission import RecognitionAdmission
from .recognition.ocr_configuration import OCRConfigurationError
from .http_diagnostics import log_inference_error
from .upload_limits import SingleImageUploadRoute

# 기존 주차면 점유 조회 라우터
from .parking.parking_api import router as parking_router
from .recognition.results_api import router as results_router


# 1. 비전 AI 라우터 생성

# APIRouter(): 관련 API들을 하나로 묶는 객체
# 이 router를 상위 main.py에서 include_router()로 등록
router = APIRouter(tags=["Vision"], route_class=SingleImageUploadRoute)
_recognition_admission = RecognitionAdmission(capacity=2)


# 2. 차량번호 인식 API 등록

# 기존 API 경로 /recognize 유지
# React 또는 Spring Boot에서 기존 경로로 호출 가능
@router.post("/recognize", responses={413: {"description": "이미지 파일 10MB 또는 2천만 픽셀 한도 초과"},
                                     503: {"description": "동시 인식 요청 한도 초과"}})
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

    # 2-2. 파일을 읽기 전에 처리 슬롯을 확보합니다. 요청을 대기열에 쌓지 않습니다.
    lease = _recognition_admission.try_acquire()
    if lease is None:
        raise HTTPException(status_code=503, detail="이미지 인식 요청이 많습니다. 잠시 후 다시 시도해 주세요.",
                            headers={"Retry-After": "1"})
    try:
        # 한도보다 1바이트 더 읽어 초과 여부만 확인합니다.
        image_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(image_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="이미지 파일은 최대 10MB까지 업로드할 수 있습니다.")
        if not image_bytes:
            raise HTTPException(status_code=400, detail="빈 이미지 파일입니다.")
        # 2-3. 작업 스레드가 디코딩·추론·슬롯 반환까지 책임집니다.
        result = await run_in_threadpool(lease.run, process_uploaded_image, image_bytes, recognize_image)
    except ImageUploadError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except HTTPException:
        raise
    except (FileNotFoundError, PermissionError, ImportError, OCRConfigurationError) as error:
        log_inference_error(error)
        # 모델·공유 라이브러리·볼륨 준비 오류는 요청 자체의 오류와 구분합니다.
        raise HTTPException(status_code=503, detail="인식 모델·패키지·접근 권한 준비 상태를 확인해 주세요.") from error
    except Exception as error:

        # 서버 콘솔에 오류 출력
        # 외부 사용자에게는 내부 오류 내용을 노출하지 않음
        log_inference_error(error)

        raise HTTPException(
            status_code=500,
            detail="AI 처리 중 오류가 발생했습니다."
        ) from error
    finally:
        # 2-4. 작업 시작 전 오류·취소일 때만 여기서 반환합니다. 실행 중 작업은 worker가 반환합니다.
        lease.cancel_pending()

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

# 4. 저장된 실행 결과 조회. 이 GET API 자체는 모델·카메라·송신기를 실행하지 않음
router.include_router(results_router)

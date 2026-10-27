# D:/finalProjectB/back/apcms_ai/ai_vision/app.py

"""문의·추천 모듈 없이 Vision API만 배포하는 진입점."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from ai_vision.main import router
from ai_vision.deployment_config import cors_origins
from ai_vision.recognition.deployment_readiness import check_readiness
from ai_vision.http_diagnostics import RequestDiagnosticsMiddleware
from ai_vision.upload_limits import UploadLimitsMiddleware


# 1. import 시 모델 생성·카메라 열기·결과 폴더 생성을 하지 않습니다.
def create_app():
    application = FastAPI(title="APCMS AI Vision")
    application.add_middleware(UploadLimitsMiddleware)
    origins = cors_origins()
    if origins:
        application.add_middleware(CORSMiddleware, allow_origins=origins,
                                   allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"],
                                   expose_headers=["X-Request-ID", "Server-Timing"])
    application.add_middleware(RequestDiagnosticsMiddleware)
    application.include_router(router)
    application.add_api_route("/health", health, methods=["GET"])
    application.add_api_route("/ready", ready, methods=["GET"])
    # 3. 전용 서버도 같은 주차 수명주기를 사용하며 기본은 비활성입니다.
    from ai_vision.parking.parking_runtime import install_parking_runtime
    install_parking_runtime(application, check_safety=False)
    return application


def health():
    # 2. 프로세스 생존 확인입니다. 모델 파일·추론 준비 완료 판정과 구분합니다.
    return {"status": "ok", "scope": "PROCESS_ONLY"}


def ready():
    # 임시 점검 파일만 생성·삭제하며 모델·카메라·전송기는 실행하지 않습니다.
    report = check_readiness()
    return JSONResponse(report, status_code=503 if report["status"] == "BLOCKED" else 200)


app = create_app()

"""통합 FastAPI 진입점: 기존 /recognize 경로 유지."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# 10/11 RAG
from ai_inquiry.config import settings
from ai_inquiry.main import router as inquiry_router

app=FastAPI(title='APCMS 통합 AI (Vision + Inquiry)',version='2.0.0')

#app.add_middleware(CORSMiddleware,allow_origins=settings()['cors'],allow_methods=['GET','POST','OPTIONS'],allow_headers=['Authorization','Content-Type'])
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings()["cors"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 10/11 RAG
app.include_router(inquiry_router)

# 10/14
# [ai_recmn] Parking zone recommendation router
from ai_recmn.service.router import router as recmn_router
app.include_router(recmn_router)

# 모듈 초기화 시 YOLO/PaddleOCR 모델 로딩(원본 동작 유지).
from ai_vision.main import router as vision_router
app.include_router(vision_router)

# 10/27 화재·연기 감지 자동감시: 라우터 lifespan에서 시작하고 종료 시 정리.
# Windows 개발환경에서는 기본 켜짐, AWS/Linux·운영환경은 기본 꺼짐.
from ai_vision.safety.camera_monitor_router import router as safety_camera_router
app.include_router(safety_camera_router)

@app.get('/')
def root(): return {'message':'APCMS AI Server is running'}

#@app.get('/health')
#def health(): return {'status':'ok','data_mode':settings()['mode']}

# Jenkins 배포 후 Health Check : 서버 가용성 확인 1025
@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "UP",
        "service": "apcms-ai",
        "data_mode": settings()["mode"]
    }
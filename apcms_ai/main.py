"""통합 FastAPI 진입점: 기존 /recognize 경로 유지."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
app.include_router(inquiry_router)
# 모듈 초기화 시 YOLO/PaddleOCR 모델 로딩(원본 동작 유지).
from ai_vision.api import router as vision_router
app.include_router(vision_router)
@app.get('/')
def root(): return {'message':'APCMS AI Server is running'}
@app.get('/health')
def health(): return {'status':'ok','data_mode':settings()['mode']}

"""환경 설정: MOCK은 로컬 개발 전용, API는 Spring Boot 검증 필수."""
from functools import lru_cache
from pathlib import Path
import os
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
@lru_cache
def settings():
    mode=os.getenv('DATA_MODE','MOCK').upper()
    if mode not in ('MOCK','API'): raise ValueError('DATA_MODE must be MOCK or API')
    env=os.getenv('APP_ENV','development').lower()
    if mode=='MOCK' and env!='development': raise RuntimeError('MOCK mode is DEVELOPMENT ONLY')
    return {
      'mode':mode, 'env':env,
      'base_url':os.getenv('SPRING_BOOT_BASE_URL','http://localhost:8080').rstrip('/'),
      'auth_path':os.getenv('AUTH_ME_PATH','/api/auth/me'),
      'reservation_path':os.getenv('RESERVATIONS_PATH','/api/reservation'),
      'usage_path':os.getenv('PARKING_USAGE_PATH','/api/parkingusage'),
      'inquiry_add_path':os.getenv('INQUIRY_ADD_PATH','/api/inquiry/add'),
      'vehicle_path':os.getenv('VEHICLES_PATH','/api/vehicle'),
      'mileage_path':os.getenv('MILEAGE_PATH','/api/mileage'),
      'fee_path':os.getenv('FEES_PATH','/api/maintenance'),
      'model':os.getenv('GEMINI_MODEL','gemini-2.5-flash'),
      'embedding_model':os.getenv('GEMINI_EMBED_MODEL','models/gemini-embedding-001'),
      'cors':[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:5173,http://localhost:3000').split(',') if x.strip()],
      'mock_db': ROOT / 'ai_inquiry' / 'mocks' / 'inquiry_demo.sqlite3',
      'llm_mode':os.getenv('LLM_MODE','GEMINI').upper()
    }

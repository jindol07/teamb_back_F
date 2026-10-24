"""환경 설정: MOCK은 로컬 개발 전용, API는 Spring Boot 검증 필수."""

from functools import lru_cache
from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@lru_cache
def settings():
    mode = os.getenv("DATA_MODE", "MOCK").upper()
    if mode not in ("MOCK", "API"):
        raise ValueError("DATA_MODE must be MOCK or API")
    env = os.getenv("APP_ENV", "development").lower()
    if mode == "MOCK" and env != "development":
        raise RuntimeError("MOCK mode is DEVELOPMENT ONLY")
    return {
        "mode": mode,
        "env": env,
        # 개발 환경의 MOCK 모드에서 TEST_RESERVATION_ENABLED=true인 경우에만 개발용 예약 조회 허용
        "test_reservation_enabled": (
            env == "development"
            and mode == "MOCK"
            and os.getenv("TEST_RESERVATION_ENABLED", "false").lower() == "true"
        ),
        "base_url": os.getenv(
            "SPRING_BOOT_BASE_URL", "http://localhost:80/alpharking"
        ).rstrip("/")
        + "/",
        # 기존 전체 조회 API 설정과 구분하여 챗봇 전용 본인 조회만 호출합니다.
        "auth_path": os.getenv("CHATBOT_ME_PATH", "api/chatbot/me"),
        "reservation_path": os.getenv(
            "CHATBOT_RESERVATIONS_PATH", "api/chatbot/me/reservations"
        ),
        "usage_path": os.getenv("CHATBOT_USAGE_PATH", "api/chatbot/me/usage"),
        "inquiry_add_path": os.getenv(
            "CHATBOT_SAVE_PATH", "api/chatbot/conversations/exchanges"
        ),
        "vehicle_path": os.getenv("CHATBOT_VEHICLES_PATH", "api/chatbot/me/vehicles"),
        "mileage_path": os.getenv("MILEAGE_PATH", "/api/mileage"),
        "fee_path": os.getenv("FEES_PATH", "/api/maintenance"),
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "embedding_model": os.getenv(
            "LOCAL_EMBED_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        ),
        "cors": [
            x.strip()
            for x in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
            ).split(",")
            if x.strip()
        ],
        "mock_db": ROOT / "ai_inquiry" / "mocks" / "inquiry_demo.sqlite3",
        "llm_mode": os.getenv("LLM_MODE", "GEMINI").upper(),
    }

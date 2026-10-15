"""Spring Boot가 호출할 POST /api/recmn/predict 엔드포인트."""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .predictor import recommend

router = APIRouter(prefix="/api/recmn", tags=["AI parking recommendation"])


class UsageRecord(BaseModel):
    entry_at: datetime  # 실제 입차일시
    zone_code: str = Field(pattern=r"^(A|B|C)$")


class RecommendationRequest(BaseModel):
    office_id: int = Field(gt=0)  # 모델 특성은 아니며, 사용자 이력 구분/응답 식별에 사용
    reservation_at: datetime  # 예약 예정 시각
    history: list[UsageRecord] = Field(default_factory=list, max_length=10000)


class ZoneScore(BaseModel):
    zone_code: str
    score: float  # RF의 추정 확률. 실제 만족 확률은 아님.


class RecommendationResponse(BaseModel):
    office_id: int
    recommendations: list[ZoneScore]
    source: str = "random_forest"


@router.post("/predict", response_model=RecommendationResponse)
def predict(request: RecommendationRequest):
    # 사용자 인증과 history가 실제 본인의 데이터인지는 Spring Boot가 검증해야 한다.
    try:
        rows = [{"entry_at": item.entry_at, "zone_code": item.zone_code} for item in request.history]
        ranked = recommend(request.reservation_at, rows)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RecommendationResponse(office_id=request.office_id, recommendations=ranked)

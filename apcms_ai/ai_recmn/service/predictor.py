"""실제 예약 API에서 쓰는 예측 함수. 여기서는 모델을 재학습하지 않는다."""
from functools import lru_cache
from pathlib import Path
import joblib
from ai_recmn.training.features import features_for_request

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "parking_rf.joblib"


@lru_cache(maxsize=1)
def load_model():
    # 신뢰할 수 있는 프로젝트 내부에서 직접 학습한 파일만 로드해야 한다.
    if not MODEL_PATH.exists():
        raise FileNotFoundError("먼저 python -m ai_recmn.training.train 명령으로 모델을 학습하세요")
    return joblib.load(MODEL_PATH)


def recommend(reservation_at, history: list[dict]) -> list[dict]:
    saved = load_model()
    row = features_for_request(reservation_at, history)
    probabilities = saved["pipeline"].predict_proba(row[saved["features"]])[0]
    classes = saved["pipeline"].named_steps["forest"].classes_
    # 모든 구역을 확률 추정치 순서로 전달: 1순위 구역이 만차면 다음 순위 사용.
    return sorted(
        [{"zone_code": str(zone), "score": round(float(p), 6)} for zone, p in zip(classes, probabilities)],
        key=lambda item: item["score"], reverse=True,
    )

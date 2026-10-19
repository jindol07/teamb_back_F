"""실행: python -m ai_recmn.training.train --csv ai_recmn/data/parking_history.csv"""
import argparse
import json
from pathlib import Path
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from .features import FEATURES, ZONES, prepare_training_data

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "parking_rf.joblib"


def train(csv_file: str | Path, model_file: str | Path = MODEL_PATH) -> dict:
    df = prepare_training_data(pd.read_csv(csv_file))
    # 동일한 일시에 기록된 데이터가 학습/평가에 함께 섞이지 않게 날짜 경계로 분리.
    # 80:20은 작은 시연 데이터에서 학습량과 평가량을 균형 있게 확보하기 위한 시작값.
    days = sorted(df["usage_date"].dt.normalize().unique())
    if len(days) < 10:
        raise ValueError("시간순 평가를 위해 최소 10일 이상의 이력이 필요합니다")
    boundary = days[int(len(days) * 0.8)]
    train_df = df[df["usage_date"] < boundary]
    test_df = df[df["usage_date"] >= boundary]
    if train_df.empty or test_df.empty or set(train_df["target_zone"]) != set(ZONES):
        raise ValueError("학습·평가용 이력에 A/B/C 구역이 충분히 있는지 확인하세요")
    encoder = ColumnTransformer(
        [("weekday", OneHotEncoder(handle_unknown="ignore"), ["day_of_week"])],
        remainder="passthrough",  # 나머지 수치형 특성은 그대로 사용. 트리는 StandardScaler 불필요.
    )
    model = RandomForestClassifier(
        n_estimators=100,  # 결정트리 100개: 450건 규모에서 안정성과 CPU 속도의 절충
        max_depth=8,  # 트리 최대 깊이 8: 작은 가상 데이터에 대한 지나친 암기 억제
        min_samples_leaf=3,  # 리프마다 최소 3건: 노이즈 한두 건에 과적합 방지
        random_state=42,  # 재현 가능한 시연을 위한 난수 고정
        n_jobs=-1,  # CPU의 사용 가능한 코어를 활용 (GPU 불필요)
    )
    pipeline = Pipeline([("encode", encoder), ("forest", model)])
    pipeline.fit(train_df[FEATURES], train_df["target_zone"])
    prediction = pipeline.predict(test_df[FEATURES])
    # 통계 비교군: 예약 요일·시간은 무시하고, 사용자별 과거 최빈 구역만 추천.
    baseline = test_df[[f"pref_score_{z}" for z in ZONES]].idxmax(axis=1).str.removeprefix("pref_score_")
    metrics = {
        "train_rows": int(len(train_df)), "test_rows": int(len(test_df)),
        "test_from": str(pd.Timestamp(boundary).date()),
        "random_forest_accuracy": round(float(accuracy_score(test_df["target_zone"], prediction)), 4),
        "most_used_zone_accuracy": round(float(accuracy_score(test_df["target_zone"], baseline)), 4),
        "classification_report": classification_report(test_df["target_zone"], prediction, labels=list(ZONES), zero_division=0, output_dict=True),
    }
    model_file = Path(model_file)
    model_file.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "features": FEATURES, "zones": ZONES}, model_file)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(ROOT / "data" / "parking_history.csv"))
    parser.add_argument("--model", default=str(MODEL_PATH))
    args = parser.parse_args()
    train(args.csv, args.model)

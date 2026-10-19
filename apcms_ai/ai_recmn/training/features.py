"""학습과 운영 API에서 공통으로 사용하는 특성 추출 (미래 데이터 사용 금지)."""

import pandas as pd

# AI가 추천할 주차구역
ZONES = ("A", "B", "C")

# Random Forest 학습에 사용할 입력 특성(X) 9개
FEATURES = [
    "day_of_week",
    "entry_hour",
    "is_weekend",
    "pref_score_A",
    "pref_score_B",
    "pref_score_C",
    "recent_A_count",
    "recent_B_count",
    "recent_C_count"
]


def prepare_training_data(raw: pd.DataFrame) -> pd.DataFrame:
    """각 행보다 이전 주차이력만 이용해 선호도와 최근 10회 빈도를 생성한다."""

    # 1. Oracle CSV의 대문자 컬럼명을 소문자로 통일
    df = raw.copy()
    df.columns = df.columns.str.strip().str.lower()

    # 2. 학습에 필요한 필수 컬럼 확인
    required = {"usage_id", "office_id", "usage_date", "target_zone"}

    if not required.issubset(df.columns):
        raise ValueError(
            f"CSV 컬럼 부족: {sorted(required - set(df.columns))}"
        )

    # 3. 문자열 날짜를 pandas 날짜형으로 변환
    df["usage_date"] = pd.to_datetime(
        df["usage_date"],
        errors="raise"
    )

    # 4. NULL 값 검사
    if df[list(required)].isna().any().any():
        raise ValueError("학습 필수 컬럼에 NULL 값이 있습니다")

    # 5. A/B/C 구역만 학습
    if not df["target_zone"].isin(ZONES).all():
        raise ValueError("이번 시연 모델은 A/B/C 구역만 지원합니다")

    # 6. 사용자별 주차이력을 시간순으로 정렬: 과거 이용 이력을 정확히 계산하기 위해
    df = df.sort_values(
        ["office_id", "usage_date", "usage_id"]
    ).reset_index(drop=True)

    # 7. 입차 날짜에서 요일과 시간 추출
    df["day_of_week"] = df["usage_date"].dt.dayofweek
    df["entry_hour"] = df["usage_date"].dt.hour

    # 토요일(5), 일요일(6)은 주말
    df["is_weekend"] = (
        df["day_of_week"] >= 5
    ).astype(int)

    # 8. 각 사용자별 '현재 행 이전[현재 행을 포함시 예측이 아니기 때문]'의 이용 건수
    history_size = df.groupby("office_id").cumcount()

    # 9. 구역별 과거 선호도와 최근 10회 이용 횟수 생성
    for zone in ZONES:

        # 현재 행이 해당 구역이면 1, 아니면 0
        indicator = df["target_zone"].eq(zone).astype(int)

        # 현재 행을 제외한 과거 해당 구역 이용 횟수
        earlier = (
            indicator.groupby(df["office_id"]).cumsum()
            - indicator
        )

        # 과거 이용 비율
        # 첫 이용 기록은 이력이 없으므로 A/B/C 각각 1/3
        df[f"pref_score_{zone}"] = (
            earlier / history_size.where(history_size > 0)
        ).fillna(1 / len(ZONES))

        # 현재 기록을 제외한 최근 10회 이용 횟수
        df[f"recent_{zone}_count"] = (
            indicator.groupby(df["office_id"]).transform(
                lambda s: s.shift(1).rolling(
                    10, min_periods=1
                ).sum()
            )
        ).fillna(0).astype(int)

    return df


def features_for_request(reservation_at, history: list[dict]) -> pd.DataFrame:
    """예약 예정 시각과 과거 주차이력으로 운영 API의 입력 특성을 생성한다."""

    at = pd.Timestamp(reservation_at)

    if pd.isna(at) or at.tzinfo is not None:
        raise ValueError("예약시간은 타임존 없는 한국 현지시각이어야 합니다")

    previous = []

    # 1. 사용자 과거 주차이력 검사
    for record in history:

        date = pd.Timestamp(record["entry_at"])

        if pd.isna(date) or date.tzinfo is not None:
            raise ValueError("입차시간은 타임존 없는 한국 현지시각이어야 합니다")

        zone = record["zone_code"]

        if zone not in ZONES:
            raise ValueError(f"지원하지 않는 구역: {zone}")

        if date < at:
            previous.append((date, zone))

    # 2. 과거 이용이력을 시간순 정렬
    previous.sort(key=lambda x: x[0])

    zones = [z for _, z in previous]

    # 3. 예약 예정 시각의 요일과 시간대 계산
    weekday = at.dayofweek

    output = {
        "day_of_week": weekday,
        "entry_hour": at.hour,
        "is_weekend": int(weekday >= 5)
    }

    # 4. 구역별 선호도와 최근 10회 이용 횟수
    for zone in ZONES:

        output[f"pref_score_{zone}"] = (
            zones.count(zone) / len(zones)
            if zones else 1 / len(ZONES)
        )

        output[f"recent_{zone}_count"] = (
            zones[-10:].count(zone)
        )

    # 학습과 예측에서 동일한 특성 순서 유지
    return pd.DataFrame([output], columns=FEATURES)
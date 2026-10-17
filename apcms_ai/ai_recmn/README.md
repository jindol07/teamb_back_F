# ai_recmn — 주차구역 추천 (최소 구성)

기존 `apcms_ai`에 **`ai_recmn/` 폴더만** 복사해 사용할 수 있는 패키지입니다. 다른 AI 담당자 파일은 수정하지 않습니다.

## 폴더별 역할

| 경로 | 용도 | 예약 버튼 클릭 시 실행? |
|---|---|---|
| `sql/01_insert_450.sql` | Oracle 11g에 3명×150건의 데모 이용이력 INSERT | 아니오 (DB 준비 시 1회) |
| `sql/02_export_history.sql` | DB에 INSERT된 이력 조회 → SQL Developer에서 CSV Export | 아니오 (재학습할 때) |
| `notebooks/train_walkthrough.ipynb` | Jupyter에서 로드·전처리·학습·평가·예측을 **셀별 실습** | 아니오 |
| `training/features.py` | 학습 및 운영 양쪽에서 동일한 특성 계산 | 예 (간접) |
| `training/train.py` | Random Forest 학습·성능 비교·모델 저장 | 아니오 (재학습할 때) |
| `models/parking_rf.joblib` | 학습 완료 모델 파일 (`train.py` 실행 후 생성) | 예 |
| `service/predictor.py` | 모델 불러오기 및 구역 A/B/C 점수 계산 | 예 |
| `service/router.py` | FastAPI `POST /api/recmn/predict` | 예 |
| `spring_boot_example/*.java` | `apcms_u`로 복사해 수정할 사용자 추천 API 예제 | Boot로 이관한 경우 예 |

**AI 모델 1개**만 사용합니다. 최빈 이용구역은 `train.py`에서 성능 비교에 쓰는 통계 기준선이며 별도의 학습 모델이 아닙니다. 예전 합성 CSV 생성 파이썬, 단독 FastAPI 실행파일, 중복된 `schemas.py` 등은 포함하지 않았습니다.

## 1. Oracle DB 준비

1. `office_id` 1, 2, 3이 존재해야 합니다. 한 층에 A/B/C 구역과 각 구역의 `parking_space`가 있어야 합니다.
2. `sql/01_insert_450.sql`의 `v_floor_id`와 `v_type_code`를 **실제 값**으로 변경해 실행하세요. `parking_usage`에 기존 주차이력을 비울 계획이라면 **개발/시연 DB에서만** 백업 후 수행하세요. 제공 SQL은 기존 데이터를 자동 삭제하지 않습니다.
3. 분포를 확인한 후 `COMMIT`하세요. 목표 건수는 1번 사용자 A=105/B=30/C=15, 2번 B=105/C=30/A=15, 3번 C=105/A=30/B=15입니다.
4. `sql/02_export_history.sql`의 층 ID를 설정하고 SQL Developer 결과 그리드에서 **CSV 내보내기**로 `ai_recmn/data/parking_history.csv`에 저장하세요. `data/` 폴더는 본인이 생성하세요. CSV 파일은 ZIP에 포함하지 않았습니다 (DB에서만 추출하도록 단일 경로 유지).

> 주의: `parking_usage_id`는 예제에서 MAX+1을 사용하므로 다른 트랜잭션과 동시 실행하면 안 됩니다. 이번 INSERT는 모델 학습용 이용이력으로, `vehicle_id`/`parking_reservation_id`는 NULL이고 한 구역의 한 주차면을 재사용합니다. 실제 예약/점유 통합 테스트에는 별도 정합 데이터가 필요합니다. SQL에 지정한 날짜는 2026-05-04부터 150일입니다. 다른 실습 날짜가 필요하면 시작일을 변경하세요.

## 2. 학습 및 평가

기존 `apcms_ai` 가상환경에서 없는 의존성만 설치:

```bash
pip install -r ai_recmn/requirements-recmn.txt
python -m ai_recmn.training.train --csv ai_recmn/data/parking_history.csv
```

학습 결과는 콘솔에서 확인하고 `ai_recmn/models/parking_rf.joblib`에 저장됩니다. 테스트 정확도와 기준선 정확도는 CSV와 분할 방법에 따라 달라집니다.

Jupyter 학습 실습은 `ai_recmn/notebooks/train_walkthrough.ipynb` 파일을 열고 **위에서 아래로** 실행하세요. 노트북은 `training/`의 **실제 운영 모듈**을 import하므로 동일한 코드를 두 벌 유지하지 않습니다. Notebook 시작 디렉터리는 `apcms_ai` 루트를 기준으로 합니다.

학습 특성: `day_of_week`, `entry_hour`, `is_weekend`, `pref_score_A/B/C`, `recent_A/B/C_count`. `office_id`는 모델 특성이 아니며 이용 이력을 분리하는 데만 사용합니다. 타깃은 `target_zone`. 입력에는 타깃 구역, 미래 이용이력, 실제 출차시간을 넣지 않습니다.

평가: **날짜 기준 과거 80% / 미래 20%**로 분리합니다. 데이터 합성 규칙이 단순하므로 높은 정확도가 나와도 실제 추천 품질의 증거는 아닙니다.

## 3. FastAPI 통합

기존 `apcms_ai/main.py`에 **아래 두 줄만 협의 후 추가**하세요 (이 ZIP은 기존 파일을 수정하지 않음).

```python
from ai_recmn.service.router import router as recmn_router
app.include_router(recmn_router)
```

해당 프로젝트에서 FastAPI 변수명이 `app`이 아닌 경우 맞게 바꾸세요. 서버 전체 실행은 기존 프로젝트의 명령을 사용합니다.

`POST /api/recmn/predict` 예시:

```json
{
  "office_id": 1,
  "reservation_at": "2026-10-20T09:00:00",
  "history": [
    {"entry_at": "2026-09-10T09:00:00", "zone_code": "A"},
    {"entry_at": "2026-09-11T18:00:00", "zone_code": "B"}
  ]
}
```

응답은 `{"office_id":1,"recommendations":[{"zone_code":"A","score":0.75},...],"source":"random_forest"}` 형태입니다. 점수는 예시이며 모델의 실제 응답은 달라질 수 있습니다. 신규 사용자 이력이 없어도 예측은 가능하지만, 데이터 3명만 학습한 모델은 신규 사용자에 대한 신뢰도가 낮습니다. 실제 운영에선 기본 추천으로 대체하는 것이 좋습니다.

## 4. Spring Boot 연동 예제

`spring_boot_example/`의 2개 Java 파일은 **ai_recmn 내부에서 실행하는 파일이 아닙니다**. `apcms_u` 담당자가 실제 패키지명/보안/예외 정책에 맞춰 복사하여 사용할 참고 소스입니다. Spring Boot 3 / Java 17, JDBC 의존성(`JdbcTemplate`)이 있다고 가정합니다. `application.properties`에 아래 예시 설정:

```properties
ai.recmn.url=http://localhost:8000/api/recmn/predict
ai.recmn.floor-id=1
```

Boot 데모 진입점: `POST /api/parking/recommendations`, 요청 `{"officeId":1,"reservationAt":"2026-10-20T09:00:00"}`.

**보안:** 예시에서는 편의상 officeId를 JSON으로 받지만 운영환경에서는 반드시 로그인 사용자로부터 office_id를 서버가 결정해야 합니다. Spring Boot가 이용이력의 소유권과 인증을 담당하고, **구역별 빈 주차면/예약 시간 겹침 검사 및 수락 시 트랜잭션**도 담당합니다. FastAPI는 구역의 순위만 예측합니다. FastAPI는 내부망에서만 접근하도록 구성하세요.

## 팀 협업을 위한 변경 파일 목록

- 기존 `apcms_ai` 파일 변경: **없음**
- 신규 폴더: `ai_recmn/` (이 ZIP의 전체 내용)
- 별도 수동 통합 필요: `apcms_ai/main.py`에 라우터 등록 2줄, 기존 `requirements.txt`의 누락 의존성 확인, `apcms_u`에 Java 예제 이관
- 기존 비전/RAG 코드는 수정하지 않음

## 10/14
## 가상환경 for JupyterNotebook
.venv\Scripts\activate
# Jupyter 설치
pip install notebook ipykernel
# Random Forest 학습에 필요한 라이브러리
pip install pandas numpy scikit-learn joblib
# 실행
jupyter notebook

## 실습 순서
1)DB에서 추출한 CSV 읽기 및 사용자별 구역 이용 분포 확인
2)요일·시간대·과거 선호도 특성 생성
3)과거 80% 학습 / 이후 20% 평가 데이터 분리
4)Random Forest 모델 학습 및 최빈 구역 추천과 정확도 비교
5)학습된 .joblib 모델을 이용한 실제 추천 함수 호출
## 실제 적용 순서
1)01_insert_450.sql에서 층 ID와 주차유형 코드를 실제 DB 값으로 수정 후 실행
2)450건 정상 INSERT 확인 후 COMMIT
3)02_export_history.sql을 실행해서 ai_recmn/data/parking_history.csv로 저장
4)Jupyter Notebook에서 단계별 학습 및 평가
5)parking_rf.joblib 생성 확인
6)기존 apcms_ai/main.py에 아래 두 줄 추가


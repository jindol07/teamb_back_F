# 저장 결과 조회와 검토

[시작 안내](../readme.md) · [영상 분석](VIDEO_ANALYSIS.md) · [결과 검토](RESULTS_REVIEW.md) · [입출차 연동](VEHICLE_INTEGRATION.md)

> 아래 명령은 모두 `D:\finalProjectB\back\apcms_ai`에서 실행합니다.
> 기존 결과를 보존하려면 예시의 출력 이름을 새 이름으로 바꿔 사용하세요.

저장된 결과를 조회하고 사람이 정답을 검토하는 방법입니다. 모델 재실행 없이 가능한 기능과 원본 영상이 필요한 검토를 구분합니다. CONFIRMED·COMPLETED·진단 PASS는 실제 정답 확인과 다릅니다.

## 목차

- [결과 API와 검색 및 CSV](#api)
- [수동 정답 검토와 이미지 HTML](#review)
- [추적과 OCR 연결 진단](#audit)

<a id="api"></a>

## 결과 API와 검색 및 CSV

실제 촬영 입력이 없어도 기존 처리 결과를 팀원과 확인할 수 있도록 조회 경로를
추가했습니다. 기존 AI 서버에 연결되며 `/recognize`, `/parking/occupancy`는 유지합니다.

| GET 경로 | 용도 |
|---|---|
| `/vision/runs?offset=0&limit=20` | 저장된 실행 목록, 1~100개씩 조회 |
| `/vision/runs/{run_id}` | 추적·OCR·통합 실행의 요약과 상태 |
| `/vision/runs/{run_id}/passages?offset=0&limit=20` | 차량별 방향·영상 시각·번호판 판정 |
| `/vision/runs/{run_id}/audit` | 저장 로그·추적/OCR 연결 일관성 진단 |

예시 실행 ID는 `traffic_pipeline_fresh`, `traffic_pipeline_reuse`,
`traffic_botsort_full`, `traffic_ocr_local`입니다. 추적만 수행한 실행은
번호판 결과가 없으므로 `/passages`에 404를 반환합니다.

결과는 `ai_vision/results/recognition` 아래에서만 읽습니다. 요청에 임의
파일 경로를 받지 않으며 절대 경로와 내부 오류 메시지는 응답에서 제외합니다.
실행 ID는 영문·숫자·하이픈·밑줄만 허용합니다. 잘못된 입력은 422,
결과 없음은 404, 손상되거나 검증되지 않는 결과는 503입니다.
목록에서는 손상된 실행을 `UNAVAILABLE`로 표시하고 다른 실행은 계속 제공합니다.

진단 경로는 손상된 실행도 HTTP 200의 `status=FAILED`와 고정 검사 코드로 설명합니다.
진단 대상 없음은 404입니다. PASS는 인식 정확도 합격을 뜻하지 않습니다.
세부 범위와 CLI 사용법은 [결과 진단](RESULTS_REVIEW.md#audit)를 참고하세요.

조회는 모델 초기화·웹캠 접근·재전송·파일 저장을 수행하지 않습니다.
POST/DELETE 등 변경 경로는 없습니다. 실시간 분석을 시작하는 API가 아닙니다.
번호판 판정은 저장된 OCR 표본으로 다시 계산해 저장 내용과 다르면 제공을 중단합니다.
보이는 CONFIRMED는 반복 인식 정책 통과를 뜻하며 실제 정답 확인을 뜻하지 않습니다.

### 차량 결과 검색과 CSV 내보내기

`/vision/runs/{run_id}/passages`에 다음 선택 조건을 함께 사용할 수 있습니다.

| 조건 | 허용 값 |
|---|---|
| `direction` | `UP`, `DOWN` (화면 기준 이동 방향) |
| `plate_status` | `CONFIRMED`, `CONFLICT`, `INSUFFICIENT_EVIDENCE`, `NO_VALID_KOREAN_PLATE` |
| `start_seconds`, `end_seconds` | 원본 영상 시각(초), 양 끝 포함 |

예: `/vision/runs/traffic_pipeline_fresh/passages?direction=DOWN&start_seconds=0&end_seconds=3`

조건은 AND로 적용하며 `total`은 검색 조건 적용 후의 건수입니다. 검색 후 페이지를
나눕니다. 시작 시각이 종료 시각보다 크면 422입니다. 필터 밖의 행도 검증하므로
검색 조건으로 손상된 기록을 숨기지 않습니다. 중복 차량 ID, 누락 행, 요약과
판정별 건수 불일치도 503으로 처리합니다.

서버를 실행하지 않고 같은 조건으로 CSV를 만들 수 있습니다. `apcms_ai`에서 실행합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.export_passages `
  --run-id traffic_pipeline_fresh `
  --direction DOWN `
  --output ai_vision/results/exports/my_passages_01.csv
```

`--plate-status`, `--start-seconds`, `--end-seconds`도 지원합니다. Excel 한글 표시를
위해 UTF-8 BOM을 사용하며, 100건을 넘는 결과도 모두 저장합니다. 검색 결과가
없으면 열 이름만 저장합니다. 원본 `results/recognition` 밖의 새 CSV만 허용하고
기존 CSV는 덮어쓰지 않습니다. 내보내기는 영상 처리가 끝난 결과에서 실행하세요.
CSV에는 실행 ID, 차량 ID, 화면 방향, 영상 시각, 번호판 판정·번호·표본 수만
들어갑니다. API 추가와 마찬가지로 실제 ENTRY/EXIT 이벤트를 만들거나 전송하지 않습니다.

### 모델 없는 독립 조회 서버

기존 통합 AI 진입점은 기존 동작대로 모델을 로딩합니다. 결과만 조회할 경우에는
아래 별도 앱을 로컬에서 실행하면 인식 모델을 불러오지 않습니다.

```powershell
# apcms_ai 폴더에서 결과 조회 서버를 실행합니다.
.\.venv312\Scripts\python.exe -m uvicorn ai_vision.recognition.results_api:app --host 127.0.0.1 --port 8001
```

이 API에는 별도 인증을 추가하지 않았습니다. 위 명령은 로컬 접속용이며,
외부 공개 전에는 팀의 인증·접근 정책을 연결해야 합니다.

### 함께 보강한 처리 규칙

- JSON의 NaN/무한대·중복 키·손상된 JSONL 검사 및 원자적 JSON 교체 저장
- 같은 원본 프레임의 서로 다른 OCR 번호는 충돌로 기록
- 같은 프레임의 서로 다른 영상 시각과 시각 역행 검사
- 중복 관찰 시각으로 안정화 프레임 수가 증가하지 않도록 처리
- 꼬인 ROI와 ROI에 닿지 않는 기준선 검사
- 통과가 없는 구간은 OCR 모델을 불러오지 않고 빈 결과 저장
- OCR 출력은 새 폴더만 사용하여 기존 결과를 보존
- 재사용 영상·폴더 관계는 OCR 전에 검사하고 새 실행 설정을 복사 저장
- 통과 로그가 바뀌면 기존 수동 검토 메모를 덮어쓰지 않고 새 폴더 사용 안내

변경 파일의 첫 줄에는 파일 경로 주석을 달았으며 주요 흐름에 한국어 주석을
유지했습니다. Boot 코드와 송신 설정은 변경하지 않았습니다.


<a id="review"></a>

## 수동 정답 검토와 이미지 HTML

`CONFIRMED`는 서로 다른 프레임에서 같은 번호를 반복 인식했다는 뜻입니다.
정답 확인과 구분하기 위해 사람이 작성한 검토 CSV를 별도로 보관합니다.
이 기능은 저장된 OCR 결과만 읽으며 영상 분석이나 실제 입출차 전송을 시작하지 않습니다.

### 1. 검토 양식 생성

PowerShell에서 `D:\finalProjectB\back\apcms_ai`로 이동하고 실행합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.review_passages template `
  --run-id traffic_pipeline_fresh `
  --output ai_vision/results/reviews/my_review_01.csv
```

모든 행은 `PENDING`이고 정답 번호는 비어 있습니다. AI 예측을 정답에 자동 복사하지 않습니다.
`results/recognition` 안에는 출력할 수 없고 기존 파일은 덮어쓰지 않습니다.
같은 위치에 파일이 있으면 `_02`처럼 새 이름을 사용하세요.

### 2. 사람이 영상과 저장 이미지를 확인

Excel에서 CSV를 열고 `review_status`, `expected_plate`, `note`만 수정하세요.
실행 ID·해시·차량 ID·영상 시각·예측 열은 그대로 유지합니다. 행의 순서는 바꿀 수 있지만
삭제하거나 중복하면 오류입니다. 저장 시 **CSV UTF-8**을 선택하세요.
원본 영상의 `video_seconds` 부근과 해당 실행의 OCR 폴더 이미지를 직접 확인합니다.
차량 ID는 해당 실행에 속하므로 다른 실행의 같은 ID와 혼동하지 마세요.

#### 번호판 이미지를 한 화면에서 보기

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.review_passages bundle `
  --run-id traffic_pipeline_fresh `
  --output ai_vision/results/reviews/my_gallery_01.html
```

생성된 HTML을 브라우저에서 열면 차량 ID·통과 시각·AI 판정·표본별 OCR 문자열과
번호판 이미지를 함께 볼 수 있습니다. 이미지를 파일 안에 포함하므로 네트워크나
API 서버 없이 열 수 있습니다. 외부 리소스·스크립트·자동 전송은 사용하지 않습니다.
번호판이 포함된 자료이므로 검토 용도에 맞게 보관하세요.

기본 20대씩 표시하며 `--offset 20 --limit 20`으로 다음 차량들을 새 HTML에 만들 수
있습니다. limit은 1~100입니다. 화면에 표시된 차량 수와 전체 OCR 차량 수를 따로
표시합니다. HTML은 읽기 전용이므로 정답은 기존 CSV에서 입력하세요. HTML과 CSV의
검토 대상 식별값이 같은지 확인합니다. CSV 양식은 전체 OCR 차량을 포함합니다.

이미지가 저장되지 않은 표본은 이미지 없음으로 표시합니다. 이는 사람이 판정한
`NO_PLATE`와 다른 상태입니다. 번호판 crop만으로 차량 전체나 번호판 미노출을
단정하지 말고 원본 영상을 함께 확인하세요. OCR 표본 자체가 없는 차량도 별도 표시합니다.
원본 결과·기존 HTML은 덮어쓰지 않습니다. 손상 JPEG·외부 폴더 이미지·판정 변경을
거부하며 이미지 한 장 4MB, 선택 페이지 이미지 합계 24MB, HTML 40MB로 제한합니다.
제한을 넘으면 limit을 줄여 주세요. 각 이미지의 해시도 HTML에 표시합니다.

| review_status | 사람이 확인한 내용 | expected_plate |
|---|---|---|
| PENDING | 아직 확인하지 않음 | 비워 둠 |
| VERIFIED_PLATE | 현재 지원하는 한국 번호판의 전체 번호를 직접 읽음 | 예: `91소6408` |
| UNREADABLE | 영상·이미지로 번호를 읽을 수 없음 | 비워 둠 |
| NO_PLATE | 검토 화면에 번호판이 보이지 않음 | 비워 둠 |
| OUT_OF_SCOPE | 외국 번호판 등 현재 한국 번호판 평가 범위 밖 | 비워 둠 |

지원 정답 형식은 숫자 2~3자리 + 한글 1글자 + 숫자 4자리입니다.
레거시 지역명·외교·임시 번호판 등은 아직 평가 범위에 포함하지 않습니다.
외국 번호판인 `traffic.mp4`를 한국 번호판 정답 자료로 사용하지 마세요.
`UNREADABLE`은 오인식이라는 뜻이 아니며, `NO_PLATE`도 차량 자체에 번호판이
없다는 단정이 아닌 검토 화면에서의 관찰입니다.

### 3. 보고서 생성

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.review_passages report `
  --run-id traffic_pipeline_fresh `
  --labels ai_vision/results/reviews/my_review_01.csv `
  --output ai_vision/results/reviews/my_report_01.json
```

예측 결과와 처리 범위의 SHA-256 식별값을 대조합니다. 결과가 바뀌거나 고정 열이
수정됐으면 보고서를 만들지 않습니다. 정답 파일 자체의 해시도 보고서에 남깁니다.
해시는 검토 대상 식별용이며 사람이 입력한 정답의 사실 여부를 보증하지 않습니다.
검토 대상 결과는 처리가 끝난 뒤 사용하세요.

### 보고서 읽기

- `review_status_counts`: 미검토·정답 입력·판독 불가·번호판 미노출·평가 범위 밖 건수
- `exact_matches`: 정답 번호와 AI 확정 번호가 완전히 같은 건수
- `wrong_confirmed_plates`: 사람이 읽은 번호와 다른 번호를 AI가 확정한 건수
- `unconfirmed_on_verified_plate`: 사람이 번호를 읽었지만 AI가 확정하지 못한 건수
- `confirmed_on_no_plate`: 번호판 미노출로 검토된 화면에서 AI가 번호를 확정한 건수
- `exact_match_rate_on_verified_plates`: 완전 일치 건수 / VERIFIED_PLATE 건수

정답 입력이 없으면 일치율은 `null`입니다. `PENDING`, `UNREADABLE`, `NO_PLATE`,
`OUT_OF_SCOPE`는 한국 번호판 완전 일치율의 분모에 들어가지 않습니다.
`review_complete`는 미검토 행이 없다는 뜻이며 인식 정확도 합격을 뜻하지 않습니다.
보고서는 **OCR 처리된 차량만** 대상으로 합니다. 미검출 차량·OCR 미처리 차량·
전체 영상의 통과 정확도는 평가하지 않습니다. 부분 OCR 실행이면
`source_total_crossings`와 `total_review_rows`가 다를 수 있습니다.

검토 파일과 보고서는 `results` 아래에서 Git 제외 대상입니다. 자동 테스트의 한국
번호판 정답 예시는 집계 규칙 검증용이며 실제 촬영 영상의 성능 증거가 아닙니다.


<a id="audit"></a>

## 추적과 OCR 연결 진단

추적·OCR·통합 실행 로그의 형식과 연결 관계를 모델 실행 없이 점검합니다.
이 기능의 PASS는 저장 로그 일관성 검사 통과입니다. 실제 차량 누락·과다 집계나
한국 번호판 정답 정확도는 원본 영상 및 수동 검토 자료로 따로 평가해야 합니다.

### 명령어

`D:\finalProjectB\back\apcms_ai`에서 PowerShell로 실행합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.audit_results `
  --run-id traffic_pipeline_fresh
```

기본 동작은 콘솔 출력뿐이며 결과 폴더를 수정하지 않습니다. 새 보고서가 필요하면:

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.audit_results `
  --run-id traffic_pipeline_fresh `
  --output ai_vision/results/audits/my_audit_01.json
```

원본 `results/recognition` 밖의 새 JSON에만 저장합니다. 기존 보고서는 덮어쓰지 않습니다.

### API

기존 결과 조회 서버에서 `GET /vision/runs/{run_id}/audit`를 사용합니다.
예: `http://127.0.0.1:8001/vision/runs/traffic_pipeline_fresh/audit`

진단 결과 자체는 HTTP 200 응답의 `status`로 구분합니다. 진단 대상이 없는 경우 404,
잘못된 실행 ID는 422입니다. 원본 절대 경로와 예외 문자열을 응답에 넣지 않습니다.
진단 API도 모델·카메라·네트워크 전송·파일 쓰기를 시작하지 않습니다.

| status | 의미 |
|---|---|
| PASS | 제공된 필수 로그의 일관성 검사를 통과 |
| WARNING | 검사 범위 제한이 있음: 관찰 로그 미저장 또는 일부 차량만 OCR |
| FAILED | 요약·로그·추적/OCR 연결 검사 실패 |
| INCOMPLETE | 통합 실행이 RUNNING 또는 FAILED로 끝나 완료 결과가 아님 |

`reason_code`에는 `RESULT_SCHEMA`, `TRACKING_LOGS`, `PIPELINE_SOURCES`,
`OCR_TRACK_LINKS` 같은 실패 위치 또는 `OBSERVATIONS_NOT_SAVED`, `OCR_PARTIAL`
같은 경고 원인이 들어갑니다. `checks`는 해당 단계의 검사가 진행됐다는 뜻이며,
전체 최종 판정은 반드시 `status`를 확인합니다.

CLI 종료 코드는 PASS/WARNING=0, FAILED/INCOMPLETE=1, 대상·출력 경로 오류=2입니다.
모든 차량의 OCR 완료가 필요한 자동화에서는 종료 코드뿐 아니라 `status`와
`reason_code`를 함께 확인하세요.

### 검사 범위

- 방향별 통과 건수와 중복 차량 ID
- FPS 기준 프레임 번호와 저장 시각의 일치 여부
- 관찰 프레임 중복·역행, 영상 크기 내 차량 상자, 통과 프레임의 관찰 존재 여부
- 통합 실행·OCR·추적의 원본 영상 및 실행 폴더 연결
- OCR 차량별 통과 방향·시각, 표본 프레임의 같은 차량 관찰 여부
- 통과 전 2초~후 0.75초의 OCR 표본 범위와 중복 표본
- OCR 표본 재계산 판정과 처리·확정 건수

OCR 결과를 진단할 때에는 원래 추적 로그와 관찰 로그가 필요합니다. 원본 영상 파일은
열지 않으므로 영상이 이동돼도 저장 로그의 연결을 검사할 수 있습니다. 이는 영상의
내용이 같다는 파일 해시 검증은 아닙니다. 이미지 무결성은 별도의 검토 HTML 생성 과정에서
검사합니다. 통과선 알고리즘을 재실행하거나 미검출 차량을 찾아내는 진단도 아닙니다.

`scope`는 항상 `SAVED_LOG_CONSISTENCY_ONLY`이며 `http_enabled`는 false입니다.
통과 0건인 정상 저장 구간도 PASS가 될 수 있고, 이는 인식 성능 증거를 뜻하지 않습니다.

# 저장된 Vision 결과 조회 API

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
세부 범위와 CLI 사용법은 `RESULT_AUDIT.md`를 참고하세요.

조회는 모델 초기화·웹캠 접근·재전송·파일 저장을 수행하지 않습니다.
POST/DELETE 등 변경 경로는 없습니다. 실시간 분석을 시작하는 API가 아닙니다.
번호판 판정은 저장된 OCR 표본으로 다시 계산해 저장 내용과 다르면 제공을 중단합니다.
보이는 CONFIRMED는 반복 인식 정책 통과를 뜻하며 실제 정답 확인을 뜻하지 않습니다.

## 차량 결과 검색과 CSV 내보내기

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

## 모델 없는 독립 조회 서버

기존 통합 AI 진입점은 기존 동작대로 모델을 로딩합니다. 결과만 조회할 경우에는
아래 별도 앱을 로컬에서 실행하면 인식 모델을 불러오지 않습니다.

```powershell
# apcms_ai 폴더에서 필요할 때 실행. 서버는 이번 작업에서 실제로 실행하지 않았습니다.
.\.venv312\Scripts\python.exe -m uvicorn ai_vision.recognition.results_api:app --host 127.0.0.1 --port 8001
```

이 API에는 별도 인증을 추가하지 않았습니다. 위 명령은 로컬 접속용이며,
외부 공개 전에는 팀의 인증·접근 정책을 연결해야 합니다.

## 함께 보강한 처리 규칙

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

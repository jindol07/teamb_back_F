# 저장된 Vision 결과 진단

추적·OCR·통합 실행 로그의 형식과 연결 관계를 모델 실행 없이 점검합니다.
이 기능의 PASS는 저장 로그 일관성 검사 통과입니다. 실제 차량 누락·과다 집계나
한국 번호판 정답 정확도는 원본 영상 및 수동 검토 자료로 따로 평가해야 합니다.

## 명령어

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

## API

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

## 검사 범위

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

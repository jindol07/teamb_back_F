# 번호판 수동 검토와 정답 비교

`CONFIRMED`는 서로 다른 프레임에서 같은 번호를 반복 인식했다는 뜻입니다.
정답 확인과 구분하기 위해 사람이 작성한 검토 CSV를 별도로 보관합니다.
이 기능은 저장된 OCR 결과만 읽으며 영상 분석이나 실제 입출차 전송을 시작하지 않습니다.

## 1. 검토 양식 생성

PowerShell에서 `D:\finalProjectB\back\apcms_ai`로 이동하고 실행합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.review_passages template `
  --run-id traffic_pipeline_fresh `
  --output ai_vision/results/reviews/my_review_01.csv
```

모든 행은 `PENDING`이고 정답 번호는 비어 있습니다. AI 예측을 정답에 자동 복사하지 않습니다.
`results/recognition` 안에는 출력할 수 없고 기존 파일은 덮어쓰지 않습니다.
같은 위치에 파일이 있으면 `_02`처럼 새 이름을 사용하세요.

## 2. 사람이 영상과 저장 이미지를 확인

Excel에서 CSV를 열고 `review_status`, `expected_plate`, `note`만 수정하세요.
실행 ID·해시·차량 ID·영상 시각·예측 열은 그대로 유지합니다. 행의 순서는 바꿀 수 있지만
삭제하거나 중복하면 오류입니다. 저장 시 **CSV UTF-8**을 선택하세요.
원본 영상의 `video_seconds` 부근과 해당 실행의 OCR 폴더 이미지를 직접 확인합니다.
차량 ID는 해당 실행에 속하므로 다른 실행의 같은 ID와 혼동하지 마세요.

### 번호판 이미지를 한 화면에서 보기

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

## 3. 보고서 생성

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

## 보고서 읽기

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

# 영상 추적부터 번호판 OCR까지 한 명령으로 실행

ROI·기준선·추적기는 [영상별 설정 파일](TRACKING_CONFIG.md)의 `--config`로 지정할 수도 있습니다.

`run_video_pipeline.py`는 다음 순서로 기존 모듈을 실행합니다.

1. `vehicle_tracking.py`: 통과 기록과 프레임별 ID 관찰 정보 저장
2. `recognize_tracked_passages.py`: 통과한 ID에만 번호판 OCR 연결
3. 영상·ID·방향·시각·표본 출처·번호판 확정 근거를 검사한 뒤 요약 저장

중간 단계가 실패하면 다음 단계로 넘어가지 않고 `pipeline.json`에 실패 단계를
남깁니다. 실행 폴더는 새 폴더여야 하며 기존 결과를 덮어쓰지 않습니다.
서버 전송 기능이나 ENTRY/EXIT 자동 매핑은 포함하지 않습니다.

## 새 영상 처리

`D:\finalProjectB\back\apcms_ai`에서 실행합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_video_pipeline `
  --source "C:\Users\ICT-008\Downloads\traffic.mp4" `
  --tracker botsort --max-seconds 10 --max-tracks 2 `
  --output-dir ai_vision/results/recognition/my_video_pipeline
```

`--max-seconds`는 추적할 영상 길이, `--max-tracks`는 OCR을 수행할 통과 ID 수입니다.
제한을 빼면 입력 영상과 기록된 통과 ID 전체를 처리합니다.
기본 ROI와 기준선은 traffic 영상의 가까운 차로용이므로 다른 영상에서는
`--line-y`, `--line-x`, `--roi`를 해당 장면에 맞춰 지정해야 합니다.
실제 움직이는 한국 차량 영상은 현재 없어 해당 통합 검증은 미완료입니다.

## 이미 실행한 결과 재사용

새 모델 실행 없이 실제 저장 결과의 연결 관계와 집계를 검증할 수 있습니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_video_pipeline `
  --source "C:\Users\ICT-008\Downloads\traffic.mp4" `
  --reuse-tracking ai_vision/results/recognition/traffic_botsort_full `
  --reuse-ocr ai_vision/results/recognition/traffic_ocr_local `
  --output-dir ai_vision/results/recognition/my_reused_pipeline
```

재사용 폴더의 자료는 수정하지 않습니다. 재사용하는 단계에는 tracker, 좌표,
처리 제한 등의 신규 실행 옵션이 적용되지 않으며 저장된 결과 자체를 검사합니다.
OCR 재사용 시에는 원래 그 OCR을 생성한 추적 폴더도 함께 지정해야 합니다.
추적만 재사용하고 OCR을 새로 실행하는 것도 가능합니다.

## 출력 파일

- `pipeline.json`: 단계별 GENERATED/REUSED/FAILED 상태와 전체 실행 상태
- `summary.json`: 통과 건수, OCR 처리·미처리 건수, 번호판 상태별 건수
- `tracking.log`, `ocr.log`: 새로 실행한 단계의 콘솔 출력과 오류
- `tracking/`, `ocr/`: 해당 단계를 새로 실행한 경우에만 생성되는 결과 폴더

`COMPLETED`는 지정한 작업의 실행과 결과 검사를 마쳤다는 뜻입니다.
OCR 제한으로 일부 차량만 처리했다면 `ocr_coverage`는 `PARTIAL`이며
`ocr_not_processed`에 남은 차량 수가 기록됩니다. 실제 인식 정확도 검증 완료와
구분해야 합니다.

## 이번 검증 범위

- 기존 실제 추적·OCR 결과를 재사용한 실행: 통과 44건, OCR 2건, 미처리 42건,
  한국 번호판 확정 0건, HTTP 비활성화 확인
- 결과 위치: `ai_vision/results/recognition/traffic_pipeline_reuse/`
- 기존 테스트 15개와 새 검사 5개, 총 20개 통과
- 새 검사: 부분 OCR 표시, 다른 차량 프레임 혼입, 표본과 다른 번호판 확정,
  다른 입력 영상 혼입, 추적 실패 시 OCR 중단과 실패 단계 기록
- 이후 결과를 재사용하지 않는 실제 연속 실행도 검증했습니다.
  `traffic.mp4`의 첫 3초를 BoT-SORT로 처리하고 통과 ID 1대에 OCR을 적용했습니다.
  단계 상태는 tracking=GENERATED, ocr=GENERATED, validation=VALIDATED,
  전체 상태는 COMPLETED였습니다.
- 연속 실행 결과: 원본 3초에서 90개 처리 프레임(30fps), DOWN 통과 1건,
  해당 ID의 OCR 3개 프레임, 한국 번호판 확정 0건, HTTP 비활성화.
  해당 실행에서 기록한 통과 ID는 모두 OCR 처리됐지만 실제 인식 정확도나
  한국 차량 이동 검증 완료를 의미하지 않습니다.
- 연속 실행 결과 위치: `ai_vision/results/recognition/traffic_pipeline_fresh/`.
  출력 MP4의 마지막 프레임까지 읽을 수 있는지도 확인했습니다.

Python 테스트의 기본 임시 폴더가 샌드박스에서 접근 거부되어 권한을 부여한
재실행에서 전체 테스트를 통과했습니다. 기존 인식기나 모델은 변경하지 않았습니다.

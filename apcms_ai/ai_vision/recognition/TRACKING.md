# 차량 이동 방향 추적 실험

저장된 결과를 모델 재실행 없이 조회하는 경로는 [결과 조회 API](RESULTS_API.md)에 있습니다.

긴 좌표 옵션 대신 [영상별 설정 파일](TRACKING_CONFIG.md)을 사용할 수 있습니다.

첫 10초의 로그 비교와 반대편 차로 실행 결과는 [검증 기록](TRACKING_VALIDATION.md)을 참고하세요.
차량별 잠정 관찰 자료와 비교하는 평가 도구는 [가림 구간 진단](OCCLUSION_ANALYSIS.md)에 설명했습니다.
통과 ID별 번호판 OCR과 웹캠 영상 촬영 절차는 [번호판 연결](TRACKED_OCR.md)을 참고하세요.

기존 `yolo11n.pt`와 ByteTrack으로 차량 ID를 유지하고, 차량 상자의 중심점이
수평 기준선을 통과하면 `DOWN` 또는 `UP`을 기록합니다.
이 모듈은 OCR, `.env`, HTTP 송신 모듈을 불러오지 않습니다.
`DOWN`/`UP`은 화면 방향이며 실제 주차장 입차/출차 의미는 아직 부여하지 않습니다.

## 실행

`D:\finalProjectB\back\apcms_ai`에서 실행합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.vehicle_tracking --source "C:\Users\ICT-008\Downloads\traffic.mp4"
```

기본값은 이 traffic 영상의 가까운 두 차로에 맞춰져 있습니다.
다른 영상에서는 ROI와 기준선을 다시 지정해야 합니다.

- `--max-seconds 10`: 처음 10초만 검증
- `--start-seconds 30 --max-seconds 12`: 원본 30~42초 구간만 재실행
- `--save-observations`: ID/상자/중심점/확정 상태를 `observations.jsonl`에 기록
- `--imgsz 960`: 탐지 입력 해상도 실험 (기본값 640, 높인다고 항상 개선되지는 않음)
- `--nms-iou 0.3 --agnostic-nms`: 겹치는 탐지 제거를 강화하는 실험 옵션 (기본값 유지)
- `--tracker botsort`: 기존 ByteTrack 대신 설치된 BoT-SORT로 비교 (기본값 bytetrack)

`traffic.mp4`의 가림 구간에서는 BoT-SORT가 누락 후보를 줄였습니다.
해당 영상의 개선 후보를 재현하려면 아래 명령을 사용합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.vehicle_tracking --source "C:\Users\ICT-008\Downloads\traffic.mp4" --tracker botsort --output-dir ai_vision/results/recognition/traffic_botsort_full
```

전체 정답 라벨을 확인한 결과는 아니므로 다른 카메라에도 항상 더 정확하다고
가정하지 않습니다. 비교 근거는 [가림 구간 진단](OCCLUSION_ANALYSIS.md)에 있습니다.
- `--stride 2`: 원본 두 프레임마다 하나 처리 (60fps 영상이면 30fps 처리)
- `--line-y 0.60`: 영상 높이의 60% 위치에 수평선 지정
- `--line-x 0.15 0.90`: 선분의 시작/끝 위치를 영상 너비 비율로 지정
- `--roi`: 다각형 꼭짓점 4개의 x/y 비율 8개
- `--output-dir`: 결과 폴더. 같은 폴더로 재실행하면 이전 결과를 덮어씁니다.

## 결과

기본 저장 위치: `ai_vision/results/recognition/traffic_tracking/`

- `tracking.mp4`: 원본 재생 속도로 ID, ROI, 기준선, 누적 수 표시
- `crossings.jsonl`: 통과별 ID, 방향, 영상 시각, 위치, 탐지 신뢰도
- `summary.json`: 처리 프레임 수, 집계, 실행 설정
- `preview.jpg`, `last_crossing.jpg`: 첫 처리 화면과 마지막 통과 화면

파란 다각형은 ROI, 빨간 선은 기준선입니다. 초록 상자는 미집계 차량,
노란 상자는 통과가 집계된 ID입니다. 로그 시각은 선 반대편 상태가 확정된
영상 시각이며, 정확한 물리적 통과 시각이나 실제 촬영 날짜는 아닙니다.
`detection_confidence`는 차량 탐지 신뢰도이며 방향 판별 신뢰도가 아닙니다.

## 판별 규칙과 한계

- 선에서 위아래 12px 이내는 판정을 보류합니다.
- 같은 쪽에서 처리 프레임 3개를 연속 확인해야 상태를 확정합니다.
- 영상 시간 1초 넘게 안 보인 ID는 이전 위치와 연결하지 않습니다.
- 위치 이동 속도가 초당 영상 높이의 1.25배를 넘으면 위치 연결을 끊습니다.
  이는 이 고정 영상용 보호값으로, 빠른 차량이나 다른 카메라에서는 조정이 필요합니다.
- 탐지 신뢰도 0.25와 NMS IoU 0.5를 사용해 낮은 신뢰도 및 겹치는 탐지를 줄입니다.
- 통과 궤적이 지정한 선분과 만나는 경우만 집계합니다.
- 한 실행 동안 같은 추적 ID는 한 번만 집계합니다. 실제 재입차·재출차를
  허용하는 운영 정책은 별도 구현이 필요합니다.
- 가림으로 ID가 바뀌면 동일 차량이 중복 집계되거나 통과를 놓칠 수 있습니다.
  따라서 자동 집계 수치는 사람이 센 정답과 비교하기 전에는 정확도로 해석하지 않습니다.
- 시작부터 선 아래에 있는 차량은 통과로 집계하지 않습니다.
- 현재 영상은 외국 도로 영상이므로 한국 번호판 및 주차장 입출차 검증과 구분합니다.

## 모델 없이 판별 로직 검증

```powershell
.\.venv312\Scripts\python.exe -m unittest ai_vision.tests.recognition.test_line_crossing -v
```

기존 두 requirements 파일의 NumPy/OpenCV/Ultralytics 조건 차이는 이 작업에서
일괄 수정하지 않았습니다. 기존 환경에 필요한 `lap` 의존성만 추가했습니다.

## 통과 전후 장면으로 결과 검토

`review_tracking.py`는 YOLO를 다시 실행하지 않고 기존 `summary.json`과
`crossings.jsonl`, 원본 영상을 읽습니다. 실행 폴더 아래 `review/`에 자료를 만듭니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.review_tracking --run-dir ai_vision/results/recognition/traffic_tracking --expected-direction DOWN
```

- `events_*.jpg`: 통과 확정 시각의 전후 0.75초 장면을 한 줄에 표시
- `timeline_*.jpg`: 누락을 검토할 수 있도록 이벤트 유무에 관계없이 0.5초 간격 장면 표시
- `audit.json`: 같은 ID 중복, 예상과 다른 방향, 요약 건수 일치 여부 자동 점검
- `event_review.csv`: 차량별 검토 상태와 의견을 기록할 표
- `review.md`: 검토 이미지를 모아서 볼 수 있는 문서

자동 점검은 서로 다른 ID가 같은 차량인지 판정하지 않습니다. CSV는 처음에
`UNREVIEWED`로 생성되며, 기존 CSV가 있으면 수동 메모를 보호하기 위해 유지합니다.
같은 실행 폴더에서 추적을 새로 돌려 로그가 달라졌다면 새 결과 폴더를 사용해야 합니다.
0.5초 사이의 짧은 움직임이나 심한 가림은 원본 영상에서 추가 확인해야 합니다.

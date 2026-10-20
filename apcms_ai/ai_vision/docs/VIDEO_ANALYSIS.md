# 영상 분석과 번호판 인식

이미지 인식의 모델은 recognizer 모듈 import 시 한꺼번에 만들지 않고, 차량 탐지·번호판
탐지·문자 OCR의 최초 호출에 각각 생성합니다. 문자열 정리나 좌표 crop 함수만 사용하면
모델을 생성하지 않습니다. 전체 이미지 인식의 반환 형식과 탐지·OCR 조건은 유지합니다.
누락된 가중치·백엔드 오류는 해당 모델을 처음 사용하는 시점에 나타날 수 있으므로
실행 전 점검과 실제 인식 확인을 함께 진행하세요. 지연 로딩 자체가 캐시·가중치 무결성이나
인식 정확도를 검증하는 것은 아닙니다.

`/recognize`는 동기 인식 함수를 작업 스레드에서 실행합니다. 모델 처리 중 API 이벤트
루프를 계속 점유하지 않으며, 기존 응답 형식과 잘못된 이미지의 400·추론 오류의 500
응답은 유지합니다. 같은 프로세스에서 공유하는 모델은 recognizer의 역할별 잠금으로
호출을 직렬화합니다. 차량 탐지의 fallback과 OCR의 결과 순회도 보호 범위에 포함됩니다.
동일 역할의 요청은 앞선 추론이 끝날 때까지 기다리므로 처리량 증가나 GPU 자원 한도
관리를 보장하는 기능은 아닙니다. 실제 GPU·다중 요청 부하 검증은 별도로 필요합니다.

이미지 업로드는 최대 10×1024×1024바이트, 최대 20,000,000픽셀을 허용합니다.
핸들러는 파일 크기 한도보다 1바이트 더 읽어 초과 여부를 확인하며, Pillow로 이미지
헤더의 크기를 확인한 뒤 OpenCV로 디코딩합니다. 해상도 확인·디코딩도 작업 스레드에서
수행합니다. 픽셀 제한은 실제 디코딩 결과에도 다시 적용합니다.

빈 파일·손상되거나 해석할 수 없는 이미지·이미지가 아닌 MIME은 400, 파일 크기나
픽셀 한도 초과는 413이며 이때 모델을 호출하지 않습니다. 모델 처리 오류는 기존 500
응답을 유지합니다. 정상 이미지의 인식 응답 형식은 유지하고 Swagger에도 413을 표시합니다.
이는 핸들러의 읽기·디코딩 제한입니다. multipart 수신·임시 저장 전에 요청 전체를 차단하는
설정이나 동시 요청을 합친 메모리 상한은 아니며, 필요 시 웹 서버의 요청 크기 제한과
함께 운영해야 합니다.

이미지 인식 API는 한 프로세스에서 최대 2개 요청만 받아 처리합니다. MIME 확인 후
파일 읽기 전에 슬롯을 확보하며, 슬롯이 없으면 대기열에 쌓지 않고 503과
`Retry-After: 1`을 반환합니다. 클라이언트는 중복 클릭을 막고 처리 중임을 표시한 뒤
필요한 시점에 다시 요청할 수 있습니다. 서버가 자동으로 요청을 재전송하지는 않습니다.

디코딩과 추론은 한 작업 스레드 안에서 실행합니다. 파일 읽기 중 오류·취소가 나면
아직 시작하지 않은 슬롯을 반환합니다. 작업이 이미 시작됐다면 요청 코루틴이 취소돼도
작업 스레드가 실제 종료할 때까지 슬롯을 유지합니다. 처리 성공·입력 오류·추론 오류
모두 작업 종료 후 슬롯을 반환하며, 실행 중인 모델을 강제로 중단하지는 않습니다.
여러 프로세스로 서버를 실행하면 각각 2개 한도가 적용됩니다. 이는 인식 작업의 수를
제한하며 multipart 수신 전체나 GPU 메모리·모든 API의 부하를 통제하는 기능은 아닙니다.

번호판 OCR 재시도는 작은 crop의 기존 4배 확대를 유지하되 한 변 4096픽셀·총
4,000,000픽셀을 넘지 않도록 크기를 맞춥니다. 큰 crop은 축소될 수 있습니다.
1500×1500 입력은 기존 6000×6000 대신 2000×2000으로 재시도합니다. 흑백 변환·CLAHE와
한국 번호판 문자열 후처리는 유지합니다. 이 한도는 재시도용 이미지 배열의 크기 제한이며
PaddleOCR 내부 메모리 전체나 인식 정확도를 보장하지 않습니다.

PaddleOCR에 전달하는 임시 파일은 PNG로 저장해 JPEG 재압축에 의한 픽셀 손실을 없앱니다.
임시 폴더는 호출이 끝나면 정리합니다. PNG의 실제 픽셀 보존·정리와 크기 제한은
검사했으며, 실제 모델에서의 인식률·지연 시간 비교는 별도 확인이 필요합니다.

[시작 안내](../readme.md) · [영상 분석](VIDEO_ANALYSIS.md) · [결과 검토](RESULTS_REVIEW.md) · [입출차 연동](VEHICLE_INTEGRATION.md)

> 아래 명령은 모두 `D:\finalProjectB\back\apcms_ai`에서 실행합니다.
> 기존 결과를 보존하려면 예시의 출력 이름을 새 이름으로 바꿔 사용하세요.

실행은 통합 실행부터 시작하고 필요한 경우 설정·추적·OCR 세부 내용을 확인합니다. 뒤의 검증·가림 실험은 과거 실행 기록이며, 전체 영상의 정답 정확도나 한국 번호판 주행 성능을 뜻하지 않습니다.

## 목차

- [추적부터 OCR까지 통합 실행](#pipeline)
- 실제 카메라 루프는 [실시간 카메라 세션](VEHICLE_INTEGRATION.md#live-session) 참고
- [영상별 ROI와 추적 설정](#config)
- [차량 추적과 화면 방향 판정](#tracking)
- [통과 ID별 OCR과 촬영 도구](#ocr)
- [기존 traffic 영상 검증 기록](#validation)
- [가림 구간 실험 기록](#occlusion)

<a id="pipeline"></a>

## 추적부터 OCR까지 통합 실행

ROI·기준선·추적기는 [영상별 설정 파일](VIDEO_ANALYSIS.md#config)의 `--config`로 지정할 수도 있습니다.

`run_video_pipeline.py`는 다음 순서로 기존 모듈을 실행합니다.

1. `vehicle_tracking.py`: 통과 기록과 프레임별 ID 관찰 정보 저장
2. `recognize_tracked_passages.py`: 통과한 ID에만 번호판 OCR 연결
3. 영상·ID·방향·시각·표본 출처·번호판 확정 근거를 검사한 뒤 요약 저장

중간 단계가 실패하면 다음 단계로 넘어가지 않고 `pipeline.json`에 실패 단계를
남깁니다. 실행 폴더는 새 폴더여야 하며 기존 결과를 덮어쓰지 않습니다.
서버 전송 기능이나 ENTRY/EXIT 자동 매핑은 포함하지 않습니다.

### 새 영상 처리

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

### 이미 실행한 결과 재사용

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

### 출력 파일

- `pipeline.json`: 단계별 GENERATED/REUSED/FAILED 상태와 전체 실행 상태
- `summary.json`: 통과 건수, OCR 처리·미처리 건수, 번호판 상태별 건수
- `tracking.log`, `ocr.log`: 새로 실행한 단계의 콘솔 출력과 오류
- `tracking/`, `ocr/`: 해당 단계를 새로 실행한 경우에만 생성되는 결과 폴더

`COMPLETED`는 지정한 작업의 실행과 결과 검사를 마쳤다는 뜻입니다.
OCR 제한으로 일부 차량만 처리했다면 `ocr_coverage`는 `PARTIAL`이며
`ocr_not_processed`에 남은 차량 수가 기록됩니다. 실제 인식 정확도 검증 완료와
구분해야 합니다.

### 이번 검증 범위

- 기존 실제 추적·OCR 결과를 재사용한 실행: 통과 44건, OCR 2건, 미처리 42건,
  한국 번호판 확정 0건, HTTP 비활성화 확인
- 결과 위치: `ai_vision/results/recognition/traffic_pipeline_reuse/`
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


<a id="config"></a>

## 영상별 ROI와 추적 설정

추적 실행 도구와 통합 실행 도구에서 `--config`로 같은 JSON 설정을 사용합니다.
카메라 번호가 아니라 영상의 촬영 구도에 맞춘 ROI·기준선·추적기 설정입니다.
실제 카메라 영상은 아직 없으므로 아래 설정은 traffic 영상 전용입니다.

### 준비한 두 설정

| 설정 파일 | 분석 영역 | 기준선(1280×720 기준) | 추적기 |
|---|---|---|---|
| `ai_vision/data/tracking_configs/traffic_near.json` | 가까운 두 차로 | y=432, x=192~1152 | BoT-SORT |
| `ai_vision/data/tracking_configs/traffic_far.json` | 반대편 차로 | y=259, x=0~294 | ByteTrack |

설정 파일의 좌표는 픽셀이 아니라 0~1 비율입니다. ROI는 화면 테두리를
따라 순서대로 나열한 네 꼭짓점의 x/y 비율 8개입니다.
번호판, API 키, 서버 주소, 입차/출차 방향 매핑은 설정에 포함하지 않습니다.

### 실행 예시

`D:\finalProjectB\back\apcms_ai`에서 실행합니다.

```powershell
# 가까운 차로 추적: 긴 좌표 옵션 대신 설정 파일 지정
.\.venv312\Scripts\python.exe -m ai_vision.recognition.vehicle_tracking `
  --source "C:\Users\ICT-008\Downloads\traffic.mp4" `
  --config ai_vision/data/tracking_configs/traffic_near.json `
  --save-observations --output-dir ai_vision/results/recognition/my_near_tracking

# 같은 설정으로 추적 → OCR → 결과 검사
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_video_pipeline `
  --source "C:\Users\ICT-008\Downloads\traffic.mp4" `
  --config ai_vision/data/tracking_configs/traffic_near.json `
  --max-seconds 3 --max-tracks 1 `
  --output-dir ai_vision/results/recognition/my_config_pipeline
```

반대편 차로는 `traffic_far.json`으로 바꿉니다.
새 촬영 구도에서는 기존 파일을 복사해 네 항목을 해당 장면에 맞춰 지정해야 합니다.

### 적용 우선순위와 검사

직접 지정한 명령 옵션 > 설정 파일 > 기존 프로그램 기본값 순서로 적용합니다.
예를 들어 `--config traffic_near.json --tracker bytetrack`이면 추적기만
ByteTrack으로 바뀌고 파일의 기준선과 ROI는 유지됩니다.
설정 없이 실행하면 기존 기본값과 같습니다.

허용 항목은 `tracker`, `line_y`, `line_x`, `roi` 네 개입니다.
알 수 없는 항목, 잘못된 개수·범위, bool/NaN/무한대 좌표,
중복 꼭짓점·넓이 없는 ROI를 오류로 처리합니다.
좌표의 문법이 맞더라도 실제 차로에 맞는지는 영상에서 확인해야 합니다.

추적 결과의 `summary.json`과 통합 실행의 `pipeline.json`에 설정 파일 경로가
기록됩니다. 실제 적용된 픽셀 좌표와 추적기도 추적 요약에 저장됩니다.
기존 결과를 재사용하는 단계에는 설정 파일을 새로 적용하지 않습니다.

### 검증 결과

- 두 설정으로 각각 실제 영상 첫 3초를 실행: 90프레임 처리
- 가까운 차로 DOWN 1건, 반대편 차로 UP 1건으로 기존 기록과 대응
- 결과 위치: `ai_vision/results/recognition/config_near_smoke/`, `config_far_smoke/`
- 우선순위, 기존 기본값, 오타, 유효하지 않은 좌표, 빈 ROI, 기존 픽셀 좌표 재현 검사를 수행했습니다.
- 새 Python 파일과 수정 파일의 첫 줄 경로 주석 및 한국어 설명 유지
- HTTP 전송 비활성화. 실제 한국 차량 입출차 통합 검증은 미완료


<a id="tracking"></a>

## 차량 추적과 화면 방향 판정

저장된 결과를 모델 재실행 없이 조회하는 경로는 [결과 조회 API](RESULTS_REVIEW.md#api)에 있습니다.

긴 좌표 옵션 대신 [영상별 설정 파일](VIDEO_ANALYSIS.md#config)을 사용할 수 있습니다.

첫 10초의 로그 비교와 반대편 차로 실행 결과는 [검증 기록](VIDEO_ANALYSIS.md#validation)을 참고하세요.
차량별 잠정 관찰 자료와 비교하는 평가 도구는 [가림 구간 진단](VIDEO_ANALYSIS.md#occlusion)에 설명했습니다.
통과 ID별 번호판 OCR과 웹캠 영상 촬영 절차는 [번호판 연결](VIDEO_ANALYSIS.md#ocr)을 참고하세요.

기존 `yolo11n.pt`와 ByteTrack으로 차량 ID를 유지하고, 차량 상자의 중심점이
수평 기준선을 통과하면 `DOWN` 또는 `UP`을 기록합니다.
이 모듈은 OCR, `.env`, HTTP 송신 모듈을 불러오지 않습니다.
`DOWN`/`UP`은 화면 방향이며 실제 주차장 입차/출차 의미는 아직 부여하지 않습니다.

### 실행

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
가정하지 않습니다. 비교 근거는 [가림 구간 진단](VIDEO_ANALYSIS.md#occlusion)에 있습니다.
- `--stride 2`: 원본 두 프레임마다 하나 처리 (60fps 영상이면 30fps 처리)
- `--line-y 0.60`: 영상 높이의 60% 위치에 수평선 지정
- `--line-x 0.15 0.90`: 선분의 시작/끝 위치를 영상 너비 비율로 지정
- `--roi`: 다각형 꼭짓점 4개의 x/y 비율 8개
- `--output-dir`: 결과 폴더. 같은 폴더로 재실행하면 이전 결과를 덮어씁니다.

### 결과

기본 저장 위치: `ai_vision/results/recognition/traffic_tracking/`

- `tracking.mp4`: 원본 재생 속도로 ID, ROI, 기준선, 누적 수 표시
- `crossings.jsonl`: 통과별 ID, 방향, 영상 시각, 위치, 탐지 신뢰도
- `summary.json`: 처리 프레임 수, 집계, 실행 설정
- `preview.jpg`, `last_crossing.jpg`: 첫 처리 화면과 마지막 통과 화면

파란 다각형은 ROI, 빨간 선은 기준선입니다. 초록 상자는 미집계 차량,
노란 상자는 통과가 집계된 ID입니다. 로그 시각은 선 반대편 상태가 확정된
영상 시각이며, 정확한 물리적 통과 시각이나 실제 촬영 날짜는 아닙니다.
`detection_confidence`는 차량 탐지 신뢰도이며 방향 판별 신뢰도가 아닙니다.

### 판별 규칙과 한계

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

### 모델 없이 판별 로직 검증

```powershell
.\.venv312\Scripts\python.exe -m unittest ai_vision.tests.recognition.test_line_crossing -v
```

기존 두 requirements 파일의 NumPy/OpenCV/Ultralytics 조건 차이는 이 작업에서
일괄 수정하지 않았습니다. 기존 환경에 필요한 `lap` 의존성만 추가했습니다.

### 통과 전후 장면으로 결과 검토

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


<a id="ocr"></a>

## 통과 ID별 OCR과 촬영 도구

추적과 OCR을 한 명령으로 실행하거나 기존 결과를 결합하려면
[통합 실행 도구](VIDEO_ANALYSIS.md#pipeline)를 사용하세요.

### 구현 내용

1. 기존 `vehicle_tracking.py`로 통과 기록과 프레임별 관찰 정보를 저장합니다.
2. `recognize_tracked_passages.py`가 통과한 각 ID의 원본 화면을 선택합니다.
3. 기존 `recognizer.py`의 번호판 탐지·영역 추출·PaddleOCR 함수를 재사용합니다.
4. `plate_consensus.py`가 서로 다른 시점의 번호판 결과를 비교합니다.
5. 방향과 번호판 관찰 결과는 `LOCAL_TRACKED_PASSAGE`로 로컬에만 저장합니다.

이 모듈은 이벤트 송신기나 `.env`를 불러오지 않으며 HTTP 전송 기능이 없습니다.
동영상의 DOWN/UP을 실제 ENTRY/EXIT로 바꾸거나 현재 날짜를 촬영 날짜로 붙이지 않습니다.

### 번호판 확정 규칙

- 같은 추적 ID에서 통과 전 2초~통과 후 0.75초의 화면 중 최대 3장을 선택
- 최소 0.25초 이상 떨어진 서로 다른 프레임을 사용
- `KOREAN_VALID`와 문자열 형식 검사를 모두 통과한 동일 번호가 최소 2회 필요
- 서로 다른 유효 번호가 나오면 다수결로 덮어쓰지 않고 `CONFLICT`
- 외국 번호판, 형식 오류, 한 번만 읽힌 번호판은 확정하지 않음

반복 인식도 실제 번호판 정답이나 추적 ID의 정확성을 보장하지 않습니다.
특히 차량 가림으로 다른 차량의 번호판이 상자 안에 들어갈 수 있어 실제 영상 검증이 필요합니다.
`plate_detection_confidence`는 번호판 상자 탐지 신뢰도이며 OCR 정확도 점수가 아닙니다.

### 기존 traffic 영상에서 재현

`apcms_ai` 폴더에서 실행합니다. 기존 추적 결과에 `observations.jsonl`이 필요합니다.

```powershell
# 먼저 추적: 같은 이름의 결과를 보존하려면 새 출력 폴더 사용
.\.venv312\Scripts\python.exe -m ai_vision.recognition.vehicle_tracking --source "영상경로.mp4" --tracker botsort --save-observations --output-dir ai_vision/results/recognition/my_tracking

# 이후 같은 ID의 원본 프레임을 OCR: 처음 2대만 검증
.\.venv312\Scripts\python.exe -m ai_vision.recognition.recognize_tracked_passages --run-dir ai_vision/results/recognition/my_tracking --output-dir ai_vision/results/recognition/my_ocr --max-tracks 2
```

출력: `passages.jsonl`, `summary.json`, 탐지된 번호판의 검토 사진.
`--max-tracks`를 빼면 통과 기록 전체를 처리합니다. 출력 폴더는 추적 폴더와
달라야 하며, OCR 출력은 새 폴더를 사용해야 합니다. 기존 폴더는 덮어쓰지 않습니다.

### 실제 실행 결과와 범위

- 기존 `car12.png`: `91소6408`, `KOREAN_VALID` 재확인.
  1차 `91소64089`는 REVIEW, 기존 전처리 재시도에서 정상 번호를 인식했습니다.
  이는 정지 이미지 인식 검증이며 이동 차량 통합 검증은 아닙니다.
- `traffic_botsort_full`의 ID 6, 7: 각 3개 프레임에 실제 번호판 탐지와 OCR 실행.
  영문·숫자를 읽었고 두 차량 모두 `NO_VALID_KOREAN_PLATE`로 처리했습니다.
- 저장 위치: `ai_vision/results/recognition/traffic_ocr_local/`.
- 처음 OCR 실행은 샌드박스 임시 폴더 권한으로 실패했습니다.
  실행 권한을 부여한 동일 로컬 모델 재실행에서 정상 처리했으며 인식기 코드를
  변경하거나 모델·패키지를 새로 설치하지 않았습니다.

### 한국 차량 영상이 없을 때: 웹캠 원본 촬영 도구

사용자가 한국 번호판 이동 영상이 없다고 확인하여, 직접 실행할 수 있는
`record_gate_video.py`를 준비했습니다. 실제 하드웨어 촬영은 아직 수행하지 않았습니다.

```powershell
# 차량과 번호판이 보이는 촬영 장면을 준비한 뒤 실행
.\.venv312\Scripts\python.exe -m ai_vision.recognition.record_gate_video --camera 0 --seconds 20
```

Q 키 또는 제한 시간에 종료합니다. 원본 MP4와 촬영 정보를
`ai_vision/results/recognition/gate_recordings/`에 새 이름으로 저장합니다.
촬영 영상의 실제 해상도와 카메라 FPS/수집 속도는 JSON에서 확인할 수 있습니다.
카메라는 고정하고 다른 프로그램의 카메라 사용을 종료한 뒤 실행합니다.

촬영 영상에는 기존 traffic용 ROI와 기준선을 그대로 적용하면 안 됩니다.
화면에서 차량이 지나가는 영역과 선 위치를 정하고 `--roi`, `--line-y`,
`--line-x`를 지정한 뒤 추적 → OCR 순서로 검증해야 합니다.
실제 입차에 해당하는 화면 방향도 해당 촬영 장면에서 확인해야 합니다.


<a id="validation"></a>

## 기존 traffic 영상 검증 기록

이 절은 기존 traffic 영상의 제한된 범위 실험을 보존한 기록입니다. 독립 정답 라벨 평가가 아닙니다.

### 검증 범위와 방법

- 입력: 사용자가 제공한 `traffic.mp4` (1280×720, 60fps, 60초)
- 이번 비교 범위: 시작 후 0초 이상 10초 미만
- 가까운 두 차로: 기존 60초 실행 로그에서 첫 10초에 해당하는 기록을 비교
- Codex가 원본을 0.25초 간격으로 추출하고 기준선 표시 이미지로 차량 이동을 검토
- 통과 기준은 차량의 앞범퍼가 아니라 차량 상자 중심점의 선 통과
- 시작부터 선 아래에 있는 차량은 집계 대상에서 제외
- 로그 시간은 여유 구간을 벗어나 반대쪽 상태가 3회 확인된 시각이므로,
  눈으로 보이는 선 통과 순간보다 늦을 수 있음

사람이 독립적으로 작성한 정답 라벨은 아닙니다. 아래 결과는 제한된 구간의
프레임 육안 검토와 자동 로그 대조이며, 전체 60초의 정확도 수치로 해석하지 않습니다.

### 가까운 차로: DOWN

설정: y=432, 선분 x=192~1152, 기본 ROI, stride=2.
0.25초 간격 원본 프레임에서 통과 차량 8대를 확인했고 자동 로그 8건과
차로별 이동 순서가 대응했습니다. 이 검토 범위에서 뚜렷한 누락·중복·역방향 기록은
확인되지 않았습니다. 차량 ID가 영상 내내 유지되었다는 의미는 아닙니다.

| 자동 확정 시각(초) | 추적 ID | 가까운 차로 위치 | 방향 |
|---:|---:|---|---|
| 1.200 | 6 | 왼쪽 차로 | DOWN |
| 3.600 | 7 | 오른쪽 차로 | DOWN |
| 4.567 | 8 | 왼쪽 차로 | DOWN |
| 5.733 | 24 | 오른쪽 차로 | DOWN |
| 6.233 | 11 | 왼쪽 차로 | DOWN |
| 7.767 | 270 | 왼쪽 차로 | DOWN |
| 8.200 | 16 | 오른쪽 차로 | DOWN |
| 9.733 | 166 | 오른쪽 차로 | DOWN |

근거 파일 (프로젝트 루트 `apcms_ai` 기준):

- 자동 로그: `ai_vision/results/recognition/traffic_tracking/crossings.jsonl`
- 기준선 표시 검토 이미지: `ai_vision/results/recognition/traffic_validation/down_line_0.jpg` ~ `down_line_4.jpg`

### 반대편 차로: UP

기존 실행 모듈의 옵션만 변경했습니다. 가까운 차로 기본 설정은 유지합니다.

처음 y=216으로 설정했을 때 첫 10초 집계는 0건이었습니다.
선과 안정화 구간을 지나는 차량을 이 짧은 구간에서 잡기 어려워,
원본의 실제 이동 경로를 보고 선을 y=259로 조정했습니다.
조정 후 자동 기록은 UP 6건, DOWN 0건입니다.
이 결과는 반대 방향의 실제 영상 동작 확인이며, 6건 모두에 대한 독립 정답
라벨 대조 및 누락률 검증까지 완료한 것은 아닙니다.

자동 확정 시각: 2.167, 3.900, 5.667, 6.300, 9.100, 9.700초.

```powershell
# apcms_ai 폴더에서 실행: 반대편 차로 첫 10초 검증
.\.venv312\Scripts\python.exe -m ai_vision.recognition.vehicle_tracking `
  --source "C:\Users\ICT-008\Downloads\traffic.mp4" `
  --max-seconds 10 `
  --line-y 0.36 --line-x 0.00 0.23 `
  --roi 0.00 0.18 0.35 0.18 0.23 0.40 0.00 0.50 `
  --output-dir ai_vision/results/recognition/traffic_up_validation_adjusted
```

- 영상·로그·요약: `ai_vision/results/recognition/traffic_up_validation_adjusted/`
- 원본 기준선 표시 이미지: `ai_vision/results/recognition/traffic_validation/up_line_0.jpg` ~ `up_line_3.jpg`

### 60초 전체 실행과 검토 자료 생성

두 방향을 각각 다른 ROI로 실행한 결과입니다. 전체 구간의 정답 대조는 아직
진행 전이며 아래 건수는 자동 집계입니다.

| 구간 | 분석 프레임 | 자동 통과 기록 | 예상 반대 방향 기록 |
|---|---:|---:|---:|
| 가까운 두 차로 | 1,800 | DOWN 42 | UP 0 |
| 반대편 차로 | 1,800 | UP 29 | DOWN 0 |

반대편 전체 결과: `ai_vision/results/recognition/traffic_up_full/`
전체 실행은 위 반대편 명령에서 `--max-seconds 10`을 빼고 출력 폴더를
`traffic_up_full`로 바꿔 재현할 수 있습니다.

각 실행 폴더의 `review/`에는 통과 전후 장면, 0.5초 간격 전체 장면,
자동 점검 결과, 판정표를 생성했습니다. 가까운 차로는 통과 검토 11장과
시간 순서 검토 10장, 반대편은 통과 검토 8장과 시간 순서 검토 10장입니다.

```powershell
# 기존 추적 결과를 읽고 검토 자료 생성: AI 추론이나 서버 전송 없음
.\.venv312\Scripts\python.exe -m ai_vision.recognition.review_tracking --run-dir ai_vision/results/recognition/traffic_up_full --expected-direction UP
```

같은 ID의 반복 기록, 예상과 다른 방향, 요약 건수 불일치를 자동 점검합니다.
같은 차량에 다른 ID가 붙은 경우는 이 검사로 판별할 수 없습니다.
CSV와 JSON의 수동 판정 상태는 `UNREVIEWED`로 두었으며, 정답 라벨을
검토한 것처럼 자동으로 채우지 않았습니다.

### 다음 검증

가림 구간의 추가 조사와 설정 비교는 [가림 구간 진단](VIDEO_ANALYSIS.md#occlusion)에 기록했습니다.
해상도 및 NMS 변경만으로 안정적인 개선을 확인하지 못해 기본 설정은 유지했습니다.

1. 두 방향의 전체 60초를 사람이 라벨링하고 누락·중복을 차량별로 대조
2. 차량 가림과 ID 변경 사례를 모아 추적 안정성 평가
3. 한국 차량 영상에서 추적 ID와 번호판 인식 결과 연결

현재 DOWN/UP은 화면 방향입니다. 실제 주차장 입차·출차 의미는 부여하지 않았으며,
이번 실행은 OCR과 HTTP 송신 모듈을 호출하지 않았습니다.


<a id="occlusion"></a>

## 가림 구간 실험 기록

이 절은 기존 traffic 영상의 제한된 범위 실험을 보존한 기록입니다. 독립 정답 라벨 평가가 아닙니다.

### 확인한 문제

원본 35~42초 부근의 가까운 왼쪽 차로를 확대해 확인했습니다.
한 차량에 서로 다른 크기의 상자가 겹치거나, 선 부근에서 추적 ID가 새로
생기는 사례가 있습니다. 따라서 서로 다른 ID는 서로 다른 실제 차량이라는
보장이 없습니다. 기존 자동 점검에서 같은 ID 중복이 0이었다는 사실만으로
실제 차량 중복이 없다고 결론 내릴 수 없습니다.

640 실험의 39.333초부터 ID 319는 y=421 부근에서 관찰되지만,
기준선 위쪽 상태(-1)가 안정적으로 확정되지 않은 채 아래쪽 상태(1)가 됩니다.
이 ID는 통과 이벤트를 만들지 않습니다. 원본 확대 장면과 함께 보면
누락 후보이며, 이전 ID와 같은 차량인지 확인이 필요합니다.
통과 이전 상태 없이 이벤트를 만들어 이를 보충하면 시작 차량과 오연결을
입출차로 잘못 처리할 수 있어 판별 규칙은 완화하지 않았습니다.

### 같은 원본 30~42초 구간 비교

각 실행은 30초에서 추적기를 새로 시작합니다. 첫 5초는 분석 관심 구간 전
차량 연결을 위한 구간이며, 전체 영상 시작부터 실행한 ID와 숫자가 다릅니다.
아래 자동 통과 건수는 정답 수치나 정확도가 아닙니다.

| 설정 | 자동 DOWN | ROI 내 관찰 ID | 실행 시간 |
|---|---:|---:|---:|
| 입력 640, NMS IoU 0.5 (기존 기본값) | 9 | 59 | 20.15초 |
| 입력 960, NMS IoU 0.5 | 11 | 71 | 31.59초 |
| 입력 640, NMS IoU 0.3, 클래스 통합 NMS | 8 | 32 | 23.84초 |

- 960에서는 39.967초 통과가 기록되지만 37.667/37.933/37.967초에
  겹치는 상자들이 다른 ID로 집계됩니다. 확대 프레임에서 중복 후보를
  확인했으므로 통과 건수가 많아졌다고 개선으로 보지 않습니다.
- NMS를 강화하면 상자는 줄지만 기존 34.833초 기록도 없어집니다.
  겹친 다른 차량의 탐지까지 제거할 수 있으므로 기본 설정으로 채택하지 않습니다.
- 결론: 기본값을 유지하고, 차량별 정답과 탐지 상자 품질을 함께 평가해야 합니다.
  이 실험에서 실제 차량 전체의 정답 집계나 해결 완료를 주장하지 않습니다.

### 추가한 진단 기능

#### 차량 두 대의 잠정 관찰 기준으로 대조

원본 36.5~40.5초의 가까운 왼쪽 차로를 0.25초 간격 확대 프레임으로 다시
확인했습니다. 파란 세단 뒤의 은색 SUV와 그 뒤의 작은 은색 차량을 구분해
`ai_vision/data/validation/traffic_occlusion_left.json`에 잠정 관찰 자료를 작성했습니다.
가림이 있어 정확한 중심점 통과 시각 대신 37.0~38.25초, 39.25~40.5초의
허용 구간으로 표시했습니다. 차량별 로그 대응은 이 넓은 시간 구간과 차로로
판단하므로, 아래 숫자는 이 관찰 기준에 한정됩니다.

| 설정 | 관찰 차량 | 일대일 대응 | 누락 후보 | 추가 중복 후보 |
|---|---:|---:|---:|---:|
| 기본 640 | 2 | 1 | 1 | 0 |
| 입력 960 | 2 | 2 | 0 | 2 |
| NMS 강화 | 2 | 1 | 1 | 0 |

`evaluate_crossings.py`는 한 차량에 여러 이벤트를 성공으로 붙이지 않으며,
검토한 시간·차로 밖의 기록은 평가에서 제외합니다. 같은 구간의 추가 기록은
중복 후보로 분리합니다. 이 비교에서는 기존 기본값 변경을 정당화할 개선이
확인되지 않았습니다. 독립적인 사람의 정답 라벨과 전체 영상 정확도는 아닙니다.

```powershell
# 기존 실험 결과와 잠정 관찰 자료 비교 (AI 실행·서버 전송 없음)
.\.venv312\Scripts\python.exe -m ai_vision.recognition.evaluate_crossings `
  --run-dir ai_vision/results/recognition/occlusion_640 `
  --annotations ai_vision/data/validation/traffic_occlusion_left.json
```

실행 폴더에 `evaluation_traffic_occlusion_left.json`이 생성됩니다.
`--run-dir`을 다른 두 실험 폴더로 바꾸면 같은 기준으로 비교할 수 있습니다.
평가 도구는 시간 구간이 겹치는 차량의 일대일 대응, 중복 후보, 역방향,
평가 범위 제외, 잘못된 차량 ID 라벨을 테스트했습니다.

#### 추적 방식 비교: BoT-SORT

탐지 모델, 입력 크기 640, NMS IoU 0.5, 기준선과 안정화 규칙을 유지한 채
`--tracker botsort`로 추적기만 바꿔 30~42초를 실행했습니다.

| 추적기 | 관찰 차량 | 일대일 대응 | 누락 후보 | 추가 중복 후보 |
|---|---:|---:|---:|---:|
| ByteTrack | 2 | 1 | 1 | 0 |
| BoT-SORT | 2 | 2 | 0 | 0 |

BoT-SORT는 37.667초 SUV와 39.800초 소형 차량을 각각 기록했습니다.
이 12초 실행 전체에서는 DOWN 10건, UP 0건이며, 입력 960 실험에서 보인
37초대 여러 이벤트가 동일 관찰 차량에 몰리는 현상은 이 관찰 범위에서 없었습니다.
결과: `ai_vision/results/recognition/occlusion_botsort/`.

BoT-SORT는 설치된 라이브러리의 기본 설정을 사용합니다. 해당 설정에서
외형 재식별(ReID)은 꺼져 있으며 추가 모델 다운로드나 설치는 수행하지 않았습니다.
추적 방식 변경이 모든 가림 상황을 해결한다는 의미는 아닙니다.

전체 60초를 처음부터 실행한 결과도 문제 구간의 두 차량과 일대일 대응했고,
해당 잠정 관찰 범위의 누락·추가 중복 후보는 모두 0건입니다.

- 전체 DOWN 기록: ByteTrack 42건, BoT-SORT 44건
- 기존 42건은 시각 ±0.35초, 통과 x좌표 ±40px 조건으로 모두 대응
- 추가 기록: 39.800초 소형 차량(관찰 자료와 대응), 45.567초 차량(독립 정답 확인 필요)
- 첫 10초 DOWN 8건과 반대편 첫 10초 UP 6건의 기록도 유지
- BoT-SORT 전체 실행은 UP 0건, 결과 영상은 1,800프레임·30fps·60초로 저장 확인

전체 결과와 비교 기록은 `ai_vision/results/recognition/traffic_botsort_full/`의
`tracking.mp4`, `regression.json`, `evaluation_traffic_occlusion_left.json`에 있습니다.
이전 결과와 대응한다는 것은 이전 결과가 정답임을 증명하지 않습니다.
부분 구간의 개선이 확인된 선택 옵션으로 제공하며 기본 추적기는 ByteTrack을 유지합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.vehicle_tracking `
  --source "C:\Users\ICT-008\Downloads\traffic.mp4" `
  --start-seconds 30 --max-seconds 12 --tracker botsort --save-observations `
  --output-dir ai_vision/results/recognition/occlusion_botsort
```

#### 구간 실행과 프레임 진단

`vehicle_tracking.py`에 다음 선택 옵션을 추가했습니다.

```powershell
# apcms_ai 폴더에서 원본 30~42초를 재현
.\.venv312\Scripts\python.exe -m ai_vision.recognition.vehicle_tracking `
  --source "C:\Users\ICT-008\Downloads\traffic.mp4" `
  --start-seconds 30 --max-seconds 12 --save-observations `
  --output-dir ai_vision/results/recognition/occlusion_640
```

- `--start-seconds`: 처리 시작 시각. 저장 영상은 선택 구간이며 로그는 원본 시각 유지
- `--max-seconds`: 시작 시점부터 처리할 길이
- `--save-observations`: 프레임별 ID, 탐지 상자, 중심점, 후보/확정 상태를 JSONL로 저장
- `--nms-iou`, `--agnostic-nms`: 실험용 겹침 제거 옵션. 기존 기본 동작 유지
- `review_tracking.py`도 시작 시각을 읽어 30초 구간을 0초로 잘못 검토하지 않도록 수정

결과 폴더는 `ai_vision/results/recognition/occlusion_640`, `occlusion_960`,
`occlusion_nms030`입니다. 실행마다 별도 폴더를 사용해 비교 근거를 보존합니다.
진단 파일은 로컬 전용이며 OCR, .env, 서버 송신 모듈을 호출하지 않습니다.

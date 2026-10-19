# 영상별 설정 파일

추적 실행 도구와 통합 실행 도구에서 `--config`로 같은 JSON 설정을 사용합니다.
카메라 번호가 아니라 영상의 촬영 구도에 맞춘 ROI·기준선·추적기 설정입니다.
실제 카메라 영상은 아직 없으므로 아래 설정은 traffic 영상 전용입니다.

## 준비한 두 설정

| 설정 파일 | 분석 영역 | 기준선(1280×720 기준) | 추적기 |
|---|---|---|---|
| `ai_vision/data/tracking_configs/traffic_near.json` | 가까운 두 차로 | y=432, x=192~1152 | BoT-SORT |
| `ai_vision/data/tracking_configs/traffic_far.json` | 반대편 차로 | y=259, x=0~294 | ByteTrack |

설정 파일의 좌표는 픽셀이 아니라 0~1 비율입니다. ROI는 화면 테두리를
따라 순서대로 나열한 네 꼭짓점의 x/y 비율 8개입니다.
번호판, API 키, 서버 주소, 입차/출차 방향 매핑은 설정에 포함하지 않습니다.

## 실행 예시

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

## 적용 우선순위와 검사

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

## 검증 결과

- 두 설정으로 각각 실제 영상 첫 3초를 실행: 90프레임 처리
- 가까운 차로 DOWN 1건, 반대편 차로 UP 1건으로 기존 기록과 대응
- 결과 위치: `ai_vision/results/recognition/config_near_smoke/`, `config_far_smoke/`
- 우선순위, 기존 기본값, 오타, 유효하지 않은 좌표, 빈 ROI, 기존 픽셀 좌표 재현
  테스트 6개를 포함해 관련 테스트 총 26개 통과
- 새 Python 파일과 수정 파일의 첫 줄 경로 주석 및 한국어 설명 유지
- HTTP 전송 비활성화. 실제 한국 차량 입출차 통합 검증은 미완료

# 가림 구간 추적 진단

## 확인한 문제

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

## 같은 원본 30~42초 구간 비교

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

## 추가한 진단 기능

### 차량 두 대의 잠정 관찰 기준으로 대조

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

### 추적 방식 비교: BoT-SORT

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

### 구간 실행과 프레임 진단

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

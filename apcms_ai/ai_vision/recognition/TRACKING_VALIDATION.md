# traffic.mp4 방향 판별 검증 기록

## 검증 범위와 방법

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

## 가까운 차로: DOWN

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

## 반대편 차로: UP

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

## 60초 전체 실행과 검토 자료 생성

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

## 다음 검증

가림 구간의 추가 조사와 설정 비교는 [가림 구간 진단](OCCLUSION_ANALYSIS.md)에 기록했습니다.
해상도 및 NMS 변경만으로 안정적인 개선을 확인하지 못해 기본 설정은 유지했습니다.

1. 두 방향의 전체 60초를 사람이 라벨링하고 누락·중복을 차량별로 대조
2. 차량 가림과 ID 변경 사례를 모아 추적 안정성 평가
3. 한국 차량 영상에서 추적 ID와 번호판 인식 결과 연결

현재 DOWN/UP은 화면 방향입니다. 실제 주차장 입차·출차 의미는 부여하지 않았으며,
이번 실행은 OCR과 HTTP 송신 모듈을 호출하지 않았습니다.

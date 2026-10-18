# 통과 차량의 추적 ID와 번호판 연결

추적과 OCR을 한 명령으로 실행하거나 기존 결과를 결합하려면
[통합 실행 도구](VIDEO_PIPELINE.md)를 사용하세요.

## 구현 내용

1. 기존 `vehicle_tracking.py`로 통과 기록과 프레임별 관찰 정보를 저장합니다.
2. `recognize_tracked_passages.py`가 통과한 각 ID의 원본 화면을 선택합니다.
3. 기존 `recognizer.py`의 번호판 탐지·영역 추출·PaddleOCR 함수를 재사용합니다.
4. `plate_consensus.py`가 서로 다른 시점의 번호판 결과를 비교합니다.
5. 방향과 번호판 관찰 결과는 `LOCAL_TRACKED_PASSAGE`로 로컬에만 저장합니다.

기존 인식기, FastAPI, 이벤트 송신기, Boot 코드는 수정하지 않았습니다.
이 모듈은 이벤트 송신기나 `.env`를 불러오지 않으며 HTTP 전송 기능이 없습니다.
동영상의 DOWN/UP을 실제 ENTRY/EXIT로 바꾸거나 현재 날짜를 촬영 날짜로 붙이지 않습니다.

## 번호판 확정 규칙

- 같은 추적 ID에서 통과 전 2초~통과 후 0.75초의 화면 중 최대 3장을 선택
- 최소 0.25초 이상 떨어진 서로 다른 프레임을 사용
- `KOREAN_VALID`와 문자열 형식 검사를 모두 통과한 동일 번호가 최소 2회 필요
- 서로 다른 유효 번호가 나오면 다수결로 덮어쓰지 않고 `CONFLICT`
- 외국 번호판, 형식 오류, 한 번만 읽힌 번호판은 확정하지 않음

반복 인식도 실제 번호판 정답이나 추적 ID의 정확성을 보장하지 않습니다.
특히 차량 가림으로 다른 차량의 번호판이 상자 안에 들어갈 수 있어 실제 영상 검증이 필요합니다.
`plate_detection_confidence`는 번호판 상자 탐지 신뢰도이며 OCR 정확도 점수가 아닙니다.

## 기존 traffic 영상에서 재현

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

## 실제 실행 결과와 범위

- 기존 `car12.png`: `91소6408`, `KOREAN_VALID` 재확인.
  1차 `91소64089`는 REVIEW, 기존 전처리 재시도에서 정상 번호를 인식했습니다.
  이는 정지 이미지 인식 검증이며 이동 차량 통합 검증은 아닙니다.
- `traffic_botsort_full`의 ID 6, 7: 각 3개 프레임에 실제 번호판 탐지와 OCR 실행.
  영문·숫자를 읽었고 두 차량 모두 `NO_VALID_KOREAN_PLATE`로 처리했습니다.
- 저장 위치: `ai_vision/results/recognition/traffic_ocr_local/`.
- 번호판 합의 규칙 5개를 포함해 관련 테스트 총 15개 통과.
- 처음 OCR 실행은 샌드박스 임시 폴더 권한으로 실패했습니다.
  실행 권한을 부여한 동일 로컬 모델 재실행에서 정상 처리했으며 인식기 코드를
  변경하거나 모델·패키지를 새로 설치하지 않았습니다.

## 한국 차량 영상이 없을 때: 웹캠 원본 촬영 도구

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

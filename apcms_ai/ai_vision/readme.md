# APCMS AI Vision 시작 안내

이 문서를 시작점으로 사용합니다. 설명서는 기능마다 추가하지 않고 아래 세 분야에
통합합니다. 모든 실행 명령의 기준 폴더는 `D:\finalProjectB\back\apcms_ai`입니다.

| 필요한 작업 | 설명서 |
|---|---|
| 영상 추적·ROI/기준선·번호판 OCR·촬영·기존 실험 확인 | [영상 분석과 번호판 인식](docs/VIDEO_ANALYSIS.md) |
| 결과 API·CSV 내보내기·수동 정답 검토·HTML·진단 | [저장 결과 조회와 검토](docs/RESULTS_REVIEW.md) |
| Boot 요청 규격·중복 억제·응답 처리·HTTP 경로 | [입출차 연동과 중복 억제](docs/VEHICLE_INTEGRATION.md) |

## 현재 구현과 검증 범위

- 저장 영상의 차량 추적 → 화면 방향 UP/DOWN 판정 → 통과 ID별 OCR → 결과 저장
- 저장 결과 조회·검색·CSV, 수동 번호판 정답 비교, 오프라인 이미지 검토, 로그 연결 진단
- 입출차 요청 검증·초안·메모리 중복 억제·응답 분류·기본 비활성 HTTP 클라이언트
- 최근 기능 작업의 자동 테스트 426개 통과. HTTP 활성 경로는 모의 세션으로 검증
- 카메라 프레임 수집·추적·OCR·기본 비활성 전송 판단의 세션 루프 구현
- 종료된 실시간 세션 요약 검사와 HTML·CSV 보고서 생성
- 카메라 실행 전 설정·설치 정보·모델 파일 점검, 선택적인 한 프레임 장치 확인
- 실행 장애 시 별도 실패·복구 기록과 저장 폴더 상태 검사
- 카메라 읽기·추적/OCR 처리 시간과 차량 관찰 통계의 저장·HTML 표시
- 실행 당시 추적 설정·카메라 번호·실행 제한의 사본 보존과 보고서 표시
- 실시간 ROI 이탈·위치 점프 시 위치 상태와 OCR 표본의 연결 초기화
- 세션 시각 기록에서 만료된 OCR crop 제외 및 표본 부족 시 보류 처리
- 실시간 처리기 직접 호출 시 중복·역순 프레임과 잘못된 시각 차단, 시각 보관 경계 역행 방지
- 실제 카메라 열기·읽기 실패와 합성 입력의 정상 종료 구분
- 다음 카메라 읽기 전 시간 제한 재검사와 검사 내역 표시
- 저장된 번호판 판정·투표 정보 일관성 검사와 확정 조건 표시
- 손상된 통과 기록의 필수 항목·자료형 검사 및 전송 판단·처리 건수 변경 전 거부
- 이미지 파일 또는 카메라 한 프레임으로 ROI·기준선 미리보기 저장
- 차량·번호판·OCR 모델을 역할별 최초 사용 시 생성해 불필요한 초기 로딩 방지
- 이미지 인식 API의 작업 스레드 실행과 공유 모델의 역할별 추론 직렬화
- 이미지 업로드 10MB·2천만 픽셀 제한과 디코딩 전 입력 검사
- 프로세스당 인식 요청 2개 제한과 실행 완료·취소에 따른 슬롯 반환
- OCR 재시도 이미지 확대 한도와 임시 PNG 저장
- DB 없는 회귀 검사 단일 명령과 PC별 Python·패키지 버전 비교
- 별도 프로세스에서 API·영상·OCR 패키지 import 실패·시간 초과 점검
- 실제 카메라 하드웨어·한국 번호판 주행·HTTP 활성화와 Boot·DB 통합 검증은 아직 남음
- 한국 번호판 주행 영상의 정확도는 미검증. traffic 영상은 외국 번호판 영상

`CONFIRMED`는 반복 OCR의 일치, `COMPLETED`는 실행 완료, 진단 `PASS`는 저장 로그의
일관성을 뜻합니다. 실제 정답 정확도 합격과 구분합니다. 화면 DOWN/UP을 설치 방향
확인 없이 ENTRY/EXIT로 매핑하지 않습니다. UUID는 DB에 저장하지 않는 설계입니다.

## 작업 환경과 서버 실행

### Linux·Docker 배포 준비

Vision 전용 서버는 `python -m uvicorn ai_vision.app:app --host 0.0.0.0 --port 8000 --workers 1`
로 실행합니다. 문의·추천 모듈을 가져오지 않으며 모델은 최초 사용 시 불러옵니다.
`/health`는 프로세스 응답만 확인합니다. `/ready`는 YOLO 모델 두 개의 읽기 가능 여부와
결과 볼륨의 실제 JSON 쓰기·읽기·정리를 검사합니다. 임시 점검 폴더만 만들고 제거하며,
파일·볼륨 오류 또는 잘못된 로컬 OCR 설정이면 503을 반환합니다. Docker healthcheck는
`/ready`를 사용합니다. 정상 결과 `CHECKED`도 추론·GPU·카메라 준비 완료를 보장하지 않습니다.
기존 통합 `main:app`의 실행 방식은 유지합니다.

`ai_vision/Dockerfile`과 `requirements-runtime.txt`는 Python 3.12·Linux amd64·CPU용
배포 후보입니다. 2026-10-21 회사 PC에서는 Docker Linux 엔진이 실행 중이지 않아 이미지
빌드·Linux 패키지 설치·실제 추론은 검증하지 못했습니다. GPU·ARM 배포에는 그대로 사용하지
말고 해당 연산 패키지와 플랫폼 지원을 별도로 확인합니다. 버전 목록은 전체 의존성 잠금
파일이 아니며, 빌드 시 `pip check`도 수행합니다.

```bash
# 기준 폴더: apcms_ai. 코드만 이미지에 넣고 모델·결과는 별도 보관합니다.
docker build --platform linux/amd64 -f ai_vision/Dockerfile -t apcms-vision:cpu .
docker run --rm -p 8000:8000 \
  --mount type=bind,src=/srv/vision/models,dst=/app/ai_vision/models,readonly \
  --mount type=bind,src=/srv/vision/data,dst=/app/ai_vision/data,readonly \
  --mount type=bind,src=/srv/vision/results,dst=/var/lib/vision/results \
  --mount type=bind,src=/srv/vision/cache,dst=/home/vision/.paddlex \
  apcms-vision:cpu
```

호스트의 네 폴더는 미리 만들고, 결과·캐시는 컨테이너 UID 10001이 쓸 수 있도록 소유권을
설정합니다. 모델에는 `yolo11n.pt`, `license_plate_yolov8n.pt`를 준비합니다. 데이터 볼륨을
연결하면 이미지 안의 기본 데이터가 가려지므로 필요한 설정·주차면 좌표·기준 사진도
호스트 데이터 폴더에 준비해야 합니다. OCR 최초 실행에는 한국어 모델 다운로드가 필요할
수 있으며 캐시는 실제 컨테이너에서 준비하고 검증합니다. 완전 오프라인 Linux 실행은 미검증입니다.

다운로드 대신 준비한 OCR 추론 모델을 사용하려면 `VISION_OCR_DETECTION_MODEL_DIR`와
`VISION_OCR_RECOGNITION_MODEL_DIR`를 함께 지정합니다. 상대 경로는 `VISION_MODEL_DIR`
기준입니다. 각 폴더에 `inference.yml`, `inference.pdiparams`, `inference.json` 또는
`inference.pdmodel`이 있어야 합니다. 파일 읽기 여부를 검사한 뒤 PaddleOCR에 전달하며,
한쪽만 지정하거나 파일이 없으면 캐시·다운로드 방식으로 되돌리지 않고 오류로 처리합니다.
Docker에서는 `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True`로 모델 공급처의 import 시점
접속 확인을 끕니다. 이는 모델 다운로드 자체를 차단하는 옵션은 아니므로 오프라인 배포는
로컬 모델 경로도 함께 지정해야 합니다.
실제 모델 조합과 파일 무결성은 추론으로 검증해야 합니다. 환경변수가 없으면 기존
캐시·다운로드 동작을 유지하며 `/ready`에서도 OCR 캐시는 미검증으로 표시합니다.

프런트가 Vision 전용 서버를 직접 호출한다면 `VISION_CORS_ORIGINS`에
`["https://frontend.example"]`처럼 JSON 목록을 지정합니다. 기본은 빈 목록이며 경로·인증정보·
와일드카드 origin은 거부합니다. 교차 출처 쿠키는 기본 허용하지 않습니다. Boot가 내부에서
호출하는 경우에는 브라우저 CORS 설정이 필요하지 않습니다. 잘못된 설정은 서버 시작 시
명시적으로 거부합니다. 모델·읽기 권한·필수 패키지·로컬 OCR 설정 누락으로 인식할 수 없으면
`/recognize`는 내부 경로를 노출하지 않고 503을 반환합니다.

환경변수 `VISION_MODEL_DIR`, `VISION_DATA_DIR`, `VISION_RESULT_DIR`, `VISION_TEST_IMAGE_DIR`
로 공통 경로를 지정합니다. 상대 경로는 `ai_vision` 폴더 기준이며 빈 값은 거부합니다.
환경변수는 Python 프로세스를 시작하기 전에 설정합니다. Boot 접속 주소는 컨테이너 내부의
`localhost` 대신 접근 가능한 서비스 주소로 지정하며 전송 활성화는 기존 설정을 따릅니다.

OpenCV는 현재 Ultralytics와 PaddleX의 의존성 때문에 기본·contrib 배포판이 함께 필요하여
배포 후보에서는 둘을 4.10.0.84로 맞췄습니다. headless 배포판을 추가로 혼합하지 않습니다.
Linux 공유 라이브러리 `libgl1`, `libglib2.0-0`, `libgomp1`을 이미지에 설치하며, 이 조합은
Linux 실제 import·추론 검증이 남아 있습니다. 개발용 NumPy는 통합 AI 조건과 동일하게
1.26.4로 정리했습니다. 이번 작업에서 회사 가상환경 패키지를 재설치하지 않았습니다.

실시간 처리·수동 촬영은 서버에 카메라 장치를 연결한 경우에만 사용할 수 있습니다.
AWS가 회사 USB 카메라를 직접 볼 수는 없습니다. 현재 실시간 CLI는 정수 장치 번호를
사용하며 RTSP 주소 입력은 아직 지원하지 않습니다. 녹화 도구는 `--no-preview`를 지정하면
GUI 호출 없이 저장하며, 수동 R 키 인식 도구는 화면이 있는 개발 PC에서만 사용합니다.

GUI 좌표 편집기, 구형 `object_detector_test.py`, 송신기 백업과 안전 분야 속도 실험은
배포 이미지에서 제외합니다. 좌표 선택기·편집기와 구형 탐지·안전 속도 측정 도구는
import 시 GUI·폴더 생성을 하지 않도록 보완했고, 공통 볼륨 경로를 사용합니다. GUI 도구는
화면이 있는 개발 PC에서 명시적으로 실행합니다. 송신기 백업은 운영 코드로 사용하지 않습니다.
주차 API는 누락·권한 오류·잘못된 인코딩·중복 키·NaN·손상 JSON을 503으로 반환합니다.
편집기의 읽기 전용 저장 실패도 503으로 응답하고, 좌표·점유 결과는 원자적으로 저장합니다.
전체 `.py` 파일은 실행 없이 구문 검사했습니다. 배포 테스트를 통합 검사에 포함했으며,
전체 426개는 Windows에서 통과했습니다. 다음 명령으로 실행합니다.

```bash
python -m unittest ai_vision.tests.recognition.test_deployment_runtime
python -m ai_vision.tests.run_checks
python -m ai_vision.recognition.deployment_readiness
python -m ai_vision.recognition.probe_runtime_imports --profile vision --timeout 60
python -m ai_vision.recognition.probe_runtime_imports --profile ocr --timeout 60
```

중복 억제와 요청 제한은 프로세스 메모리에 있으므로 worker·컨테이너를 늘리면 공유되지
않고 재시작 시 초기화됩니다. 현재 Docker 실행은 worker 하나를 사용합니다.

공통 JSON 읽기는 파일이 도중에 커져도 실제 읽기량을 상한+1바이트로 제한합니다.
JSON 중첩은 Python 재귀 설정과 무관하게 128단계로 제한합니다. 주차면 좌표의 해상도·ID·
꼭짓점과 저장 결과의 상태·변화율·건수 합계를 검사하고, 손상된 주차 결과는 503을 반환합니다.

2026-10-21 회사 Windows 환경에서는 기존 로컬 모델 파일로 차량·번호판 YOLO의 CPU
합성 이미지 추론과 PaddleOCR 초기화·합성 이미지 추론을 실제 실행했습니다. 로컬 OCR은
`inference.yml`의 `Global.model_name`을 안전하게 읽어 모델 이름과 경로를 함께 전달합니다.
경로만 지정하면 PaddleOCR 기본 모델 이름과 충돌하는 문제가 있어 이 부분을 수정했습니다.
흰색 합성 이미지의 YOLO 결과는 탐지 0건, OCR 결과는 빈 문자열이며, 정상 번호판 정확도나
Linux·GPU 호환성을 검증한 결과는 아닙니다. 회사 캐시는 다운로드 없이 사용했고 별도
패키지 설치는 하지 않았습니다.
녹화·추적 결과 요약도 원자적으로 저장하며, 카메라 해제가 실패해도 영상 저장기는
계속 해제합니다. 처리 중 발생한 원래 오류는 정리 오류로 바꾸지 않습니다. 다만 OpenCV
저장기가 디스크 부족 등의 실패를 예외 없이 반환하는 상황까지 탐지하는 것은 아닙니다.

### 집·새 PC에서 DB 없이 이어서 작업

1. 회사에서 작업을 피처 브랜치에 커밋·Push하고, 새 PC에서 같은 브랜치를 받습니다.
2. Python 3.12로 `.venv312`를 새로 만듭니다. 기존 가상환경 폴더를 복사하지 않습니다.
3. 저장소에 포함한 [회사 환경 버전 기록](data/runtime/company_windows_py312.json)을
   패키지 준비에 참고합니다. 이 파일을 커밋·Push하면 집에서도 같은 브랜치로 받습니다.
4. 환경 비교와 회귀 검사를 실행합니다. 이 검사에는 DB·실제 모델·카메라가 필요하지
   않지만 API 테스트를 위한 내부 루프백 통신과 임시 파일 쓰기는 허용되어야 합니다.
5. 실제 영상·OCR 작업을 할 때에는 모델 파일·PaddleOCR 캐시와 테스트 자료도 준비합니다.
   Boot·DB 반영은 별도 통합 검증이며 기본 비활성 전송 상태로 개발할 수 있습니다.

```powershell
# 모든 명령은 받은 저장소의 apcms_ai 폴더에서 실행합니다.
py -3.12 -m venv .venv312

# 집 PC: 저장소에 포함된 회사 기록과 비교 (패키지를 준비한 뒤 실행)
.\.venv312\Scripts\python.exe -m ai_vision.recognition.check_runtime_environment `
  --compare ai_vision/data/runtime/company_windows_py312.json

# 검사 목록만 확인: 테스트 모듈을 불러오지 않습니다.
.\.venv312\Scripts\python.exe -m ai_vision.tests.run_checks --list

# DB·실제 모델·카메라 없는 전체 회귀 검사
.\.venv312\Scripts\python.exe -m ai_vision.tests.run_checks
```

버전 기록에는 선택한 패키지의 설치 정보와 Python·운영체제 정보만 포함합니다.
회사 기준 기록은 2026-10-20에 복사한 Windows·Python 3.12.7 환경입니다.
현재 환경을 새로 기록하려면 `--output ai_vision/results/company_runtime.json`을 사용합니다.
이 새 결과는 Git 제외 대상이므로 회사 기준을 갱신할 때에만 내용을 확인해 위 기준 파일에
반영하고 함께 커밋합니다. 기존 결과 파일이 있으면 다른 이름으로 저장합니다.
환경변수·접속 정보·개인 경로는 수집하지 않습니다. 기록은 설치 스크립트나 전체 의존성
잠금 파일이 아닙니다. 같은 버전이라도 실제 모델·GPU·드라이버 호환성은 따로 확인합니다.
기존 requirements와 설치된 버전은 차이가 있으므로 기록만 보고 모든 패키지를 자동으로
재설치하지 않습니다. 비교 종료 코드는 일치 0, 차이 1, 입력·출력 오류 2입니다.

통합 검사는 구형 YOLO·PaddleOCR 실험 스크립트를 자동 수집하지 않고 명시된 회귀 검사만
실행합니다. 실패·의존성 누락·환경 오류는 성공이나 생략으로 바꾸지 않습니다.
`--failfast`는 첫 실패에서 중단하고 `-v`는 검사명을 표시합니다.

설치 버전이 같아도 DLL·의존성 충돌로 패키지를 불러오지 못할 수 있습니다. 아래 명령으로
실제 import를 별도 프로세스에서 확인합니다. 실패해도 나머지 패키지 점검을 이어가며
결과는 패키지별 `IMPORTED`, `FAILED`, `TIMEOUT`, `PROCESS_ERROR`로 표시합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.probe_runtime_imports --profile api
# 영상·OCR 의존성은 해당 작업을 준비할 때 선택합니다.
.\.venv312\Scripts\python.exe -m ai_vision.recognition.probe_runtime_imports --profile vision --timeout 60
.\.venv312\Scripts\python.exe -m ai_vision.recognition.probe_runtime_imports --profile ocr --timeout 60
```

제한 시간은 패키지 하나당 1~300초입니다. 모두 성공하면 종료 코드 0, 하나라도 실패하면
1입니다. 이 점검은 모델을 직접 생성하거나 카메라·DB를 사용하지 않지만, 외부 패키지의
import 초기화 코드는 실행됩니다. 추론·GPU 작동·FastAPI 요청 처리 성공은 별도 확인이
필요합니다. 외부 패키지 출력 원문은 개인 경로 등의 노출을 막기 위해 보고서에서 제외합니다.

실시간 사전 점검에서도 `check_live_gate` 명령에 `--probe-imports`를 추가하면 영상·OCR
패키지를 함께 검사합니다. `--import-timeout 60`으로 패키지별 제한 시간을 조절합니다.
설치·모델 파일 누락 시 import는 `SKIPPED_MISSING_ENVIRONMENT`로 표시합니다.
import 실패 시 전체 결과는 `BLOCKED`이며, `--probe-camera`를 함께 지정했더라도 카메라를
열지 않습니다. 기본 옵션에서는 import 점검을 실행하지 않습니다. import 성공도 모델
추론·패키지 조합의 전체 호환성을 보장하지 않으므로 기존 미검증 항목은 유지합니다.

기존 `.venv312` 환경을 사용합니다. 통합 `requirements.txt`와
`ai_vision/requirements.txt`는 조건 차이가 있으므로 문서 확인만을 위해 기존 환경에
일괄 재설치하지 않습니다. 아래 명령은 PowerShell에서 사용합니다.

```powershell
cd D:\finalProjectB\back\apcms_ai
$env:PYTHONIOENCODING = "utf-8"

# Vision·문의·추천을 등록한 통합 AI 서버. 기존 모델을 불러올 수 있음
.\.venv312\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

결과 조회만 할 때에는 별도 창에서 모델 없는 앱을 실행할 수 있습니다.

```powershell
.\.venv312\Scripts\python.exe -m uvicorn ai_vision.recognition.results_api:app --host 127.0.0.1 --port 8001
```

주요 Vision 경로는 `/recognize`, `/parking/occupancy`, `/vision/runs`입니다.
저장 결과 조회 서버의 Swagger는 `http://127.0.0.1:8001/docs`입니다.
서버를 실행하는 것과 실시간 카메라·입출차 전송을 활성화하는 것은 별개입니다.

## 가장 짧은 영상 분석 예시

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_video_pipeline `
  --source "C:\Users\ICT-008\Downloads\traffic.mp4" `
  --config ai_vision/data/tracking_configs/traffic_near.json `
  --max-seconds 3 --max-tracks 1 `
  --output-dir ai_vision/results/recognition/my_pipeline_01
```

입력 영상·기존 모델이 로컬에 있어야 합니다. 재실행 시 출력 폴더 이름을 바꿉니다.
이 영상은 한국 번호판이 아니므로 `NO_VALID_KOREAN_PLATE`가 예상되는 결과입니다.
나머지 실행 옵션과 결과 파일은 [영상 분석](docs/VIDEO_ANALYSIS.md#pipeline)에 있습니다.

## 주요 연동 기능 자동 검사

실제 HTTP 요청 없이 검증합니다. 아래는 최근 전체 369개 중 HTTP·후보 변환·전송
흐름 관련 22개 테스트만 실행하는 명령입니다. 구형 실험 스크립트가 함께 있어
recognition 폴더 전체를 무조건 discover하는 방식은 사용하지 않습니다.

```powershell
.\.venv312\Scripts\python.exe -m unittest `
  ai_vision.tests.recognition.test_vehicle_http `
  ai_vision.tests.recognition.test_vehicle_delivery_flow `
  ai_vision.tests.recognition.test_vehicle_live_candidate `
  ai_vision.tests.recognition.test_run_vehicle_delivery_check -v
```

영상 전체 정답 비교와 하드웨어·실제 서버 검증은 자동 검사와 별도로 진행합니다.
실행 결과·모델·가상환경·환경변수는 Git 업로드에서 제외합니다.

FastAPI API 테스트는 Windows asyncio의 내부 루프백 소켓을 사용할 수 있는 환경에서
실행해야 합니다. 제한된 환경에서는 API 호출 전에 `ASYNCIO_RUNTIME_UNAVAILABLE`로
종료합니다. 이는 테스트 성공이나 생략이 아닙니다. 원인과 확인 방법은
[결과 API 실행 환경](docs/RESULTS_REVIEW.md#api-runtime)에 정리했습니다.

## 모델·라이브러리 용어

| 이름 | 역할 |
|---|---|
| YOLO / Ultralytics | 영상·이미지의 차량과 번호판 영역 탐지 |
| `yolo11n.pt` / COCO | COCO 데이터로 사전 학습된 차량 탐지 모델 |
| PyTorch / torchvision | YOLO 계산과 관련 이미지 기능 |
| PaddleOCR / PaddlePaddle | 번호판 문자 인식 / 계산 엔진 |
| OpenCV / NumPy / Pillow | 프레임·배열·이미지 처리 |
| matplotlib / lap | 결과 시각화 / 추적 객체 연결 계산 |
| FastAPI / uvicorn / python-multipart | API / 서버 실행 / 이미지 업로드 처리 |
| EasyOCR / Ko-TrOCR | 기존 비교 후보. 현재 주 인식기는 PaddleOCR |
| transformers / sentencepiece | Ko-TrOCR 같은 모델 사용·토큰 처리 시 사용하는 라이브러리 |

탐지 신뢰도는 모델 점수이며 그 값을 차량·번호판의 실제 정답 확률이나 OCR 정확도로
해석하지 않습니다. 설치 패키지는 위 용어 목록보다 프로젝트 requirements를 기준으로 확인합니다.

## 정지 이미지 인식 API 응답 예시

아래는 기존 정지 이미지 테스트에서 저장한 예시입니다. 주행 영상 검증 결과가 아닙니다.

```json
{
    "success": true,
    "message": "차량 인식 처리가 완료되었습니다.",
    "vehicle_fallback_used": false,
    "vehicle_count": 1,
    "vehicles": [
        {
            "vehicle_index": 1,
            "vehicle_type": "car",
            "vehicle_confidence": 0.6485,
            "vehicle_box": {
                "x1": 10,
                "y1": 26,
                "x2": 1411,
                "y2": 1074
            },
            "plate_detected": true,
            "plate_confidence": 0.9736,
            "plate_number": "91소6408",
            "plate_type": "KOREAN_VALID",
            "first_ocr": "91소6408O©",
            "first_type": "REVIEW",
            "retry_ocr": "91소6408",
            "retry_type": "KOREAN_VALID"
        }
    ]
}
```

| 필드 | 의미 |
|---|---|
| success / message | 요청 처리 성공 여부와 설명 |
| vehicle_fallback_used | 기본 탐지 기준 미달 시 완화된 기준으로 재탐지했는지 |
| vehicle_count / vehicles | 탐지된 차량 수 / 차량별 결과 |
| vehicle_index / vehicle_type | 차량 순서 / car·truck·bus·motorcycle 등 참고 분류 |
| vehicle_confidence / vehicle_box | 차량 탐지 점수 / 원본 영상의 x1·y1·x2·y2 상자 |
| plate_detected / plate_confidence | 번호판 탐지 여부 / 번호판 탐지 점수 |
| plate_number / plate_type | 최종 번호 문자열 / 형식 분류 |
| first_ocr / first_type | 첫 인식 문자열과 분류 |
| retry_ocr / retry_type | 전처리 후 재인식 문자열과 분류 |

`plate_type`은 KOREAN_VALID, FOREIGN_OR_OTHER, REVIEW, OCR_FAILED 등으로 구분합니다.
REVIEW/OCR_FAILED 시 확대·그레이스케일·CLAHE 등의 전처리 후 재시도할 수 있습니다.
형식상 KOREAN_VALID인 것과 여러 프레임에서 CONFIRMED인 것, 사람이 정답을 확인한
것은 서로 다른 단계입니다.

## 문서 유지 기준

실행·검토·연동 내용은 해당 분야 설명서에 추가합니다. 기능별·커밋별 새 설명서를
계속 만들지 않습니다. 과거 실험은 영상 분석 문서의 검증 기록에 남기고, 현재 상태와
구분합니다. 코드 설명은 해당 Python 파일의 경로 주석과 한국어 설명 주석을 유지합니다.

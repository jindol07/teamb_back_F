# 주차 A/B 카메라 원본 프레임 → 화재·연기 감지 연결 (AI Vision 전용)

기준: 2026-10-27 GitHub `develop`의 `live_fire_smoke.py`와 `FRAME_EXCHANGE_INTERFACE.md` v1.

## 범위

주차 소스는 **절대 변경하지 않습니다**. 현재 진행 중인 주차 코드 수정과 충돌하지 않도록 화재 감지기 `live_fire_smoke.py`만 정확한 문자열 위치에 패치하고 아래 2개 파일을 새로 추가합니다.

- `ai_vision/safety/shared_frame_source.py`: `ai_vision.parking.frame_exchange.read_latest` 수신용 어댑터
- `ai_vision/tests/safety/test_shared_frame_source.py`: 카메라·HTTP 없는 계약 단위 테스트
- `ai_vision/safety/live_fire_smoke.py`: 공유 입력 CLI·상태 처리·카메라 구분 최소 변경

기존 화재 판단(최근 5회 중 3회), FIRE/SMOKE YOLO 추론, 증거 파일, 사건 상태 이력, `fire_alert_live.py` 자동 송신을 그대로 사용합니다. A/B는 서로 **다른 화재 프로세스와 출력 폴더**를 사용합니다.

## 사전 조건 — 주차 담당 구현 확인

코덱스 쪽 `frame_exchange.py`는 전달 문서에 구현 완료라고 나와 있으나 **검증한 GitHub develop에는 2026-10-27 기준 아직 없었습니다**. 먼저 로컬에 다음 파일이 있어야 합니다.

```powershell
Test-Path .\ai_vision\parking\frame_exchange.py
```

`True`가 나와야 합니다. 주차 담당이 기존 runtime JSON에 `frame_export_dir`, `frame_export_fps` 설정을 추가해 실행해야 하며, 런타임이 만든 **현재** `frame_export_dir\<run_id>` 폴더를 정확히 확인해야 합니다. A = `gate.frame`, B = `parking.frame`. 프레임 공유는 동일 호스트/로컬 공유 볼륨에서만 지원합니다.

## 적용 (로컬에서 작업 중인 파일을 통째로 덮어쓰지 않음)

ZIP을 **`D:\finalProjectB\back\apcms_ai` 폴더에 바로 압축 해제**하여 그 폴더 아래에 `apply_shared_fire_input.py`, `new_files` 폴더가 있도록 합니다.

```powershell
cd D:\finalProjectB\back\apcms_ai
.\.venv\Scripts\Activate.ps1

# 다른 곳에서 최신화된 화재 코드와 충돌하지 않는지 먼저 검사
python .\apply_shared_fire_input.py --check

# 패치 도구 자체 단위 테스트
python -m unittest test_patch_shared_fire_input -v

# 안전한 부분 패치/백업/새 파일 2개 추가
python .\apply_shared_fire_input.py --apply

# 수신기 단위 테스트. 추가로 기존 테스트 실행 권장
python -m unittest ai_vision.tests.safety.test_shared_frame_source ai_vision.tests.safety.test_live_fire_smoke ai_vision.tests.safety.test_fire_alert_live -v
```

- `--check`/`--apply`는 충돌 시 파일을 수정하지 않고 중단합니다.
- 현재 로컬 파일에 이미 다른 작업이 섞여 있으면 전체 파일을 덮어쓰지 말고 오류 내용을 알려주세요.
- 원본 백업은 `ai_vision/results/safety/patch_backups/shared_frame_*`에 저장합니다.
- `apply_shared_fire_input.py`와 `test_patch_shared_fire_input.py`는 적용 보조 도구이며 Git 커밋 대상으로 자동 포함하지 않습니다.

## DRY-RUN 시연: 카메라 장치는 주차 프로세스만 엽니다

주차 런타임 실행을 먼저 완료한 뒤 현재 run_id 폴더 및 gate_id, parking_id를 확인합니다. 아래 경로와 ID는 **예시이므로 본인 설정의 실제 값으로 바꾸세요.**

```powershell
cd D:\finalProjectB\back\apcms_ai
.\.venv\Scripts\Activate.ps1
$env:SAFETY_CAMERA_AUTOSTART = '0'  # 화재 쪽 독립 카메라 자동 실행 차단
$run = 'D:\finalProjectB\back\apcms_ai\shared_frames\여기에_현재_run_id'

# 터미널 1: A 입출차 원본 프레임 구독
python -m ai_vision.safety.fire_alert_live `
    --output '.\ai_vision\results\safety\shared_gate_demo' `
    -- `
    --shared-run-dir $run `
    --shared-role gate `
    --shared-camera-id A_GATE `
    --fire-conf 0.30 --smoke-conf 0.30 `
    --save-evidence --max-seconds 0
```

```powershell
# 터미널 2: B 주차면 원본 프레임 구독 (실제 parking_id를 사용)
cd D:\finalProjectB\back\apcms_ai
.\.venv\Scripts\Activate.ps1
$env:SAFETY_CAMERA_AUTOSTART = '0'
$run = 'D:\finalProjectB\back\apcms_ai\shared_frames\여기에_현재_run_id'
python -m ai_vision.safety.fire_alert_live `
    --output '.\ai_vision\results\safety\shared_parking_demo' `
    -- `
    --shared-run-dir $run `
    --shared-role parking `
    --shared-camera-id B_PARKING `
    --fire-conf 0.30 --smoke-conf 0.30 `
    --save-evidence --max-seconds 0
```

> DRY-RUN은 실제 AWS 전송을 하지 않습니다. 완료 뒤 `summary.json`, `incident_history.json`, `events.json`, `fire_alert_live_preview.json`을 확인합니다. 감지기에는 실제 영상을 입력해야 AI가 FIRE/SMOKE를 판정합니다. 실제 화재 여부는 사람이 확인해야 합니다.

입력이 생성되지 않거나 주차 쪽에서 종료하면 최근 유효 프레임은 절대로 재추론하지 않습니다. 기본 12초 뒤 공유 입력 불가 상태로 종료하고 `SESSION_ENDED`를 기록합니다. 알림 해제(`CLEARED`)로 오인하지 않습니다. 새 `run_id`가 나오면 새로운 프로세스/출력 폴더를 사용하세요. 단순 카메라 단절 시 별도 재연결을 시도하지 않습니다.

## AWS 시험 전송

기존 `fire_alert_live.py --send --allow-test-records --url ...` 옵션이 작동하는 구조입니다. 시연 전 로컬 DRY-RUN의 양쪽 카메라 감지, 사건 분리 및 증거 기록을 확인해야 합니다. 기존 HTTP 시험 주소는 암호화되지 않으며 공유 인증키 노출 위험이 있어 실제 차량 영상/운영 키로는 이용하지 마세요. 운영 전송은 HTTPS, 인증키, `--production-camera` 및 `--allow-production-records`가 필요합니다.

## 검사 범위와 한계

자체 검증: 공유 파일 수신기 모의 테스트 11개 및 패치 적용 모의 테스트 3개 통과. 실제 웹캠/모델/주차 측 원본 파일/서버/DB를 이 환경에서 직접 실행한 것은 아닙니다. **실제 A/B 카메라 동시 처리, 모델 속도/자원 영향, 현재 run_id 전달, 공유 볼륨, 장시간 감시는 로컬 통합 검증이 남았습니다.**

## Git 반영 (`2`를 입력할 때만 준비)

소스 파일은 `ai_vision/safety/live_fire_smoke.py`, `ai_vision/safety/shared_frame_source.py`, `ai_vision/tests/safety/test_shared_frame_source.py`만 분리해서 스테이징할 예정입니다. 다른 주차 소스나 테스트 동영상은 포함하지 않습니다.

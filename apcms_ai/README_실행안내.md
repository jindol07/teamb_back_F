# AI Vision → 팀 AWS Spring Boot 자동 전송: 프로젝트 시험용 HTTP 예외

**변경 범위:** `ai_vision/safety/fire_alert_sender.py`의 **원격 HTTP 주소 검증**만 한 줄 확장하고 헬퍼 함수를 삽입합니다. 기존 감지·상태 전이·중복방지·Bearer 인증·ACK 검증·Spring Boot·Oracle은 그대로 유지합니다. GitHub에 있는 최신 코드를 덮어쓰지 않고 사용자의 **현재 로컬 파일에 최소 수정**합니다.

## 0. 사전 조건

- 이전 모의 수신기(8765)와 FastAPI(8001) 종료 (`Ctrl+C`).
- `main.py`와 자동 감시 라우터는 **이전 8765 모의 수신 테스트에 성공한 그대로** 유지합니다.
- AWS Spring Boot에는 이미 `FIRE_ALERT_ALLOW_TEST=true`, `FIRE_ALERT_API_KEY` 설정되어 있다고 보고 진행합니다. 새로 설정할 필요 없습니다.
- 테스트 전용 URL: `http://52.79.133.132:3000/admin-api/api/parking/ai/fire-alerts` (2026-10-27 이전에 사용한 팀 배포 테스트 주소). **AWS IP나 라우팅이 바뀌었다면 확인이 필요합니다.**
- 외부 HTTP는 암호화되지 않으므로 토큰이 네트워크에서 노출될 수 있습니다. 개인/실서비스에 재사용하지 말고 짧은 테스트 기간만 사용하세요. 가능하면 테스트 후 키 교체.

## 1. ZIP 파일 배치

ZIP 파일의 아래 세 파일을 모두 다음 폴더에 풀어놓습니다.

`D:\finalProjectB\back\apcms_ai\`

- `apply_aws_test_http.py` : 기존 소스 최소 패치/원본 백업
- `test_aws_test_http_policy.py` : 외부 네트워크를 호출하지 않는 단위 테스트
- `01_run_aws_test_http.ps1` : 설정, 키 입력, FastAPI 실행, 종료 후 환경변수 정리

## 2. 적용 및 확인

**8001 서버가 종료된 상태에서** PowerShell에서 실행:

```powershell
cd D:\finalProjectB\back\apcms_ai
.\.venv\Scripts\Activate.ps1
python .\apply_aws_test_http.py --check
python .\apply_aws_test_http.py
python -m unittest test_aws_test_http_policy -v
```

패치는 `fire_alert_sender.py`를 수정하기 전에 원본을 `ai_vision/results/safety/patch_backups/fire_alert_sender_날짜시간.py.bak`로 백업합니다. 이미 적용되어 있다면 파일을 변경하지 않습니다. 예상한 조건식이 현재 로컬 파일과 다르면 **중단**하므로 억지로 덮어쓰지 마세요.

## 3. AWS 실제 저장 시연

FastAPI(8001)를 다른 창에서 실행 중이지 않도록 하고, 다음 실행:

```powershell
cd D:\finalProjectB\back\apcms_ai
.\01_run_aws_test_http.ps1
```

화면에 `공유키` 입력 메시지가 나오면 **이전에 AWS Spring Boot 환경변수 `FIRE_ALERT_API_KEY`로 설정한 값**을 입력합니다. 화면에는 표시되지 않습니다. `FIRE_ALERT_TOKEN`이라는 별도 키를 만들어야 하는 것이 아니고 **동일한 값**을 Python 측에서 사용하는 이름입니다.

이후 `GET http://127.0.0.1:8001/safety/camera/status`에서 `running: true`, `delivery: "TEST_HTTP"`를 확인합니다. 웹캠으로 *녹화된* FIRE/SMOKE 영상을 보여주면 `SUSPECTED` 이후 `[자동 전송] 신규 1건 ...` 로그를 기대합니다. 이전에는 로컬 모의 수신기가 이 로그를 받았지만, 이번에는 팀 AWS Spring Boot가 요청을 처리합니다.

이후 **기존 Postman 관리자 JWT**로 다음을 조회하여 새 시험 기록을 확인합니다.

- `GET http://52.79.133.132:3000/admin-api/api/admin/safety-incidents?limit=30`
- `GET http://52.79.133.132:3000/admin-api/api/admin/safety-notifications?limit=30`

스프링 부트에서 HTTP 2xx **정상 JSON ACK**가 오면 Python이 성공 체크포인트를 기록합니다. 네트워크 실패 또는 401/403/404/502인 경우 성공이라고 표시하지 않습니다. 토큰 값 자체나 전체 요청 본문을 채팅에 붙이지 마세요.

## 4. 원상 복구

- `Ctrl+C`로 서버를 종료하세요. 실행 스크립트는 토큰/테스트용 환경변수를 지웁니다. 다른 PowerShell 창에는 영향을 주지 않습니다.
- 더 이상 HTTP 예외가 필요하지 않다면 백업한 `fire_alert_sender_날짜시간.py.bak`를 원래 `fire_alert_sender.py`에 복사하면 됩니다. 다른 작업이 진행됐다면 원본 덮어쓰기 전 diff 확인.
- **기본적으로 `SAFETY_TEST_AWS_HTTP`를 설정하지 않는 한 외부 HTTP는 계속 거부됩니다.** 코드를 그대로 두어도 기본 차단입니다.

## 5. 운영과 보안

- 운영 전송은 HTTPS를 반드시 사용하며 `SAFETY_CAMERA_ALLOW_PRODUCTION=1` 별도 승인 필요. 이번 예외는 시험 데이터 전용입니다.
- 실제 판매 서비스가 아니어도 HTTP에는 여전히 키 노출 위험이 있습니다. 짧은 시연 이후 해당 키를 교체하는 편이 안전합니다.
- 이 작업은 AWS에 접근해 재배포하는 작업이 아닙니다. **로컬 송신기만 변경**합니다.

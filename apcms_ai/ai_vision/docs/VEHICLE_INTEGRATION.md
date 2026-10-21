# 입출차 연동과 중복 억제

[시작 안내](../readme.md) · [영상 분석](VIDEO_ANALYSIS.md) · [결과 검토](RESULTS_REVIEW.md) · [입출차 연동](VEHICLE_INTEGRATION.md)

> 아래 명령은 모두 `D:\finalProjectB\back\apcms_ai`에서 실행합니다.
> 기존 결과를 보존하려면 예시의 출력 이름을 새 이름으로 바꿔 사용하세요.

UUID를 DB에 저장하지 않는 설계를 유지합니다. 기본 비활성 HTTP 전송 경로와 별도 카메라 세션 실행 루프를 구현했습니다. 아래에는 과거 단계별 기록도 포함됩니다. 최신 확인 범위는 로컬 Boot·DB 입출차, AWS 사진 OCR, USB 웹캠의 사진 재촬영 연결이며 실제 이동 차량의 자동 입출차는 아직 검증 전입니다. 기존 sender에는 자동 연결하지 않았습니다.

## 목차

- [실시간 카메라 세션 실행](#live-session)
- [현재 전송 경로와 비활성 기본값](#http)
- [Boot 규격과 로컬 초안](#contract)
- [AI 메모리 중복 억제](#guard)
- [응답 분류와 모의 검증](#response)
- [후보부터 모의 응답 기록까지](#flow)

<a id="http"></a>

## 현재 전송 경로와 비활성 기본값

### 이번 기능 단위

실시간 형태의 통과 자료 → 요청 후보 생성 → 비활성/활성 판단 → 중복 억제 →
단발성 HTTP 요청 → 응답 분류 → 같은 Guard에 결과 기록을 연결했습니다.

**이번 검증에서는 실제 HTTP 요청을 하지 않았습니다.** 활성 경로는 모의 HTTP
세션으로 검사했으며 기존 카메라 실행 루프와 기존 parking_event_sender에는
자동 연결하지 않았습니다. 기존 점유 이벤트 전송 동작도 바꾸지 않았습니다.

### 기본값과 명시적 활성화

`VehicleHTTPClient()`와 `VehicleDeliveryFlow()`는 기본 비활성입니다. 비활성 흐름은
후보를 예약하지 않으며 HTTP 세션 생성도 하지 않습니다. `.env`나 기존 sender의
송신 환경변수를 자동으로 읽지 않으므로 다른 기능의 설정 때문에 켜지지 않습니다.

실제 연결 코드를 작성할 때에는 관리자 context URL과 API 키, `enabled=True`를
프로그램에서 명시적으로 넘겨야 합니다. URL은 관리자 context까지만 전달하며
클라이언트가 `/api/parking/ai/vehicle-events`를 붙입니다. API 키는
`X-AI-API-Key` 헤더로만 사용하고 코드·보고서에 실제 키를 기록하지 않습니다.

한 번 생성한 VehicleDeliveryFlow를 실행 루프에서 유지해야 합니다. 매 프레임 새로
만들면 메모리 중복 억제가 사라집니다. 실제 활성화는 팀 테스트 서버와 카메라 방향·
시각 기준을 확인한 뒤 별도 단계로 진행하세요. 이 문서의 검사 명령에는 실제 전송을
켜는 옵션이 없습니다.

### 실시간 후보 변환

`vehicle_live_candidate.create_live_candidate`는 `LIVE_TRACKED_PASSAGE` 자료만
받습니다. 저장 영상의 `LOCAL_TRACKED_PASSAGE`는 거부합니다. 이 표시는 호출자가
제공하는 출처 구분이며 실시간 촬영임을 암호학적으로 보증하지 않습니다.
별도 `run_live_gate` 실행 루프가 이 자료를 생성해 기본 비활성 처리 흐름에 연결합니다. 실제 하드웨어 검증은 아직 수행하지 않았습니다.

번호판 확정은 OCR 표본으로 재계산하고, 카메라 ID·DOWN의 ENTRY/EXIT 매핑·
통과 순간에 확보한 타임존 포함 detected_at을 요구합니다. 현재 시각을 임의로
대입하지 않습니다. UP은 명시한 DOWN 방향의 반대입니다.

미확정·외국·충돌 번호판과 탐지 신뢰도 누락은 BLOCKED입니다. confidence는
일치 번호판 표본의 탐지 신뢰도 최솟값이며 OCR 정확도가 아닙니다.
UUID는 후보 생성 시 만들 수 있지만 같은 차량 반복 입력에서는 Guard가 최초 UUID를
유지합니다. UUID DB 저장은 추가하지 않았습니다.

### HTTP 동작

- 연결/읽기 제한 시간 기본 3초/5초, 각각 0초 초과 60초 이하
- POST 한 번만 시도, 리다이렉트 미추적, 어댑터 자동 재시도 0회
- 환경의 프록시·netrc 인증 자동 적용 비활성
- 응답 스트리밍으로 최대 64KB 읽고 세션·응답 닫기
- 200 응답도 UUID·번호판·유형과 outcome 확인 후 분류
- PENDING·타임아웃·서버 오류·손상 응답 이후 재요청하지 않음

읽기 제한은 전체 요청의 절대 마감 시간이 아니라 개별 소켓 읽기 대기 제한입니다.
일반적인 요청 시간 제한과 응답 크기 제한을 적용한 것이며 전체 시간의 상한을
보장하는 별도 작업 스케줄러는 이번 범위에 없습니다.

`request_attempted=true`는 POST 메서드를 호출했다는 뜻이며 서버 도착·DB 반영을
보장하지 않습니다. 세션 준비 단계 오류는 false이고, 호출 경계의 예상치 못한
예외로 시도 여부를 확인할 수 없으면 null입니다. 모두 자동 재전송하지 않습니다.

예외 원문·URL·키를 결과에 복사하지 않습니다. 메모리 상태는 프로세스 재시작이나
여러 프로세스 사이의 중복을 막지 않습니다. 자세한 범위는 [중복 억제](VEHICLE_INTEGRATION.md#guard)에 있습니다.

### 실제 네트워크 없는 실행 검사

`D:\finalProjectB\back\apcms_ai`에서:

```powershell
# 기본 비활성: 세 번 입력해도 모의/실제 POST 모두 0회
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_vehicle_delivery_check `
  --output ai_vision/results/previews/delivery_disabled_01.json

# HTTP 클라이언트는 활성화하되 가짜 세션만 사용: 타임아웃 후 추가 요청 없음
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_vehicle_delivery_check `
  --mode mock-http `
  --scenario timeout `
  --passes 3 `
  --output ai_vision/results/previews/delivery_timeout_01.json
```

`processed`, `pending`, `unauthorized`, `server_error`, `invalid_json` 등 기존
14개 모의 시나리오를 지원합니다. 실제 전송 모드는 없습니다. mock-http 모드의
내부 단계는 테스트용 클라이언트 설정상 http_enabled=true이지만, 최상위 보고서는
`real_http_used=false`, `http_enabled=false`, `uses_synthetic_event=true`입니다.
`mock_post_calls`는 가짜 세션 호출 횟수입니다. 실제 HTTP나 실제 한국 번호판 영상의
성능 증거로 사용하지 마세요. 출력 파일은 원본 결과 밖의 새 JSON만 허용합니다.

### 검증과 다음 연결 지점

후보 변환과 모의 HTTP 세션, 동시 입력, 인증 헤더·URL·요청 옵션, 응답 크기 제한,
타임아웃·보류 유지, 비활성 상태의 세션 미생성을 자동 테스트합니다.
실제 Boot/DB 테스트는 아직 수행하지 않았습니다. 카메라 세션의 시작·종료와 수집 시각은 아래 실시간 세션 절에서 설명합니다.


<a id="contract"></a>

## Boot 규격과 로컬 초안

### 현재 Boot 규격

2026-10-20 로컬 `apcms_a`의 `AiVehicleEventController`, `AiVehicleEventRequest`,
`AiVehicleEventService` 코드를 확인했습니다. 서버를 실제 호출한 검증은 아닙니다.

- 컨트롤러: `POST /api/parking/ai/vehicle-events`
- 현재 관리자 context path 포함: `/alpharking/admin/api/parking/ai/vehicle-events`
- 인증 헤더: `X-AI-API-Key`
- 서버 설정 키: `AI_OCCUPANCY_API_KEY`
- `event_type`: `VEHICLE_PASSAGE`
- 필수 값: UUID `event_id`, 타임존 포함 `detected_at`, `camera_id`, ENTRY/EXIT `direction`,
  한국 번호판 `plate_number`, 숫자 0~1 `confidence`
- 통과 요청의 `space_code`는 없어야 하거나 null이어야 함
- 감지 시각이 서버 현재 시각보다 60초 넘게 미래이면 거부

Python 검증은 UUID를 표준 문자열로 정리하고 번호판 공백을 제거합니다.
AI 측에서는 매칭용 `method`도 null 또는 생략만 허용합니다. 감지 시각은 초 단위와
최대 6자리 소수 초, Z 또는 분 단위 offset을 지원합니다. 날짜·타임존을 생략하면 거부합니다.
이는 Boot에서 받을 수 있는 형식 중 이번 연동에서 사용하는 범위입니다.

### 로컬 초안 확인

`D:\finalProjectB\back\apcms_ai`에서 실행합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.preview_vehicle_events `
  --run-id traffic_pipeline_fresh `
  --output ai_vision/results/previews/my_preview_01.json
```

이 명령에는 송신 옵션이 없습니다. 기존 sender, .env, API 키를 불러오지 않고
검증된 저장 결과만 읽습니다. 새 JSON은 원본 결과 폴더 밖에 저장하며 덮어쓰지 않습니다.
`http_enabled=false`, `sendable=false`를 항상 기록합니다.

현재 외국 번호판 영상은 `NO_CONFIRMED_KOREAN_PLATE`로 보류됩니다.
실제 촬영 정보가 없는 경우에도 다음 항목을 임의로 채우지 않습니다.

| reason | 보류 원인 |
|---|---|
| NO_CONFIRMED_KOREAN_PLATE | 한국 번호판 반복 인식이 확정되지 않음 |
| MISSING_CAMERA_ID | 촬영 카메라 식별자 없음 |
| MISSING_DIRECTION_MAPPING | DOWN을 ENTRY/EXIT 중 무엇으로 볼지 미설정 |
| MISSING_RECORDING_START | 실제 촬영 시작 날짜·타임존 없음 |
| MISSING_DETECTION_CONFIDENCE | 일치 번호 표본의 탐지 신뢰도 없음·유효하지 않음 |

각 차량의 `payload`는 보류 시 null입니다. 연결 진단 FAILED/INCOMPLETE 결과나
OCR 없이 추적만 한 실행은 초안 생성 자체를 중단합니다. 일부 차량만 OCR한 경우
그 범위를 `audit_status=WARNING`으로 유지하며 OCR 처리된 차량만 검토합니다.

### 실제 촬영 정보가 확보된 뒤

선택 인수는 `--camera-id`, `--down-direction ENTRY|EXIT`,
`--recording-started-at "촬영시작시각(타임존 포함)"`입니다.
DOWN 방향을 지정하면 UP은 반대 방향으로 해석합니다. 현재 기능은 양방향 통과선
카메라 한 대 기준이며, 설치 방향을 확인하기 전에 이 값을 추측해서 지정하지 마세요.
`detected_at`은 촬영 시작 시각 + 원본 영상 통과 초로 계산하고 현재 날짜로 바꾸지 않습니다.

`confidence`는 일치한 번호판 표본들의 **번호판 상자 탐지 신뢰도 최솟값**입니다.
OCR 문자 정확도나 전체 차량 인식 확률이 아닙니다. 이 선택 기준이 적절한지 실제
한국 번호판 영상으로 확인한 뒤 운영 정책을 정해야 합니다.

필수 조건을 만족하면 `CANDIDATE_ONLY` 초안이 만들어지지만 실제 전송 허가를
뜻하지 않습니다. 동일한 입력 문맥에서는 UUID가 같으며, 문맥·판정이 바뀌면 달라질
수 있습니다. 이는 프리뷰 식별용이며 실시간 이벤트 중복 방지 수단이 아닙니다.

### 실제 전송 연결 전에 남은 사항

- Boot는 UUID 형식만 검사하고 UUID를 영구 저장하지 않으므로 재전송 중복 방지를 보장하지 않음
- 기존 sender의 재전송 정책을 그대로 적용하기 전에 이벤트별 멱등성·타임아웃 처리 협의 필요
- 과거 영상의 초안을 운영 입출차 API로 재생하면 실제 이용 기록이 바뀔 수 있음
- Python 모의 테스트는 요청 변환 검증이며 실제 Boot·Oracle 통합 테스트가 아님
- 기존 `create_vehicle_event`는 현재 시각을 자동 생성하므로 오프라인 영상 초안에 재사용하지 않음

이번 변경은 기존 sender와 Boot 코드를 바꾸거나 서버를 실행하지 않습니다.
모의 응답의 PROCESSED·UNCHANGED·PENDING·통신 실패 분류는 [응답 분류](VEHICLE_INTEGRATION.md#response)의
도구로 확인할 수 있습니다. 실제 테스트 서버와의 통합 검증은 아직 수행하지 않았습니다.


<a id="guard"></a>

## AI 메모리 중복 억제

UUID를 DB에 저장하지 않는 현재 설계를 유지합니다. `VehicleEventGuard`는 한 AI
프로세스의 메모리에서만 후보 생성과 응답 상태를 관리하며 HTTP 전송·DB 쓰기·
파일 상태 저장·자동 재전송을 하지 않습니다. 기존 sender와 실시간 카메라에는
아직 연결하지 않았습니다. 원본 이벤트 UUID는 응답 대조용으로 메모리에 유지합니다.

후보부터 모의 응답 기록까지 연결한 실행 도구는 [모의 처리 흐름](VEHICLE_INTEGRATION.md#flow)를 참고하세요.

### 판정 규칙

| decision | 의미 |
|---|---|
| NEW_CANDIDATE | 최초 후보. 로컬 검토용 payload 반환 |
| SUPPRESSED_SAME_TRACK | 같은 카메라·실행·차량 ID와 동일한 번호·방향·시각이 반복됨 |
| HELD_TRACK_CONFLICT | 같은 차량 ID의 번호·방향·시각이 달라짐 |
| SUPPRESSED_RECENT_PLATE | 다른 ID여도 같은 카메라·번호판·방향이 5초 미만으로 반복됨 |
| HELD_OUT_OF_ORDER | 같은 카메라·번호판·방향의 최신 후보보다 과거 입력 |
| HELD_EVENT_ID_REUSE | 이미 다른 후보에 사용된 UUID를 새 통과에 재사용 |
| HELD_CAPACITY | 보관 건수 한도 도달. 기존 기록은 제거하지 않음 |

같은 차량 ID의 반복 입력에서 UUID가 재생성되거나 탐지 신뢰도가 바뀌어도 최초
이벤트를 유지합니다. 동일 순간의 서로 다른 타임존 표현도 같은 시각으로 취급합니다.
보류·억제 판정에서는 payload를 반환하지 않습니다. 모든 출력은 `sendable=false`,
`http_enabled=false`, `automatic_retry_allowed=false`입니다.

번호판 반복 억제 시간의 기본 5초는 **검증용 초기 정책**입니다. 정확히 5초부터는
새 ID의 후보를 허용합니다. 실제 설치 환경과 한국 번호판 주행 영상으로 조정해야
하며, 물리적으로 같은 차량인지 확정하는 기능이 아닙니다. 반대 방향·다른 카메라는
독립적으로 취급합니다. 억제된 기존 ID가 시간 경과만으로 다시 생성되지는 않습니다.

### 응답 상태와 수명

최초 후보는 AWAITING_RESULT입니다. `vehicle_response.assess_response`의 결과를
`record_result`에 전달하면 APPLIED·UNCHANGED·HELD·REJECTED·AUTH_REQUIRED·
DELIVERY_UNKNOWN으로 기록합니다. UUID·이벤트 유형과 응답 검증 플래그를 확인하고,
같은 결과의 반복 기록만 허용합니다. 다른 상태로 덮어쓰는 자동 복구는 없습니다.
타임아웃 기록 후 같은 차량이 반복돼도 새 후보를 만들거나 자동 재전송하지 않습니다.

기본 보관 한도는 후보·보류 차량 ID를 합쳐 10000개입니다. 한도에 도달하면 신규
입력을 보류하며, 오래된 기록을 몰래 제거해 중복이 재허용되는 것을 피합니다.
이 한도에서 세션을 어떻게 종료·교체할지는 실제 실행 루프 연결 단계에서 정해야 합니다.

RLock으로 한 프로세스의 동시 스레드 입력을 보호합니다. 다음은 보장하지 않습니다.

- 프로세스 재시작 또는 새로운 Guard 객체 생성 후의 중복 방지
- 여러 프로세스·여러 PC·여러 카메라 사이의 전역 중복 방지
- 추적 ID 재사용·번호판 오인식·실제 차량의 재진입 여부 판단
- Boot/Oracle의 멱등 처리 또는 응답 유실 후 서버 처리 여부 확인

실시간 연결 시 한 실행 루프에서 같은 Guard 객체를 유지해야 합니다. session_id는
추적기 실행을 식별하는 안정적인 값이어야 하며, 매 프레임 새로 만들면 안 됩니다.
추적기가 재시작해 ID를 재사용한다면 별도 세션으로 구분해야 합니다.

### 송신 없는 검증

`D:\finalProjectB\back\apcms_ai`에서:

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.simulate_event_guard `
  --demo `
  --output ai_vision/results/previews/guard_demo_01.json
```

합성 번호판과 가짜 타임아웃으로 7단계를 검사합니다. 새 후보는 최초 통과와
5초 경계의 새 ID, 총 2건입니다. 실제 촬영·실제 서버·DB 처리 증거가 아닙니다.

기존 초안을 같은 Guard에 반복 입력하는 검증:

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.simulate_event_guard `
  --preview ai_vision/results/previews/vehicle_preview_20261020_01.json `
  --passes 3 `
  --output ai_vision/results/previews/guard_preview_01.json
```

외국 번호판 영상의 BLOCKED 차량은 후보로 대체하지 않습니다. 초안 전체의 형식과
건수를 검사한 뒤 상태에 반영합니다. 반복 횟수는 1~10, 초안은 1000건 이하입니다.
기존 출력 파일과 원본 결과 폴더는 덮어쓰지 않습니다. CLI를 다시 실행하면 Guard는
새로 생성되므로 CLI 실행 사이의 중복을 억제하는 도구는 아닙니다.


<a id="response"></a>

## 응답 분류와 모의 검증

Boot `AiVehicleEventResponse`의 camelCase 응답을 요청 UUID·이벤트 유형·번호판과
대조합니다. 실제 HTTP 호출·sender 연결·대기 큐 변경·자동 재전송은 없습니다.
이 절은 요청 초안과 응답 분류 규칙을 설명합니다.

### 결과 구분

| 응답 | state | 처리 의미 |
|---|---|---|
| 200 + PROCESSED | APPLIED | 백엔드가 처리 완료라고 응답 |
| 200 + UNCHANGED | UNCHANGED | 새 변경 없이 현재 상태 유지 |
| 200 + PENDING | HELD | 업무 선행 조건 확인 필요 |
| 401/403 | AUTH_REQUIRED | 인증·접근 설정 확인 필요 |
| 그 외 일반 4xx(400/409 등) | REJECTED | 요청 거부로 분류 |
| 408/429, 5xx, 타임아웃·연결 오류 | DELIVERY_UNKNOWN | 처리 여부를 단정할 수 없음 |
| 손상 JSON·UUID/번호판 불일치·알 수 없는 outcome | DELIVERY_UNKNOWN | 정상 완료 응답으로 인정하지 않음 |

300대 응답은 리다이렉트 미추적 상태로 REJECTED, 200 이외의 예상하지 않은 성공
응답은 DELIVERY_UNKNOWN입니다. 현재 HTTP 클라이언트도 리다이렉트와
라이브러리 수준 자동 재시도를 차단합니다.

`receipt_verified=true`는 UUID·유형·번호판과 지원 outcome을 확인했다는 뜻입니다.
APPLIED의 DB 변경을 독립적으로 조회해 입증했다는 뜻이 아닙니다. PENDING도
응답 식별은 확인할 수 있지만 처리 완료 상태는 아닙니다.

모든 상태에서 `automatic_retry_allowed=false`입니다. 현재 Boot는 UUID를
영구 보관하지 않아 타임아웃 직후 같은 이벤트를 재전송하면 업무 중복 위험이
남습니다. 인증 오류·거부·보류도 원인 해결 없이 자동 반복하지 않습니다.
응답의 detail 원문은 보고서에 복사하지 않습니다.

### 모의 검증 실행

`D:\finalProjectB\back\apcms_ai`에서 실행합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.simulate_vehicle_exchange `
  --demo `
  --output ai_vision/results/previews/mock_exchange_01.json
```

명시적인 `--demo`는 합성 한국 번호판 1건과 가짜 Boot 응답 14개를 사용합니다.
보고서는 `uses_synthetic_event=true`, `http_enabled=false`, `sendable=false`입니다.
실제 인식 정확도·실제 서버 응답·DB 처리 성공의 증거가 아닙니다.
모든 사례에서 원본 UUID를 유지하며 타임아웃도 자동 재전송하지 않습니다.

기존 로컬 초안으로 확인하려면:

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.simulate_vehicle_exchange `
  --preview ai_vision/results/previews/vehicle_preview_20261020_01.json `
  --output ai_vision/results/previews/mock_from_preview_01.json
```

BLOCKED 차량은 건너뛰며 합성 번호판으로 대체하지 않습니다. 외국 번호판 영상은
후보가 없으므로 사례 0개·보류 1건이 정상입니다. 실험할 조건만 선택할 때는
`--scenario processed --scenario timeout`처럼 지정합니다.

중복 UUID·후보/전체 건수 불일치·잘못된 초안 형식을 거부합니다. 생성 사례는
최대 1000개이고 기존 파일은 덮어쓰지 않습니다. 검증에 API 키나 .env를 사용하지 않습니다.


<a id="flow"></a>

## 후보부터 모의 응답 기록까지

`MockVehicleEventFlow`가 기존 모듈을 다음 순서로 연결합니다.

1. 전체 초안의 형식·건수 검사
2. VehicleEventGuard로 후보 예약 및 중복 억제
3. NEW_CANDIDATE일 때만 기존 가짜 Boot 응답 함수 호출
4. 응답 분류 결과를 같은 Guard에 기록
5. 반복 입력은 기존 상태만 확인하고 모의 응답 함수를 다시 호출하지 않음

실제 카메라·HTTP·DB·기존 sender는 연결하지 않았습니다. 모든 결과는
`http_enabled=false`, `sendable=false`, `automatic_retry_allowed=false`입니다.
이 기능은 실제 전송 전 AI 내부 처리 순서를 검증하는 단위입니다.

### 실행

`D:\finalProjectB\back\apcms_ai`에서:

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_guarded_vehicle_flow `
  --demo `
  --scenario timeout `
  --passes 3 `
  --output ai_vision/results/previews/flow_timeout_01.json
```

합성 후보 한 건을 세 번 입력해도 모의 응답 호출은 한 번입니다.

| pass | decision | receipt_state | mock_invoked |
|---|---|---|---|
| 1 | NEW_CANDIDATE | DELIVERY_UNKNOWN | true |
| 2 | SUPPRESSED_SAME_TRACK | DELIVERY_UNKNOWN | false |
| 3 | SUPPRESSED_SAME_TRACK | DELIVERY_UNKNOWN | false |

`--scenario pending`이면 HELD가 유지되고 `processed`면 APPLIED가 유지됩니다.
PENDING 뒤 같은 후보에 processed를 지정해도 Guard는 다시 호출을 허용하지 않습니다.
지원 시나리오는 [응답 분류](VEHICLE_INTEGRATION.md#response)의 모의 응답 14종과 같습니다.
APPLIED는 가짜 백엔드의 응답 분류일 뿐 실제 입차 완료가 아닙니다.

실제 저장 초안으로 확인하려면:

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_guarded_vehicle_flow `
  --preview ai_vision/results/previews/vehicle_preview_20261020_01.json `
  --scenario processed `
  --passes 3 `
  --output ai_vision/results/previews/flow_preview_01.json
```

외국 번호판 영상의 BLOCKED 차량은 그대로 건너뜁니다. 합성 번호판으로 대체하지
않으므로 모의 응답 호출도 0회입니다. 출력 파일은 원본 결과 밖의 새 JSON만 허용합니다.

### 오류와 동시 입력

- 잘못된 시나리오와 손상된 초안은 후보 예약 전에 거부합니다.
- 후보 예약 뒤 모의 응답 함수 오류나 잘못된 결과가 발생하면
  `LOCAL_RESPONSE_PROCESSING_FAILED`의 DELIVERY_UNKNOWN으로 기록합니다.
- 예외 원문은 보고서에 넣지 않습니다. 다른 상태로 자동 복구하거나 재전송하지 않습니다.
- 같은 프로세스의 여러 스레드가 같은 후보를 입력해도 최초 입력만 모의 응답을 호출합니다.
- 응답 기록 전 다른 입력이 도착하면 AWAITING_RESULT로 보일 수 있지만 새 호출은 하지 않습니다.

응답은 `receipt`, 최종 보관 상태는 `receipt_state`로 표시합니다. 중복 입력은
새 응답을 받지 않았으므로 receipt가 null입니다. `mock_call_count`는 실제 HTTP
전송 횟수가 아니라 가짜 응답 함수 호출 횟수입니다.

프로세스 재시작·여러 PC 사이의 보장은 없습니다. 같은 처리 흐름을 유지하려면
한 실행에서 같은 MockVehicleEventFlow 객체를 재사용해야 합니다. CLI를 재실행하면
새 메모리 상태로 시작합니다. 세부 중복 억제 범위와 임시 5초 정책은 [중복 억제](VEHICLE_INTEGRATION.md#guard)를 참고하세요.


<a id="live-session"></a>

## 실시간 카메라 세션 실행

### 2026-10-21 로컬 실제 연동 확인

- 사용자 DB 조회 화면으로 복구 후 이용 기록 70번의 차량번호 `99하0001`과
  ENTRY_AT·EXIT_AT 저장(2026-10-21 15:24:00)을 확인했습니다.
- 실제 `1080P Webcam` 0번 장치에서 640×480 한 프레임 읽기·해제에 성공했습니다.
  이후 실제 `run_live_gate`를 HTTP 비활성 상태로 5초 실행해 63프레임을 처리했습니다.
  STOPPED / TIME_LIMIT, 통과 자료 0건, 요청 0회, 세션 종료와 자원 정리 오류 0건입니다.
  모델 준비·차량 추적·프레임 수집·종료 경로를 확인한 것이며 실제 출입구의 ROI·방향과
  주행 번호판 정확도는 확인하지 않았습니다. 전 화면 ROI와 중앙 기준선을 점검용으로만
  사용했고 입출차 방향도 보정되지 않은 비활성 시험 설정입니다. 사진·영상은 저장하지
  않았으며, 결과는 로컬 `results/camera_checks/hardware_2fba992f35/session/summary.json`입니다.

- 가상환경·STS 프로젝트 재등록 및 관리자 실행 설정 키 복구 후, 실제 `.env` 설정을
  읽는 클라이언트로 `99하0001` ENTRY·EXIT를 재확인했습니다. 두 요청 모두
  HTTP 200 / PROCESSED, 이용 기록 번호 70을 응답받았습니다. 현재 DB 직접 조회는
  하지 않았으며, 이 재확인은 실제 카메라·OCR을 사용하지 않은 수동 요청입니다.

- 수동 지정 번호 `99하0001`: 실제 AI HTTP 클라이언트로 ENTRY·EXIT를 요청해 모두
  HTTP 200 / PROCESSED를 받았습니다. 이용 기록 번호는 68이며, 사용자가 DB 조회 화면으로
  해당 차량의 ENTRY_AT·EXIT_AT 저장을 확인했습니다.
- 실제 `test_images/car12.png`: 로컬 YOLO·PaddleOCR 실행으로 차량 1대와 최종 번호판
  `91소6408` / KOREAN_VALID를 확인했습니다. 1차 OCR은 `91소66408`, 기존 전처리 재시도는
  `91소6408`이었습니다. 번호판 탐지 점수는 0.9736이며 OCR 정답 확률이 아닙니다.
- 사용자가 해당 번호의 테스트를 승인한 뒤, 인식 결과의 번호판과 탐지 점수를 그대로
  사용해 ENTRY·EXIT를 요청했습니다. 모두 HTTP 200 / PROCESSED, 이용 기록 번호 69를
  응답받았습니다. 이후 사용자가 DB 조회 화면으로 69번의 차량번호 `91소6408`과
  ENTRY_AT·EXIT_AT 저장(2026-10-21 12:20:38)을 확인했습니다.
- 정지 사진에는 통과 방향·실제 통과 시각이 없으므로 방향과 시각은 수동 테스트 값입니다.
  반복 프레임 합의나 주행 통과를 검증한 것이 아니며, LIVE 출처로 위장하지 않았습니다.
  AWS 재검증이나 실제 카메라 실행 명령의 하드웨어 검증도 포함하지 않습니다.
- 원본 인식 및 전송 결과는 로컬 `results/manual_integration/`의
  `car12_recognition_20261021.json`, `car12_boot_delivery_20261021.json`에 보관했습니다.
  이 로컬 결과를 Git에 포함했다고 간주하지 않습니다.

`LiveGateClock` → `LiveGateProcessor` → `LiveGateSession` → 기본 비활성
`VehicleDeliveryFlow`를 `run_live_gate`에서 연결합니다. 기존 웹캠 코드와 sender를
수정하지 않은 별도 실행 경로입니다. 실제 카메라·주행·실제 모델 OCR 성능 검증은
아직 하지 않았으며, 이번 검증은 가짜 카메라와 주입한 추적/OCR 함수 기준입니다.

### USB 웹캠과 원격 Vision API 연결

2026-10-21 AWS 실접속 점검: SSH 별칭 `apcms-aws`로 접속했고 컨테이너
`apcms-vision-test`의 포트가 AWS의 `127.0.0.1:8000`에만 연결된 것을 확인했습니다.
공인 주소의 8000번 포트 연결은 시간 초과였지만 AWS 내부 `/health`, `/ready`는 정상
응답했습니다. 현장 PC는 SSH 로컬 포워딩으로 연결할 수 있으며 공인 포트를 열지 않았습니다.

임시 SSH 터널로 `car12.png`를 한 번 요청했으나 인식 중 연결이 끊겼습니다. 해당 시점
Docker 이벤트의 `oom`·`die`·`start`와 운영체제의 `Out of memory: Killed process ...
(python)` 기록을 확인했습니다. 종료 기록의 Python anon-rss는 6,875,076KiB(약 6.6GiB)였습니다.
재시작 뒤 inspect의 OOM=false만으로 이전 OOM을 배제할 수 없었습니다. 컨테이너는 다시
실행 중이지만 이 요청의 원격 인식 성공은 확인하지 못했습니다. 현재 최우선 배포 과제는
실제 OCR의 메모리 사용 원인과 상한을 확인하고 개선하는 것입니다. 비용이 발생하는
인스턴스 변경·서버 설정 변경·이미지 재배포는 수행하지 않았습니다.

연결만 확인할 때는 별도 터미널에서 다음 터널을 유지하고 Vision 주소를
`http://127.0.0.1:18000`으로 지정할 수 있습니다. 이 주소의 서버는 AWS에 있으며
터널 터미널을 종료하면 연결도 종료됩니다. OCR 메모리 문제 해결 전에는 부하·반복
인식 테스트를 하지 않습니다.

```powershell
ssh -N -L 127.0.0.1:18000:127.0.0.1:8000 apcms-aws
```

최종 시연 입력은 현장 PC에 연결한 USB 웹캠입니다. 이 구성에서는 현장 PC가
카메라 수집·YOLO 차량 추적·통과 방향·OCR 표본 합의·중복 억제·Boot 전송을 담당하고,
AWS의 기존 `POST /recognize` API가 차량 영역의 번호판 탐지·OCR을 담당합니다.
차량 추적도 현장 PC에서 실행하므로 현장에는 Python·OpenCV·Torch·YOLO와 차량 모델이
필요합니다. 원격 모드에서는 현장 PaddleOCR·번호판 모델을 준비하지 않습니다.

```mermaid
flowchart LR
  A[현장 USB 웹캠] --> B[현장 차량 추적·통과 판정]
  B -->|차량 영역 PNG| C[AWS Vision API]
  C -->|번호판·분류·탐지 점수| D[현장 표본 합의·중복 억제]
  D -->|명시적 전송 활성화| E[Boot 입출차 API]
```

기존 `run_live_gate`에 `--vision-api-url`을 추가합니다. 아래 주소는 예시이므로 실제
접근 가능한 Vision 서버 주소로 바꿉니다. 추적 설정과 DOWN 방향은 실제 카메라 구도에
맞춰야 합니다. 아래 명령은 번호판 인식을 원격으로 보내지만 Boot 전송은 비활성입니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_live_gate `
  --camera-index 0 --camera-id GATE_01 --down-direction ENTRY `
  --config "실제_출입구_설정.json" --vision-api-url "https://vision.example.com" `
  --seconds 20 --output-dir ai_vision/results/live_gate/remote_01
```

실제 입출차 반영이 필요할 때만 `--enable-http`를 추가합니다. Boot 서버 주소와 키는
앞서 설명한 `.env` 또는 운영체제 환경변수에서 읽습니다. Boot 키는 Vision 요청에
전달하지 않습니다. 원격 인식 옵션을 생략하면 기존 로컬 인식 방식이 유지됩니다.
합성 데모에는 원격 인식 옵션을 사용할 수 없습니다.

원격 서버는 입력 차량 한 대에 대해 정확히 한 차량 결과를 반환해야 합니다. 여러 차량이
탐지되면 한 번호를 임의 선택하지 않고 중단합니다. 차량 없음·REVIEW·외국 번호판은
확정 표본으로 채택하지 않습니다. 형식 통과 번호판과 유한한 탐지 점수를 검사하고,
현장 세션이 기록한 서로 다른 프레임의 표본으로 기존 합의 조건을 적용합니다.
서버 오류·시간 초과·손상 응답도 현재 세션을 실패로 종료하며 자동 재시도하지 않습니다.

차량 영역은 메모리에서 PNG로 인코딩하며 요청 파일은 저장하지 않습니다. 응답 상한은
1MB이며 연결 제한 3초·읽기 제한 120초입니다. 전송은 순차 처리이므로 원격 OCR·네트워크
대기 중 새 프레임 수집이 지연될 수 있습니다. 이번 구현이 주행 처리량을 보장하지 않으며,
실제 통신 지연과 차량 속도에 따른 누락 여부를 시연 구도에서 확인해야 합니다.
응답 대기 시간은 카메라 실행 제한과 별개이므로 세션이 지정 초보다 늦게 종료될 수 있습니다.
요약에는 `recognition_mode=REMOTE_API`만 기록하고 원격 주소·키는 저장하지 않습니다.

로컬 Windows Vision 서버와 실제 HTTP 통신으로 `car12.png`의 `91소6408` / KOREAN_VALID,
탐지 점수 0.9736 응답을 확인했습니다. 이는 원격 클라이언트와 서버 연결 검증이며
AWS·실제 주행·원격 카메라 자동 DB 반영 검증은 아닙니다. 로컬 결과는
`results/remote_camera_checks/local_http_e433b9344f.json`에 보관했습니다.

### 로컬·원격 모드 공통 Boot 전송 설정

실제 카메라 모드는 차량 추적·번호판 탐지·OCR 모델을 먼저 생성한 뒤 세션 시계와
카메라를 시작합니다. 출력 폴더를 먼저 확보하고, 모델 준비 → 카메라 생성 → 세션 시계
시작 순서로 진행하여 준비 시간을 프레임 시각에서 제외합니다.
준비 중에는 안내 문구를 표시하며 모델 준비가 실패하면 카메라를
열지 않습니다. 기본 20초 제한에는 모델 생성 시간이 포함되지 않습니다. 이는 모델
객체 준비이며 실제 추론 예열이나 첫 추론 지연 제거를 보장하지 않습니다. 합성 데모와
테스트에서 주입한 추적·OCR 함수에는 실제 모델을 불러오지 않습니다.

`run_live_gate`는 기본적으로 전송하지 않습니다. 실제 카메라 실행에 `--enable-http`를
추가한 경우에만 활성 클라이언트를 연결합니다. API 키는 Boot와 동일한
`AI_OCCUPANCY_API_KEY`를 운영체제 환경변수 또는 `apcms_ai/.env`에 지정하며
명령 인자나 결과 파일에 넣지 않습니다. `.env`는 `--enable-http`를 지정할 때만 읽고
운영체제 환경변수를 변경하지 않습니다. 관리자 서버 context URL은 `--boot-context-url`,
운영체제의 `VISION_BOOT_CONTEXT_URL`, `.env`의 같은 항목 순서로 선택합니다.
키는 운영체제 환경변수가 `.env`보다 우선하며, 빈 환경변수도 명시된 설정으로 취급합니다.
활성화 시 주소·키가 없으면
모델·카메라를 열기 전에 종료합니다. 환경변수만으로는 전송이 켜지지 않으며,
`--demo`와 실제 전송 옵션의 조합은 거부합니다.

```powershell
# 카메라가 연결된 PC에서 실행합니다. 호스트·설정 경로·카메라 ID·방향은 실제 값으로 바꿉니다.
# AI_OCCUPANCY_API_KEY는 .env 또는 운영체제 환경변수에 Boot와 같은 값으로 준비합니다.
$env:VISION_BOOT_CONTEXT_URL = "http://관리자서버호스트:81/alpharking/admin"
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_live_gate `
  --camera-id GATE_01 --camera-index 0 --down-direction ENTRY `
  --config "실제_추적설정_경로.json" --seconds 20 --enable-http `
  --output-dir ai_vision/results/live_gate/boot_01
```

이 명령은 확정된 실제 통과 후보가 생기면 DB 변경을 수반하는 요청을 보냅니다.
DOWN→ENTRY 설정은 실제 카메라 방향에 맞을 때만 사용합니다. 현재 입력은 로컬 장치
번호이므로 카메라가 연결된 PC에서 실행해야 하며 AWS가 회사 USB 카메라를 직접 열 수는
없습니다. 다른 호스트의 Boot는 해당 PC에서 접근 가능한 주소를 사용하고, 별도
컨테이너의 `localhost`를 다른 서버 주소로 사용하지 않습니다.

현재 소스 대조 결과, 요청은 관리자 모듈 `apcms_a`의
`POST /alpharking/admin/api/parking/ai/vehicle-events`로 보내며 인증 헤더는
`X-AI-API-Key`입니다. 사용자 모듈 `apcms_u`에는 이 수신 경로가 없습니다.
기본 설정 포트는 관리자 81입니다. 실제 배포에서 바꿨다면 배포 주소를 사용합니다.

Boot의 ENTRY는 활성 입차 기록이 없고 시각 조건을 통과하면 `PARKING_USAGE`에 추가하며,
EXIT는 열린 입차 기록의 `EXIT_AT`을 갱신합니다. 이미 입차 상태이면 `UNCHANGED`,
활성 기록 없는 출차·시각 역전 등은 `PENDING`이 될 수 있습니다. AI는 각각
`APPLIED`·`UNCHANGED`·`HELD`로 분류합니다. UUID는 DB에 저장하지 않으며, 처리 여부가
불명확한 타임아웃은 자동 재전송하지 않습니다. 중복 억제는 현재 실행 메모리 범위이므로
재시작 후 중복 방지를 보장하지 않습니다.

이번 확인은 소스 대조와 모의 HTTP 연결 테스트입니다. 실제 Boot 실행·DB 쓰기 검증은
아직 하지 않았습니다. 실연동 시 `summary.json`의 `http_enabled`, `request_attempts`,
각 결과의 `receipt_state`와 DB의 해당 차량 `ENTRY_AT`·`EXIT_AT`을 함께 확인해야 합니다.

### 카메라·모델·HTTP 없는 데모 실행

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_live_gate `
  --demo `
  --output-dir ai_vision/results/live_gate/my_demo_01
```

합성 프레임 3개와 한국 번호판 예시로 통과 자료 1건을 구성합니다. summary.json은
`uses_synthetic_source=true`, `decision_counts={"DISABLED":1}`, HTTP 요청 0건입니다.
카메라·모델을 열지 않으며 실제 인식 성공의 증거가 아닙니다. 이미 있는 출력 폴더는 거부합니다.

### 촬영 가능한 시점의 실제 카메라 실행

실제 카메라 실행 전에는 설정·패키지 설치 정보·모델 파일을 먼저 점검할 수 있습니다.
아래 기본 명령은 카메라·모델·OCR·HTTP를 실행하지 않으며 패키지를 설치하지 않습니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.check_live_gate `
  --config "카메라구도설정.json" `
  --camera-id GATE_CAM_01 `
  --down-direction ENTRY `
  --output "사전점검.json"
```

`--output`은 생략할 수 있습니다. 지정하면 부모 폴더가 있어야 하고 기존 파일은
덮어쓰지 않습니다. 출력의 `CHECKED`는 설정 형식·패키지 설치 정보·비어 있지 않은
YOLO 가중치 파일을 확인했다는 의미입니다. 패키지 import 호환성, 가중치 무결성,
PaddleOCR 캐시·추론 성공이나 실제 촬영 구도의 적절성을 보장하지 않습니다.
누락·읽기 실패가 있으면 `BLOCKED`, 종료 코드 1과 함께 부족한 항목을 기록합니다.

카메라가 준비됐을 때만 `--probe-camera --camera-index 0`을 추가하세요.
기본 점검을 통과한 경우에만 장치를 열어 한 프레임의 BGR 형식·해상도를 확인한 뒤
해제합니다. 영상·사진 파일은 저장하지 않고 자동 재연결도 하지 않습니다. 장치·읽기·
해제 실패는 `BLOCKED`이며 오류 원문 대신 고정 코드를 기록합니다. 드라이버의 읽기가
멈추는 시간을 별도 스레드로 강제 제한하지는 않습니다. 다른 프로그램이 카메라를
사용하고 있으면 점검에 실패할 수 있으므로 해당 프로그램을 종료한 뒤 다시 확인하세요.

먼저 같은 카메라 구도의 정지 이미지로 설정 위치를 확인할 수 있습니다.
움직이는 번호판 영상은 필요하지 않습니다. JSON의 비율 좌표를 수정한 뒤 아래 명령을
다시 실행하고, 초록 ROI와 빨간 통과선이 원하는 위치인지 확인합니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.preview_gate_config `
  --image "카메라정지화면.png" `
  --config "카메라구도설정.json" `
  --down-direction ENTRY `
  --output "카메라설정확인.png"
```

출력은 새 PNG 파일이어야 하고 부모 폴더는 미리 있어야 합니다. 입력 이미지와
설정은 변경하지 않습니다. 위 이미지 입력 모드는 카메라를 열지 않습니다.
추적 모델·OCR·HTTP는 사용하지 않으며, 화면의
DOWN/UP 문구는 지정한 방향을 보여줄 뿐 실제 입출차 방향의 정확성을 판정하지 않습니다.
원근과 차량 중심점 이동 경로까지 고려해 기준선을 선택해야 합니다.

카메라가 준비됐을 때는 별도 이미지를 촬영하지 않고 한 프레임으로 미리보기를
저장할 수 있습니다. 이 명령은 실제 카메라 0번을 열고 한 번 읽은 뒤 닫습니다.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.preview_gate_config `
  --camera-index 0 `
  --config "카메라구도설정.json" `
  --down-direction ENTRY `
  --output "카메라설정확인.png"
```

`--image`와 `--camera-index` 중 하나만 지정합니다. 카메라 번호는 0~32이며 영상 경로나
URL을 받지 않습니다. 설정·출력 경로 오류는 카메라를 열기 전에 거부합니다.
드라이버가 배열을 재사용할 수 있어 프레임을 복사한 뒤 자원을 해제합니다. 읽기나 해제에
실패하면 미리보기를 저장하지 않으며 자동 재연결도 없습니다. 사용자 중단 시 장치를
해제하고 종료 코드 130을 반환합니다. 저장되는 PNG는 ROI·기준선이 표시된 한 프레임이며
영상 녹화·GUI 창·번호판 인식·HTTP 전송은 수행하지 않습니다.

모델·기존 환경과 카메라가 준비된 뒤, 해당 촬영 구도의 설정 JSON을 먼저 만듭니다.
설정은 영상 분석 문서의 tracker·line_y·line_x·roi 네 항목과 같습니다.
아래는 **DOWN이 실제 입차인 카메라로 확인했을 때**의 예시입니다.
traffic 영상 설정을 다른 구도에 그대로 쓰지 마세요.

```powershell
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_live_gate `
  --camera-index 0 `
  --camera-id GATE_CAM_01 `
  --down-direction ENTRY `
  --config "카메라구도설정.json" `
  --seconds 20 `
  --output-dir ai_vision/results/live_gate/my_camera_01
```

카메라 정수 인덱스만 허용하며 영상 파일·URL은 입력으로 받지 않습니다. 기본 20초,
최대 300초, 내부 프레임 처리 상한 100000장입니다. Ctrl+C 또는 시간·프레임 제한,
읽기 종료 시 멈춥니다. 자동 재연결은 하지 않습니다. GUI 미리보기 창도 열지 않습니다.
실행 도구에는 HTTP 활성화·API 키 인수가 없고 기본 비활성 흐름만 사용합니다.

### 시각·표본·종료 규칙

- 한 실행 동안 고유 session_id와 같은 처리 흐름·Guard를 유지합니다.
- 프레임 read 직후의 단조 시각을 세션 시작 UTC 시각에 연결합니다. 이는 센서 하드웨어
  촬영 시각이 아니라 프로그램의 수집 시각이며 카메라 드라이버 버퍼 지연을 제거하지 않습니다.
- 최근 512개 프레임의 시각을 보관하고 번호·시각의 중복/역행과 다른 세션 stamp를 거부합니다.
- 실시간 실행 루프는 보관 중인 가장 오래된 프레임 번호를 처리기에 전달합니다.
  시각 기록에서 이미 제거된 crop은 OCR 전에 제외합니다. 따라서 높은 수집 빈도나
  작은 시각 보관 한도로 2초보다 먼저 기록이 만료되어도 오래된 시각을 만들어 쓰지 않습니다.
  남은 표본이 부족하면 번호판을 확정하지 않고 후보를 보류합니다.
- OCR 표본은 같은 실행에서 확보한 프레임이고 통과 전 2초 안에 있어야 합니다.
- 원본 차량 crop을 최대 3장/ID, 최소 0.25초 간격으로 보관합니다. 통과 후에만 OCR하며
  이 실시간 경로는 미래 프레임을 기다리지 않습니다. 오프라인의 큰 상자 우선 선택과 다릅니다.
- 버퍼 기본 한도는 활성 차량 16개·총 32MB입니다. 부족한 crop은 고정 점수나 번호로
  대체하지 않습니다. 관찰 공백이 1초를 넘으면 해당 crop 연결을 초기화합니다.
- 같은 추적 ID는 한 실행에서 한 번만 통과 판정합니다. 추적 ID 재사용에는 새 세션이 필요합니다.
- 실시간 관찰의 중심이 ROI 밖으로 나가면 해당 ID의 위치 상태·crop을 함께 지웁니다.
  반대편으로 재진입해도 이전 ROI 안 위치에서 직선으로 통과했다고 간주하지 않습니다.
- 허용 속도를 넘는 위치 점프에서도 위치 상태·crop을 함께 초기화합니다. 이후 새 관찰로
  안정화와 OCR 표본을 다시 모으며 이미 통과한 ID의 중복 억제 기록은 유지합니다.
- 실행 중 해상도 변경·추적/OCR 오류는 실패로 종료합니다. 카메라·crop 버퍼·세션을 정리하고
  종료 뒤 늦은 결과·프레임을 처리하지 않습니다.

### 결과 읽기와 제한

새 실행의 `run_context`에는 실제 카메라 번호, 시간·프레임 제한, 추적기와 ROI·통과선
설정의 사본 및 `tracking_config_sha256`을 보관합니다. RUNNING 요약에도 같은 사본을
넣으므로 실행 도중 원본 설정 파일을 바꾸더라도 기존 결과의 설정은 유지됩니다.
원본 설정 파일의 절대 경로는 저장하지 않습니다. 해시는 숫자 표현을 통일한 설정
내용의 일치 검사이며, 전자서명이나 변조 방지·실제 카메라 구도 확인을 대신하지 않습니다.

합성 데모는 `source_type=SYNTHETIC`이고 카메라 번호·추적 설정·해시는 null입니다.
데모는 합성 프레임 3개의 고정 시나리오를 실행하며 실행 제한 사본도 실제 데모에
사용하는 기본 20초·100000프레임입니다. 카메라 관련 옵션은 실제 카메라 모드용입니다.

JSON을 직접 읽는 대신 [실시간 세션 보고서](RESULTS_REVIEW.md#live-report)로
HTML·CSV를 생성해 상태와 통과 자료를 확인할 수 있습니다.

출력 폴더의 summary.json에 실행 상태·종료 사유·세션 ID·프레임 수·판정별 건수·
통과별 OCR 합의·표본 수·결정 시각을 기록합니다. crop/원본 영상은 이번 루프에서
파일로 저장하지 않습니다. `dropped_crops`는 이미지 보관 실패 횟수,
`dropped_tracks`는 차량 한도로 건너뛴 관찰 횟수이며 실제 차량 정답 수가 아닙니다.
오류 원문 대신 오류 종류와 종료 코드를 기록합니다.

`performance`에는 카메라 read와 추적·OCR·후보 처리 단계의 호출·예외 횟수,
합계·최대 소요 시간, 최대 수집 간격과 1초 초과 간격 횟수를 기록합니다. 시간 측정은
별도 perf_counter를 사용하므로 프레임의 UTC 수집 시각을 변경하지 않습니다.
처리 시간에는 처음의 모델 로딩과 해당 단계에서의 후보 판정도 포함됩니다.
이미지 인식용 recognizer는 차량·번호판·PaddleOCR를 역할별 최초 사용 시 생성합니다.
실시간 추적기가 이미 잘라낸 차량 crop을 읽을 때는 recognizer의 차량 모델을 추가로
요청하지 않습니다. 번호판 탐지에 성공해 문자를 읽는 시점에 PaddleOCR를 요청합니다.
따라서 첫 통과 자료에서는 번호판·OCR 초기화 시간이 처리 시간에 포함될 수 있습니다.
모델 생성은 프로세스 안에서 역할별로 재사용합니다. recognizer의 차량 탐지·번호판 탐지·
OCR 함수는 같은 역할의 모델 호출을 직렬화하며, OCR 결과가 generator여도 결과 순회가
끝날 때까지 잠금을 유지합니다. 서로 다른 역할에는 별도의 잠금을 사용합니다.
모델 객체를 직접 꺼내 호출하는 외부 코드나 여러 프로세스까지 보호·공유하지는 않습니다.
read가 False로 끝난 호출은 읽기 호출 수에는 포함되지만 예외 횟수는 늘리지 않습니다.
시간 제한으로 읽기 직후 중단하면 수집 프레임 수가 처리 호출 수보다 많을 수 있습니다.

실제 LiveGateProcessor의 `processor_statistics`에는 검사한 프레임·관찰 건수,
이미 통과한 ID의 반복 관찰·ROI 밖 관찰·ROI 안 처리 대상 관찰, 관찰 공백으로 crop을
초기화한 횟수, 통과 판정·OCR 표본 처리 호출, 최대 crop 보관 바이트를 남깁니다.
관찰 건수는 반복 검출을 포함하며 고유 차량 수가 아닙니다. OCR 예외가 발생한 호출도
시도 횟수에는 포함되므로 성공 인식 건수로 읽지 않습니다. 합성 데모의 처리기는
실제 추적을 하지 않으므로 processor_statistics는 null입니다.

이 수치는 처리 병목을 찾는 자료입니다. 카메라 센서 FPS·드라이버 버퍼 지연이나
정확도를 측정하지 않으며, 1초 초과 간격만으로 미검출 차량 수를 알 수는 없습니다.

`roi_resets`는 ROI 이탈 때문에 남아 있던 위치·crop 연결을 끊은 횟수이고,
`speed_resets`는 허용 속도 초과로 연결을 끊은 횟수입니다. ROI 밖에 계속 보이는
차량을 매번 초기화 횟수로 세지는 않습니다. 이미 집계한 ID는 새로 처리하지 않습니다.
실제 추적기의 ID 오연결을 완전히 판별하는 기능은 아니며, 검출 자체가 사라졌다
1초 이내 재등장하는 경우에는 기존 공백 규칙이 적용됩니다.

`expired_history_crops`는 시각 기록에서 만료되어 OCR 전에 제외한 crop 수입니다.
차량 미검출 수나 OCR 오답 수가 아닙니다. 직접 LiveGateProcessor를 호출하는 경우에는
`minimum_frame_index`에 같은 세션 clock의 `oldest_frame_index`를 전달해야 동일한
제외 규칙이 적용됩니다. CLI의 실시간 실행 루프는 이를 자동으로 연결합니다.
다른 세션 표본이나 위조 시각을 거부하는 LiveGateSession의 검사는 그대로 유지합니다.

출력은 기본 결과 조회 저장소 recognition 밖의 live_gate에 두며 원본 분석 결과를
덮어쓰지 않습니다. 처리·자원 정리 실패는 summary의 FAILED입니다. 실제 카메라의
열기 실패는 CAMERA_OPEN_FAILED, read 실패·예외는 CAMERA_READ_FAILED이며 종료 코드 1입니다.
첫 프레임을 못 읽어도 정상 종료로 처리하지 않습니다. 실패 전 모은 통과 결과는 유지하며
자동 재연결하지 않습니다. 합성 데모처럼 끝이 있는 입력만 source_end_expected=true로
CAMERA_READ_ENDED 정상 종료를 허용합니다. 카메라 read/모델 추론이 블로킹되는 시간을 강제로
중단하는 별도 스레드 작업은 없으므로 seconds는 절대 마감 시간을 보장하지 않습니다.

다음 read를 시작하기 전에도 별도 단조 시계로 실행 시간 제한을 확인합니다.
OCR·후보 처리 중 제한을 넘긴 경우 새 프레임 읽기를 시작하지 않고 TIME_LIMIT로
멈춥니다. read가 시작된 뒤 오래 걸리면 반환 후 프레임 수집 시각도 검사해 추가 처리를
막습니다. 이미 진행 중인 read·모델 처리를 강제로 취소하는 기능은 아닙니다.
별도 시계는 execute 실행 시작을 기준으로 하며, 세션 생성부터 계산하는 프레임 시각
제한도 유지하므로 먼저 도달한 조건에서 중단합니다.

`deadline`에는 읽기 전 검사 횟수, 마지막 확인 경과 시간과 읽기 전 시간 초과 여부를
기록합니다. 마지막 확인 시간은 종료·자원 정리·저장을 포함한 총 실행 시간이 아닙니다.
시간 초과가 확인된 뒤의 새 read는 수행하지 않으며 기존 결과와 자원 정리는 유지합니다.

직접 execute를 호출해 유한 테스트 입력을 사용하는 경우에는 allow_source_end=True를
명시해야 입력 소진을 정상 종료로 처리합니다. CLI의 실제 카메라 모드에는 이 허용 옵션이
없습니다. 시간·프레임 제한과 사용자 중단은 기존대로 정상 중단으로 구분합니다.
read가 False를 반환한 실패는 예외 발생 횟수에 포함되지 않을 수 있으므로 성능 통계의
예외 횟수만 보지 말고 실행 status·stop_reason도 함께 확인하세요.

실제 하드웨어와 한국 번호판 이동 영상으로 ROI·통과 규칙·OCR 및 버퍼 한도를
확인해야 합니다. 프로세스 재시작·여러 PC 사이의 중복 방지는 여전히 보장하지 않습니다.

### 시작·저장 실패 시 남는 파일

카메라 초기화나 최종 저장 중 오류가 나면 가능한 경우 `failure.json`에 단계
`INITIALIZATION` / `EXECUTION` / `FINAL_SAVE`와 오류 종류, 자원 정리 실패 건수를
기록합니다. 예외 원문은 기록하지 않습니다. 카메라 해제 실패가 처리기·세션 정리를
막지 않도록 각 자원을 따로 정리합니다.

최종 summary 저장 실패 때 이미 만든 전체 결과가 있으면 `recovered_summary.json`에
별도로 저장을 시도합니다. 실패 처리 때문에 기존 summary.json을 작은 실패 요약으로
덮어쓰지 않습니다. 저장장치·권한 문제로 두 파일 모두 저장하지 못할 수도 있습니다.
그때도 종료 코드 1과 실패 기록 저장 불가 메시지를 반환합니다.

`RUNNING` 파일만 남았다고 현재 프로세스가 실행 중인 것은 아닙니다. 비정상 종료나
저장 실패 가능성도 있으므로 [실행 폴더 상태 검사](RESULTS_REVIEW.md#live-report)를
사용하세요. 복구 파일을 확인하는 과정에서 자동 전송이나 재실행은 하지 않습니다.
## OCR 메모리 점검 후속 기록 (2026-10-21)

- AWS 서버 메모리는 약 7.6GiB이며, 컨테이너의 별도 메모리 제한은 없었습니다.
  재시작 후 유휴 컨테이너 사용량은 약 118MiB였습니다. 이는 추론 최대 사용량이 아닙니다.
- 로컬 코드는 OCR CPU 스레드를 2개로 제한하고 문자 탐지 입력을 긴 변 최대
  960픽셀 기준으로 처리하도록 변경했습니다. 재시도용 원본 이미지의 확대 정책은 유지합니다.
- 변경 후 로컬 `car12.png`에서 `91소6408` 인식과 회귀 검사 508개 통과를 확인했습니다.
  AWS에는 아직 이 변경을 배포하지 않았으며, 메모리 부족 해결이나 인식 속도 개선을
  확인한 결과는 아닙니다. 스레드 수와 입력 크기가 이번 종료의 원인이었다고 확정하지 않습니다.
- 후속 배포에서는 단일 요청부터 최대 메모리·응답 시간·재시작 횟수를 측정하고,
  반복 요청에서도 확인한 뒤 인스턴스 증설 필요 여부를 판단합니다.

### AWS 임시 컨테이너 측정 결과

같은 날 기존 `apcms-vision:cpu` 이미지에 변경한 `recognition_models.py`만 읽기 전용으로
연결한 별도 시험 컨테이너에서 확인했습니다. 최신 소스 전체를 빌드·배포한 결과는 아닙니다.
기존 컨테이너는 유지했고, 시험 컨테이너는 메모리 4GiB·CPU 2개 상한으로 실행했습니다.

- `car12.png` 순차 요청 3회 모두 `91소6408`, `KOREAN_VALID`로 응답했습니다.
- 소요 시간은 첫 요청 20.84초, 두 번째 4.98초, 세 번째 4.73초였습니다.
- cgroup `memory.peak`는 2,922,807,296바이트(약 2.72GiB), 마지막 요청 후
  `memory.current`는 1,484,853,248바이트(약 1.38GiB)였습니다. 프로세스 RSS와는 다른 지표입니다.
- `memory.events`의 `max`, `oom`, `oom_kill`은 모두 0, 재시작 횟수도 0이었습니다.
- 기존 종료 기록과 실행 조건·측정 지표가 다르므로 감소 비율이나 단일 원인을 확정하지 않습니다.
  같은 사진의 순차 요청 결과이며 다양한 이미지·동시 요청·장시간 안정성은 추가 확인이 필요합니다.
- 이 조건에서는 인스턴스 증설이 필요하지 않았습니다. 시험 컨테이너와 로컬 SSH 터널은
  종료했으며 기존 서비스의 교체나 Boot·DB 요청은 하지 않았습니다.
- 상세 결과는 Git 제외 경로 `results/aws_memory_checks/ocr_threads2_limit960.json`에 저장했습니다.

### 최신 전체 소스 이미지의 AWS 시험 결과

이후 로컬 Vision 소스 전체를 빌드했습니다. 비밀 설정·가상환경·모델·영상·실행 결과와
Docker 제외 목록의 개발 자료를 뺀 211개 파일을 전송했습니다. Git 커밋·푸시는 수행하지 않았습니다.
이미지 이름은 `apcms-vision:memory-current-20261021`, 이미지 식별값은
`sha256:8737935dd7f2a918510745c412eb9e9b3d6395da1222a90e78a4c193c2c15e0c`입니다.
기존 서비스 교체 없이 별도 컨테이너에 메모리 4GiB·CPU 2개 상한을 적용했습니다.

| 입력 | 관측 결과 |
| --- | --- |
| `car12.png` 최초·반복 | 두 번 모두 `91소6408`, `KOREAN_VALID`. 10.28초·4.83초 |
| `car.jpg` | 차량 3대. 가운데 번호판은 `10-15574`, `REVIEW`; 재시도는 `10-1557` |
| `car3.jpg` 외국 번호판 | `1146NMC`, `FOREIGN_OR_OTHER` |
| `car2.jpg` 여러 차량 | 차량 3대. 가운데 번호판은 `32부05178`, `KOREAN_VALID` |
| 흰색 합성 이미지 | 차량 0대, 번호판 결과 없음 |

`car2.jpg`의 육안 번호판은 `32부5178`이므로 출력에는 숫자 하나가 추가됐습니다.
형식 검사를 통과해도 실제 번호가 정확하다는 뜻은 아닙니다. 임의로 정답 문자열로
보정하지 않았습니다. 원격 실시간 경로는 여러 차량 응답을 차단하지만,
단일 차량의 형식상 유효한 오인식까지 막는다는 검증 결과는 아닙니다.

- 상태·준비 API와 인식 6회 요청은 모두 HTTP 200이었고, 요청 추적·처리 시간 헤더도 확인했습니다.
- cgroup 최대 메모리는 2,527,789,056바이트(약 2.35GiB)였습니다.
  `max`, `oom`, `oom_kill` 이벤트와 재시작 횟수는 모두 0이었습니다.
- 새 Linux 이미지에서 `pip check` 및 모델 로딩·OCR 크기 정책·업로드 제한·진단 헤더·
  원격 판독·기존 AWS 사례 관련 회귀 검사 42개가 통과했습니다. 전체 검사 508개를
  컨테이너에서 실행한 것은 아닙니다.
- 상세 결과와 빌드 소스 해시 목록은 Git 제외 폴더 `results/aws_memory_checks/`의
  `current_image_cases.json`, `vision-current-source-manifest.json`에 저장했습니다.
- 시험 컨테이너와 SSH 터널은 정리했습니다. 새 이미지는 후속 확인을 위해 남겼고,
  기존 `apcms-vision-test`는 유지했습니다. Boot·DB 기록 생성은 하지 않았습니다.

이번 순차 시험에서는 인스턴스 증설이 필요하지 않았습니다. 동시 요청·장시간 실행·
실제 USB 웹캠의 이동 차량 정확도는 아직 확인하지 않았으며, 실서비스 컨테이너도 교체하지 않았습니다.

### 화면·인쇄물 재촬영으로 USB 웹캠 연결 확인

실제 차량을 비출 수 없는 상황에서는 `test_images/car12.png`를 화면에 크게 띄우거나
인쇄해서 웹캠으로 비춥니다. 이것은 촬영부터 AWS 응답까지의 연결 확인이며 실제 차량의
조명·반사·이동·통과 방향 정확도를 검증하지 않습니다. 차량 한 대가 보이도록 맞추고,
화면 재촬영 시 반사나 줄무늬가 생기면 각도·거리·밝기를 조절합니다.

현재 AWS에는 `apcms-vision-camera-check`를 별도로 실행했습니다. 이미지 이름은
`apcms-vision:memory-current-20261021`, 메모리 상한 4GiB, CPU 상한 2개이며,
호스트 `127.0.0.1:18001`에서만 접근합니다. 기존 서비스는 유지합니다.
이 컨테이너는 카메라 조작 결과를 확인하기 위해 실행 중이며 자동 재시작은 설정하지 않았습니다.

PowerShell 첫 번째 창에서 SSH 터널을 열고 그대로 유지합니다.

```powershell
ssh -N -L 127.0.0.1:18000:127.0.0.1:18001 apcms-aws
```

두 번째 창에서 현장 PC의 웹캠 도구를 실행합니다.

```powershell
cd D:\finalProjectB\back\apcms_ai
.\.venv312\Scripts\python.exe -m ai_vision.recognition.camera_recognition --camera-index 0 --vision-api-url http://127.0.0.1:18000
```

웹캠 창을 클릭한 뒤 `R`로 현재 프레임을 한 번 전송하고 터미널에서 번호를 확인합니다.
첫 요청은 모델 준비 때문에 시간이 더 걸릴 수 있으며 인식 중 미리보기가 잠시 멈춥니다.
`Q`로 종료합니다. 여러 차량이 탐지되면 원격 판독 오류로 표시하며 번호 하나를 임의 선택하지 않습니다.
오류가 나면 미리보기로 돌아오고 다음 `R` 입력 전에는 다시 전송하지 않습니다.
사진·영상 파일 저장과 Boot 입출차 전송은 수행하지 않습니다.

시험 후 터널 창에서 `Ctrl+C`를 누르고, 사용한 AWS 시험 컨테이너를 종료·제거합니다.

```powershell
ssh apcms-aws "sudo -n docker stop apcms-vision-camera-check"
ssh apcms-aws "sudo -n docker rm apcms-vision-camera-check"
```

수동 웹캠 도구의 로컬 기본 경로·원격 선택·오류 처리·종료·잘못된 주소 및 카메라 번호 검사
6개를 추가했고, Windows 가상환경의 전체 회귀 검사 514개가 통과했습니다.
사용자가 사진을 비춘 실제 촬영 인식 결과는 아직 확인 전입니다.

### 사용자 웹캠 결과와 연속 프레임 합성 시험

이후 사용자가 전달한 웹캠 터미널 출력에서는 `91소6408`, `32부5178`을 한국 번호판으로,
`7NM4281`을 외국 번호판으로 분류했습니다. 화면·인쇄물 재촬영 결과이며 실제 이동 차량이나
정답 영상 전체를 검증한 것은 아닙니다. 위의 촬영 확인 전 상태는 이 사용자 보고 이전 기록입니다.

별도 AWS 시험 컨테이너에서 `car12.png`를 합성 배경 위로 이동시킨 연속 프레임 32장을
실제 로컬 YOLO 추적과 실제 AWS OCR에 연결했습니다. 추적 ID나 OCR 문자열을 주입하지 않았습니다.
단, 프레임의 이동·0.3초 간격 시각은 합성 자료이며 물리 카메라의 실제 수집 속도가 아닙니다.

- 프레임 9·10·11의 차량 crop OCR 3개 모두 `91소6408`이었고 `CONFIRMED`로 합의했습니다.
- 아래 방향 통과 1건을 생성했고, 같은 추적 ID가 되돌아간 뒤에도 통과 기록은 1건이었습니다.
  이후 같은 ID 관찰 20회는 이미 집계한 차량으로 처리했습니다.
- 세션은 HTTP 비활성 상태였으며 판단은 `DISABLED`, 입출차 요청 시도는 0회였습니다.
  이 시험은 처리기의 같은 ID 재집계 억제 확인이며 활성 HTTP Guard의 전송 중복 검증은 아닙니다.
- AWS cgroup 최대 메모리는 2,303,315,968바이트(약 2.15GiB), 메모리 한도 도달·OOM·재시작은 0회였습니다.
- 상세 결과는 Git 제외 경로 `results/aws_memory_checks/real_tracker_remote_consensus_sequence.json`에
  저장했습니다. 시험 컨테이너와 SSH 터널은 정리하고 기존 서비스는 유지했습니다.

중요한 처리 지연도 확인했습니다. 통과 순간 3개의 원격 OCR을 순차 실행한 프레임의 처리에는
25.266초가 걸렸습니다. 모델 초기 준비 시간이 포함된 단일 관측값이며 일반적인 처리 시간으로
단정할 수 없지만, 현재 동기 구조에서는 이 시간 동안 다음 카메라 프레임을 읽지 못합니다.
따라서 실시간 처리 성능을 통과한 결과가 아닙니다. 다음 개발 우선순위는 OCR 대기 중 수집 중단을
줄이는 구조와 유한한 대기열·종료 처리를 함께 점검하는 것입니다. 실제 웹캠의 ID 변경·추적 공백과
연속 차량 처리 능력도 별도로 확인해야 합니다.

### 중간점검과 최신 프레임 수집 선택 기능

현재 개발·자동 검사는 회사 Windows PC의 `apcms_ai/.venv312/Scripts/python.exe`
(Python 3.12.7)에서 진행합니다. AWS Ubuntu Docker의 전체 소스 빌드·사진 인식 시험과
현장 PC USB 웹캠의 사진 재촬영 연결은 확인했지만, 실제 이동 차량·동시 요청·장시간 운용은
확인하지 않았습니다. 현장 PC가 촬영·YOLO 추적을 담당하고 AWS는 OCR 요청을 받습니다.
AWS 인스턴스가 현장 PC의 USB 장치를 직접 여는 구조가 아닙니다.

현재 우선순위는 원격 OCR 대기 중 수집·추적 공백, 실제 차량 번호판 정확도,
최종 배치의 Boot·DB 연결 확인입니다. 보조 보고서 기능 확대보다 이 항목들을 먼저 처리합니다.

`run_live_gate`에 선택 옵션 `--buffered-capture`를 추가했습니다. 기존 실행 명령에 붙이면
별도 스레드가 카메라를 계속 읽으며 대기 프레임을 최신 한 장으로 덮어씁니다.
오래된 프레임을 모두 처리하는 방식이 아니므로 프레임 유실은 의도된 동작입니다.
차량 추적과 OCR은 여전히 같은 처리 루프에 있으므로 OCR 대기 중 추적까지 계속되는 기능은 아닙니다.
짧게 지나가는 차량을 놓치는 문제를 완전히 해결했다고 판단하면 안 됩니다.

- 기존 기본 모드는 유지합니다. 합성 데모에는 이 물리 카메라 옵션을 사용할 수 없습니다.
- 처리 시작 시각 대신 실제 `read` 직후 단조 시각을 프레임 시각으로 사용합니다.
  폐기된 프레임에 가짜 시각·번호를 채워 연속된 추적으로 위장하지 않습니다.
- 결과 JSON의 `capture_buffer`에 실제 수집·전달·폐기 수, 최대 대기 이미지 바이트,
  수집 스레드 생존 여부와 오류 종류를 기록합니다. `captured_frames` 본문은 기존처럼
  처리 루프에 전달된 프레임 수이며 물리 수집 수와 구분합니다.
- 대기 프레임의 메모리 상한은 기본 32MiB입니다. 카메라 드라이버·추적·OCR 전체의 메모리 상한은 아닙니다.
- 처리 종료 시 수집 중단을 요청하고 최대 2초 기다립니다. 네이티브 카메라 읽기가 멈춰 있으면
  강제로 스레드를 종료할 수 없으므로 정리 실패로 보고합니다. 읽기가 돌아오면 수집 스레드가 장치를 해제합니다.
- 실행 시간 제한은 기존처럼 처리 루프 경계에서 확인합니다. OCR·네이티브 read를 강제로 끊지 않으며,
  OCR이 길어지면 설정 시간을 넘겨 종료할 수 있고 수집도 정리 시점까지 계속될 수 있습니다.

실제 USB 웹캠 640×480에서 처리 측이 1초 대기하는 동안 추가 29장을 수집했습니다.
총 수집 30장 중 2장을 전달하고 28장을 폐기했으며, 최대 대기 이미지 921,600바이트,
종료 후 작업 스레드 없음·오류 없음으로 확인했습니다. 이미지 파일·OCR·입출차 전송은 사용하지 않았습니다.
결과는 Git 제외 경로 `results/camera_checks/buffered_capture_20261021.json`에 저장했습니다.
관련 검사 9개와 Windows 전체 회귀 검사 523개가 통과했습니다.

다음 단계는 OCR 작업을 차량 추적 루프에서 분리하면서 작업 대기열·메모리·원본 프레임 시각·
종료 시 미완료 작업을 함께 관리하는 것입니다. 최신 프레임 수집만으로 완료된 단계는 아닙니다.

### 원격 OCR 비동기 선택 기능

이후 `run_live_gate --async-ocr`를 추가해 통과 차량의 OCR을 차량 추적 루프에서 분리했습니다.
`--vision-api-url`을 지정한 원격 모드에서만 선택할 수 있고, 기존 동기 기본 실행은 유지합니다.
현장 PC에서 동작하는 변경이며 이 선택 기능을 AWS 서버에 별도로 올려야 실행되는 구조는 아닙니다.

- 메인 스레드는 촬영·YOLO 추적·통과 판정을 계속합니다. OCR 작업 스레드 한 개는
  해당 차량의 표본 최대 3개를 순서대로 원격 인식합니다. 번호판 합의 규칙은 유지합니다.
- 실행 중 작업을 포함해 최대 2건, 대기 차량 이미지 합계 기본 32MiB로 제한합니다.
  한도를 넘은 통과 차량은 `async_ocr.dropped_jobs`에 기록하며 자동 재시도하지 않습니다.
  추적 버퍼·카메라 버퍼·모델 전체 메모리를 이 수치로 제한한다는 의미는 아닙니다.
- 일반 시각 기록에서 제거된 프레임도 결과 검증이 가능하도록 최대 두 작업, 작업당
  네 프레임의 세션 발급 원본 시각만 추가 보관합니다. 완료·실패·종료 후 반납합니다.
  결과 완료 시각을 원래 차량의 통과 시각으로 사용하지 않습니다.
- 결과는 제출 순서로 메인 스레드가 검증한 뒤 기존 중복 억제·전송 판단에 전달합니다.
  OCR 작업 스레드에서는 Boot 전송이나 세션 후보 판정을 실행하지 않습니다.
- 종료 시 시작 전 작업을 취소하고 이미 요청 중인 작업이 돌아오면 남은 표본 요청을
  중단합니다. 미반영 작업은 `abandoned_jobs`에 기록하며 종료 후 후보로 전달하지 않습니다.
  이미 진행 중인 HTTP 요청은 강제로 중단할 수 없어 종료가 지연될 수 있습니다.
  정상 종료 뒤에도 모든 대기 차량의 결과를 반드시 반영하는 정책은 아닙니다.
- 작업 오류는 실패로 보고합니다. 기존 동기 실행처럼 오류를 숨기거나 무제한 재시도하지 않습니다.
  실제 Boot 전송을 켜면 Boot 요청 자체는 여전히 메인 스레드를 기다리게 할 수 있습니다.

기존 `run_live_gate` 명령에 다음 선택 옵션을 붙입니다. 물리 카메라·설정·카메라 ID·방향·
새 출력 폴더 인자는 기존처럼 지정해야 합니다. 터널과 실행 중인 AWS API도 필요합니다.

```text
--vision-api-url http://127.0.0.1:18000 --async-ocr --buffered-capture --seconds 60
```

모델 초기 준비와 원격 OCR이 길어질 수 있으므로 시험은 60초처럼 충분한 시간으로 진행합니다.
시간 제한 전에 완료되지 않은 OCR은 종료 시 미반영될 수 있습니다. `dropped_jobs`나
`abandoned_jobs`가 있으면 모든 차량 처리가 성공했다고 판단하지 않습니다.

실제 로컬 YOLO와 AWS OCR을 연결한 합성 이동 시험에서 124장을 처리했습니다.
OCR 작업이 미완료인 시점에 다음 프레임 읽기를 112회 시작했고, 표본 3개 모두
`91소6408`로 합의해 통과 기록 1건을 생성했습니다. 원래 통과 시각은 세션 시작 후
약 3.188초이며 완료 시각으로 덮어쓰지 않았습니다. 추가 시각 보관도 실제 시험에서 사용했습니다.
실제 시계로 실행했지만 차량 이동·입력 프레임은 합성 자료입니다.

- 메인 루프의 최대 프레임 처리 시간은 약 1.353초였습니다. 원격 OCR 요청 자체가 이 시간에
  끝났다는 뜻이 아니며, 이전 동기 시험과 조건이 완전히 같지 않아 속도 개선 비율은 산출하지 않습니다.
- 제출·완료 1건, 한도 초과·미반영 종료·대기 작업·작업 오류 0건, 입출차 요청 0회였습니다.
- AWS 최대 메모리는 2,392,915,968바이트(약 2.23GiB), OOM·재시작은 0회였습니다.
- 관련 검사 11개를 추가했고, Windows 전체 회귀 검사 534개가 통과했습니다.
- 결과는 Git 제외 경로 `results/aws_memory_checks/async_real_tracker_remote_20261021.json`에
  저장했습니다. 시험 컨테이너와 SSH 터널은 정리했고 기존 AWS 서비스는 유지했습니다.

실제 이동 차량의 인식 정확도·연속 진입 부하·활성 Boot 전송을 포함한 비동기 운영은 아직
검증 전입니다. 처리 지연 시 대기열 손실을 숨기지 않는 상태로 실제 촬영 조건에서 확인해야 합니다.

### USB 웹캠 비동기 모드의 사진 이동 시험 준비

`run_live_gate --preview`로 실제 입력 화면에 ROI·수평 통과선을 표시할 수 있습니다.
미리보기에는 프레임 복사본을 사용하므로 그린 선이 OCR 입력에 들어가지 않습니다.
창을 클릭한 뒤 `Q`로 종료합니다. 첫 결과 대기 중에는 바로 종료하지 말고 결과 출력을 기다립니다.
종료 시 창은 먼저 닫고 카메라·OCR 작업·세션을 정리합니다. 사진이나 영상 파일은 저장하지 않습니다.
화면 없는 환경에서는 이 옵션을 사용하지 않으며, GUI를 생성하기 전에 실행 조건을 검사합니다.

`data/tracking_configs/webcam_connection_check.json`은 전체 화면 ROI와 화면 중앙 통과선으로
구성한 연결 시험 전용 설정입니다. 실제 현장의 보정된 ROI나 입출차 방향을 의미하지 않습니다.
사용자는 화면·인쇄물만 촬영할 수 있다고 알려주었으므로 아래 결과도 그 범위로 구분합니다.

AWS 시험 API는 `apcms-vision-webcam-async-check` 컨테이너로 준비했습니다. 기존 서비스와
별개이며 메모리 4GiB·CPU 2개 상한, 호스트 `127.0.0.1:18001` 바인딩을 사용합니다.
첫 PowerShell 창에서 터널을 열고 유지합니다.

```powershell
ssh -N -L 127.0.0.1:18000:127.0.0.1:18001 apcms-aws
```

다른 PowerShell 창에서 다음을 실행합니다. 결과 폴더는 시각별로 새로 만듭니다.

```powershell
cd D:\finalProjectB\back\apcms_ai
$webcamRunTag = Get-Date -Format 'yyyyMMdd_HHmmss'
.\.venv312\Scripts\python.exe -m ai_vision.recognition.run_live_gate --config ai_vision/data/tracking_configs/webcam_connection_check.json --camera-index 0 --camera-id WEBCAM_CONNECTION_CHECK --down-direction ENTRY --vision-api-url http://127.0.0.1:18000 --async-ocr --buffered-capture --preview --seconds 60 --output-dir "ai_vision/results/live_sessions/webcam_async_$webcamRunTag"
```

`test_images/car12.png`의 차량 전체가 보이게 촬영합니다. 차량 중심을 빨간 선 위에 몇 초
유지한 뒤 천천히 아래로 움직이고 선 아래에서도 몇 초 유지합니다. `R` 입력은 필요 없습니다.
같은 차량을 놓치지 않도록 화면 밖으로 빼거나 갑자기 가리지 않습니다.
원격 OCR이 끝나면 터미널에 통과 ID·화면 방향·번호판 합의·전송 판단을 출력합니다.
`91소6408`·`CONFIRMED`·`DISABLED`를 확인하는 것이 목표이며, 세션 요약도 새 결과 폴더에 저장됩니다.

한 번 처리된 같은 추적 ID는 되돌아가도 재집계하지 않습니다. 차량을 놓쳤다가 다른 ID로
재탐지하면 같은 ID 재집계 억제만으로는 동일 차량임을 보장할 수 없습니다.
HTTP 비활성 시험은 활성 전송 Guard의 동작 검증을 대신하지 않습니다.

시험 종료 후 터널 창에서 `Ctrl+C`를 누르고 준비한 시험 컨테이너를 정리합니다.

```powershell
ssh apcms-aws "sudo -n docker stop apcms-vision-webcam-async-check"
ssh apcms-aws "sudo -n docker rm apcms-vision-webcam-async-check"
```

미리보기의 원본 보존·Q 종료·화면 없는 환경·실패 정리 관련 검사 7개를 추가했고 전체 회귀
검사 541개가 통과했습니다. 이번 사진 이동 시험의 실제 사용자 촬영 결과는 아직 확인 전입니다.

### 첫 프레임 종료 오류 수정과 사용자 준비 단계

사용자가 실행한 `webcam_async_20261021_171142/summary.json`에서는 시간 제한이 아니라
`CAMERA_READ_FAILED`로 약 2.2초 만에 종료됐습니다. 수집 스레드의 오류는 `ValueError`였고
OCR 제출은 0건이었습니다. 같은 카메라 연결 방식으로 재현한 결과 첫 두 프레임의
`time.monotonic()` 값이 같았습니다. 수집 코드가 같은 시각까지 오류로 처리한 것이 원인이었습니다.

- 같은 시각의 프레임은 가짜 시각을 만들지 않고 버리되 계속 수집하도록 수정했습니다.
  실제 시각 역행은 여전히 오류입니다. 제외한 수는 `duplicate_timestamp_frames`에 별도 기록합니다.
- `--preview` 실행은 준비 화면에서 기다립니다. 창을 클릭하고 스페이스바를 눌러야
  세션 시계와 60초 측정을 시작합니다. 준비 중에는 촬영 구도를 충분히 맞출 수 있습니다.
  준비 화면의 `Q`는 측정 없이 정상 취소하며 입출차 요청을 보내지 않습니다.
- 준비 단계는 일반 카메라를 사용하고, 측정용 별도 수집 스레드와 세션은 준비 완료 뒤
  생성합니다. 준비 프레임의 오래된 시각이 측정 세션에 섞이지 않도록 했습니다.
- 수정 후 같은 웹캠에서 총 61장을 수집했고 중복 시각 2장을 제외하면서 두 번째 읽기와
  자원 해제에 성공했습니다. 이는 짧은 수집 재시험이며 전체 이동·OCR 시험을 완료한 결과는 아닙니다.
- 관련 검사 6개를 추가했고 전체 회귀 검사 547개가 통과했습니다. 실제 재시험 요약은
  Git 제외 경로 `results/camera_checks/buffered_capture_clock_fix_20261021.json`에 저장했습니다.

다시 실행할 때는 `$webcamRunTag = Get-Date -Format 'yyyyMMdd_HHmmss'`를 먼저 실행해 새 결과
폴더 이름을 만들고 위의 동일 명령을 사용합니다. 준비 화면에서 스페이스바를 누른 뒤
차량 사진을 중앙선 위에서 아래로 천천히 이동시킵니다.

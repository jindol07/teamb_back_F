# 입출차 연동과 중복 억제

[시작 안내](../readme.md) · [영상 분석](VIDEO_ANALYSIS.md) · [결과 검토](RESULTS_REVIEW.md) · [입출차 연동](VEHICLE_INTEGRATION.md)

> 아래 명령은 모두 `D:\finalProjectB\back\apcms_ai`에서 실행합니다.
> 기존 결과를 보존하려면 예시의 출력 이름을 새 이름으로 바꿔 사용하세요.

UUID를 DB에 저장하지 않는 설계를 유지합니다. 기본 비활성 HTTP 전송 경로와 별도 카메라 세션 실행 루프를 구현했습니다. 기존 sender에는 자동 연결하지 않았고 실제 카메라 하드웨어도 검증하지 않았습니다. 지금까지의 전송 경로 검증은 모의 세션이며 실제 Boot·DB 검증이 아닙니다.

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

`LiveGateClock` → `LiveGateProcessor` → `LiveGateSession` → 기본 비활성
`VehicleDeliveryFlow`를 `run_live_gate`에서 연결합니다. 기존 웹캠 코드와 sender를
수정하지 않은 별도 실행 경로입니다. 실제 카메라·주행·실제 모델 OCR 성능 검증은
아직 하지 않았으며, 이번 검증은 가짜 카메라와 주입한 추적/OCR 함수 기준입니다.

### 카메라·모델·HTTP 없는 실행 확인

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
설정은 변경하지 않습니다. 카메라·추적 모델·OCR·HTTP는 사용하지 않으며, 화면의
DOWN/UP 문구는 지정한 방향을 보여줄 뿐 실제 입출차 방향의 정확성을 판정하지 않습니다.
원근과 차량 중심점 이동 경로까지 고려해 기준선을 선택해야 합니다.

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
- OCR 표본은 같은 실행에서 확보한 프레임이고 통과 전 2초 안에 있어야 합니다.
- 원본 차량 crop을 최대 3장/ID, 최소 0.25초 간격으로 보관합니다. 통과 후에만 OCR하며
  이 실시간 경로는 미래 프레임을 기다리지 않습니다. 오프라인의 큰 상자 우선 선택과 다릅니다.
- 버퍼 기본 한도는 활성 차량 16개·총 32MB입니다. 부족한 crop은 고정 점수나 번호로
  대체하지 않습니다. 관찰 공백이 1초를 넘으면 해당 crop 연결을 초기화합니다.
- 같은 추적 ID는 한 실행에서 한 번만 통과 판정합니다. 추적 ID 재사용에는 새 세션이 필요합니다.
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

출력은 기본 결과 조회 저장소 recognition 밖의 live_gate에 두며 원본 분석 결과를
덮어쓰지 않습니다. 처리·자원 정리 실패는 summary의 FAILED이고 단순 읽기 종료는
CAMERA_READ_ENDED로 표시합니다. 카메라 read/모델 추론이 블로킹되는 시간을 강제로
중단하는 별도 스레드 작업은 없으므로 seconds는 절대 마감 시간을 보장하지 않습니다.

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

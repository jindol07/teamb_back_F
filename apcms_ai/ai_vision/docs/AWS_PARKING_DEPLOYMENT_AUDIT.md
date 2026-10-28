# AWS 주차 배포 사전 점검 — 2026-10-28

## 2026-10-28 AWS 주차 실제 전체 시험 성공 — 현재 확인 결과

실제 카메라 A1/B0와 AWS 배포 API/Oracle로 수행한
results/parking_demo/aws_20261028/e2e_manual_0e153185/http_e2e_result.json의
success=true, completion_checks 전 항목 true, incomplete_reasons=[]를 확인했습니다.
91소6408 입차→Z02 WRONG_SPACE(이용 미연결 DB 확인)→Z01 MATCHED→출차가
동일 이용 ID32로 처리됐습니다. DB LINKED_ROWS1/EXITED_ROWS1/OPEN_ROWS0,
LINK_VERSION2, B 신원 EMPTY/작업자 종료코드0·0 확인. B OCR 재인식 없이 A 신원
전달 방식으로 수행했습니다. 실제 관리자 웹 화면 표시는 이번 실행에서 확인하지 않았습니다.
시험 생성 행19개 삭제/잔여0/기존 해당 번호 이용0 보존. 별도 새 JDBC 읽기 전용 조회에서
소유 매니페스트의 차량9/층9/구역18/구획64·65/예약18/이용32 및 구획 이벤트·이력
모두0건 재확인했습니다. 기존 업무 데이터나 사무실은 수정하지 않았습니다.
근거: results/deployment_audit_20261028/schema_apply/cleanup_recheck_0e153185.json.
이번 성공으로 한국 시각 기준 시험 예약 수정의 실제 AWS 동작도 확인됐습니다.
이는 한 대·두 시험 구획·수동 시작 경로의 성공입니다. 다중 차량 식별, 구획 이동 후
연결 해제 API, 배포 AI 컨테이너 자동 카메라 기동, 공유 화재 실시간 AWS 전송까지
검증됐다는 뜻은 아닙니다. 운영 모델의 회색 배경 SMOKE 오탐 개선도 여전히 남았습니다.

## 최신 적용 결과 — 아래 미적용 기록보다 우선

사용자가 ‘추가하기로 했던 누락을 찾아 모두 추가’하도록 명시 승인했습니다.
AWS15.165.205.246:1521/xe ALPHARKING,Oracle11.2.0.2.0에 다음3개를 실제 적용했습니다.

| 추가 객체 | 정의·검증 |
|---|---|
| PARKING_USAGE.LINK_VERSION | NUMBER(18,0),DEFAULT0,NOT NULL |
| CK_PUSAGE_LINK_VERSION | CHECK(LINK_VERSION>=0),ENABLED/VALIDATED |
| TRG_PUSAGE_LINK_VERSION | INSERT0,구획/예약/차량번호/출차 변경 시+1,그 외 유지;VALID/ENABLED |

적용 전3개가 없고 기존 PARKING_USAGE 트리거도 없는지 재조회했습니다. 기존 객체를
덮어쓰지 않도록 실제 실행은CREATE TRIGGER를 사용했습니다. 적용 후 새 JDBC 연결에서
재조회했고,트리거 소스가 승인된 SQL과 일치하며USER_ERRORS0건임을 확인했습니다.
비교한 기존 컬럼 정의와 화재 해시 인덱스는 변경되지 않았습니다. 기존 화재 해시 컬럼·
인덱스·테이블·시퀀스는 이미 존재하므로 중복 생성하지 않았고 새 테이블은 만들지 않았습니다.

DDL은 실제 반영·커밋됐습니다. 기존 이용의 신규 버전 기본값은0이며,기존 구획·예약·출차
업무 필드를 DML로 수정하지 않았습니다. 실제 업무 행을 이용한 트리거 상태 전이 시험과
AWS 주차 전체 연동 검증은 아직 수행하지 않았으며 서버 해제 플래그도 변경하지 않았습니다.

근거:results/deployment_audit_20261028/schema_apply의apply_before.json,applied_ddl.sql,
applied_steps.json,apply_after.json,reconnect_verification/inspect_before.json,
verification_summary.json. 소스SQL은apcms_a/docs/sql/parking-usage-link-version.sql.

아래는 오늘 적용 전 확인 기록입니다. ‘0개·미적용’은 적용 이전 상태를 뜻합니다.

## 실제 확인

팀장님 DB 인스턴스의 주소가 변경됐습니다. SQLGate에서15.165.205.246:1521/xe,
실제 세션 사용자ALPHARKING,Oracle11.2.0.2.0을 SELECT로 확인했습니다.
연결 별칭 alpharking_1016과 실제 스키마명을 구분합니다. 비밀번호를 조회·출력하지 않았습니다.
이전15.164.166.210은 현재 연결 대상으로 사용하지 않습니다. 로컬.env는 수정하지 않았습니다.

주차 입출차·예약 연결·점유·판정 기록 코드에서 사용하는8개 테이블의 필수57개 컬럼이
모두 존재하며,사용하는 시퀀스3개도 존재합니다. 이는 존재 여부 대조이고 전체 FK·제약·
컬럼 형식·업무 트랜잭션 동작의 검증 완료를 의미하지 않습니다.

| 대상 | 필수/존재 컬럼 수 |
|---|---|
| AI_DETECTION_EVENT | 5/5 |
| PARKING_FLOOR | 2/2 |
| PARKING_RESERVATION | 7/7 |
| PARKING_SPACE | 9/9 |
| PARKING_SPACE_HISTORY | 15/15 |
| PARKING_USAGE | 11/11 |
| PARKING_ZONE | 3/3 |
| VEHICLE | 5/5 |

SEQ_AI_DETECTION_EVENT,SEQ_PARKING_SPACE_HISTORY,SEQ_PARKING_USAGE는 각각1개 존재합니다.
RAW_PAYLOAD는CLOB,ENTRY_AT/EXIT_AT은DATE이며,SOURCE_EVENT_HASH와SOURCE_GROUP_HASH는
VARCHAR2(64)입니다. UX_ADE_SOURCE_EVENT_HASH는UNIQUE/VALID 상태입니다.
AI 이벤트/입차INSERT에서 제공하지 않는 추가 NOT NULL·기본값없는 컬럼 조회는0행입니다.
DEFAULT NULL 등 기본값 내용 전체와 다른 제약 조건까지 검증한 것은 아닙니다.

## 누락과 코드 적용 범위

PARKING_USAGE.LINK_VERSION,CK_PUSAGE_LINK_VERSION,TRG_PUSAGE_LINK_VERSION은 각각0개입니다.
개발21c에만 적용됐다는 기존 기록과 일치합니다. 실제DB에서는 변경하지 않았습니다.

현재 로컬 AiVehicleEventService는 space-release-enabled 기본false이고,
매칭 응답의 버전 조회는 플래그true에서만 실행합니다. release()도false이면SQL진입전503입니다.
따라서 '버전 컬럼이 없으면 일반 입출차·예약 연결도 반드시 실패한다'는 이전 설명은
잘못된 단정입니다. 자동 구획 해제를 활성화할 때는3개 객체를 먼저 적용·검증해야 합니다.
현재 배포 코드와 플래그는 확인 전이므로 실제배포환경에도이조건이같다고확정하지않습니다.

## 배포 HTTP 읽기 전용 확인

사용자가 고정 주소52.79.133.132:3000을 확인했습니다.

- 웹 루트:HTTP200,HTML.
- /admin-api/actuator/health:HTTP200,JSON statusUP.
- /admin-api/actuator/health/readiness:HTTP200,JSON statusUP.
- /admin-api/actuator/info:HTTP401. 인증 우회 시도 없음.

로컬소스는Actuator health만노출합니다. healthUP만으로배포커밋·실제DB호스트·해제플래그를
판정하지않습니다. 사용자에게배포커밋,DB_URL호스트,parking.ai.space-release-enabled를
팀장님께확인하거나원격읽기전용접근방법제공을요청했습니다. 자격정보전달은요청하지않았습니다.

## 다음 순서

1. 배포 코드·DB 호스트·플래그 확인. 현재 일반 주차 구조 자체가 빠진 상태로 단정하지 않음.
2. 현재 기능 범위에 필요한 DB 변경만 확정하고3개 객체 적용이 필요하면 사용자 승인 후 실행.
3. 승인된 별도 시험 데이터로 배포된 입차→예약 판정→구획 연결→출차와 정리까지 검증.
4. 그 후 FIRE/SMOKE 모델 조합의 실제 추론 구현으로 복귀.

## 근거와 실행 범위

results/deployment_audit_20261028의core_required_columns.sql,column_type_check.sql,
schema_observations.json,deployment_http_readonly.json에조회문·관찰값·HTTP응답요약보존.
SQLGate결과그리드를직접확인해기록했으며자동JDBC추출결과로표현하지않습니다.
처음대조조회는ORDER BY별칭문제ORA00904로실패했고ORDER BY1로수정후11행정상조회했습니다.
DB구조오류나업무SQL실패와구분합니다.
DDL/DML/업무행조회/행잠금/NEXTVAL/COMMIT/이벤트POST없음. 로컬서버·카메라시작과Git조작없음.

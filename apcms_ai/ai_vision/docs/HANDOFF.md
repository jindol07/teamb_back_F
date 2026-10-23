# AI Vision 작업 인수인계 — 2026-10-23

## 카메라 사용 규칙

사용자 책상은 고정된 시험 환경이 아닙니다. 카메라를 쓰기 전에 목적·배치·움직임·예상 시간을 설명하고,
해당 시험 방식으로 준비됐다는 답변을 받은 뒤 시작합니다. 한 장의 구도 확인 촬영도 포함합니다.
이전 배치 확인이나 단순 `1` 요청만으로 현재 준비 상태를 가정하거나 카메라를 켜지 않습니다.
실제 시험 때마다 그 시점의 준비 상태를 확인하며, 준비를 기다리는 동안 카메라 없는 작업을 진행합니다.

## 현재 상태와 다음 순서

### 이번 PR의 일회성 통합 범위 (2026-10-23)

사용자가 이번 PR에 한해 다른 작업의 변경도 모두 포함하도록 승인했습니다.
AI 주차·예약·구획 연결/해제와 함께 관리자 화재 업무 API·알림 조회·설정·관련 검사를 포함합니다.
이 승인은 다음 작업의 화재 수정·업로드까지 확대되지 않습니다. 다음부터 기존 AI 전용 범위를 유지합니다.
최신 develop b254e1b5에서도 사용자 AlpharkingApplication이 삭제되어 로컬 삭제와 일치합니다.
따라서 해당 삭제는 develop 대비 별도 PR 변경이 아닙니다. 로컬 ignored ApcmsUApplication은 그대로 유지합니다.
사용자가 STS에서 사용자 서버 재시작 성공을 확인했습니다.
DDL 파일은 배포용 참고 자료이며 이 PR 작업에서 DB 변경·실제 업무 API·카메라 시험은 수행하지 않습니다.
관리자 실행 클래스의 로컬 ignored 의존성은 여전히 별도 팀 확인 사항입니다.


### 사용자 모듈 중복 실행 클래스 삭제 (2026-10-23)

사용자 지시로 develop에서 추가된 apcms_u의 AlpharkingApplication.java를 삭제했습니다.
기존 로컬 ignored ApcmsUApplication과 crosConfigurer 빈이 중복되어 서버 시작이 실패한 것이 원인입니다.
ApcmsUApplication은 유지하며 STS Main type도 기존 값을 사용합니다. Gradle clean 후 재컴파일·예약 검사19개 통과.
서버 전체 시작은 아직 재확인하지 않았습니다. STS도 F5와 Project > Clean 후 재실행해야 합니다.
이 삭제는 아직 미스테이징이며 후속 Git 업로드 때 별도 삭제 변경으로 확인해야 합니다.

### develop 동기화 완료 (2026-10-23)

사용자 승인으로 feature/ai-vision을 origin/develop b318275a0까지 fast-forward했습니다.
겹치는 10개 파일은 팀원 수정(감지 시각의 Instant 비교, DTO Alias·매퍼 정리, 예약 추천 변경)과
기존 예약 보호·구획 연결/해제 기능을 통합해 복원했습니다. 기존 충돌 후보 6개는 통합본으로 해소했습니다.
추가로 해제 API 시각 검증도 Instant 비교로 맞추고 기존 검사 2개에 Alias 등록·시간대 회귀 검사를 반영했습니다.
동기화 시점의 다른 로컬 파일 52개는 SHA-256 비교로 보존을 확인했습니다.
복구용 stash 1개와 원본·통합본 백업은 유지합니다. results/git_reviews/20261023_144305는 Git 제외입니다.
stash는 이미 통합해 복원한 내용이므로 다시 pop/apply하지 않습니다.
동기화 후 실제 소스에서 관리자 주차 73개·사용자 예약 19개 검사가 통과했습니다.
스테이징·커밋·푸시는 하지 않았습니다. 화재·application.properties의 기존 로컬 수정은 보존했습니다.
다음 업로드 전에는 그 시점의 origin/develop을 재확인하고 AI/주차 변경만 선별해야 합니다.
관리자 실행 클래스 ApcmsAApplication은 기존 로컬 ignored 파일에 의존하므로 새 PC 재현성은 별도 팀 확인이 필요합니다.


### 한 대 시연의 A→B 신원 전달 구현 (2026-10-23)

공용 DB 업무 데이터 시험은 사용자 요청대로 계속 보류합니다. 이번에는 AI 코드만 변경했습니다.
A의 정상 입차 응답에서 차량번호·양의 주차 이용 ID를 보존하고 새 실행 폴더의 single_vehicle_handoff.json에 전달합니다.
B는 이 현재 실행 파일에서 받은 신원과 단일 추적 대상·유일한 연속 점유·기존 정차 조건을 결합합니다.
B의 OCR 표본을 꾸며 만들지 않고 identity_basis=SINGLE_VEHICLE_ENTRY_HANDOFF로 구분합니다.
두 번째 다른 차량이 관찰되면 신규 입차 POST 전에 보류하고 기존 신원을 덮어쓰지 않습니다.
동일 이용 ID의 출차 성공 때 신원을 비우고 B의 이전 연결 억제를 해제합니다. 다른 이용의 출차는 정리 근거가 아닙니다.
A 종료/손상 파일/다른 실행/5초 heartbeat 만료는 B 신원 사용을 중단합니다. 새 입차에는 새 정차 근거가 필요합니다.
동일 PC의 실행 간 파일 전달 방식이며 다중 차량·다중 입출차 카메라의 일반 운영 기능이 아닙니다.
독립 OCR 모드는 기본값으로 유지합니다. 한 대 모드는 B의 중간 자동 구획 해제와 함께 켤 수 없습니다.
A→B 입력 신원은 Boot 성공 응답에 의존하므로 A에서 HTTP를 명시한 실제 모드만 사용할 수 있습니다.
실제 모델·카메라·Boot 업무 POST·공용 DB 행 수정은 하지 않았으며 자동 해제도 활성화하지 않았습니다.
모의 검사 22개를 기존 검사 파일6개에 통합했고 AI 전체844개 통과입니다. 과거822개는 이전 검사 수입니다.

실행 옵션(지금 실행하지 않음):
- A: 기존 run_live_gate 명령에 --single-vehicle-handoff 추가. 새 출력 폴더에 single_vehicle_handoff.json 생성.
- B: 기존 run_parking_camera --track-vehicles 명령에 --single-vehicle-handoff <A 출력 폴더>/single_vehicle_handoff.json 추가.
- B에서 --enable-space-release-http를 함께 사용하지 않습니다. B --tracking-target vehicle(기본)은 차체 위치,
  plate는 번호판 위치를 근거로 쓰며 차량 전체 포함을 보증하지 않습니다.
- A는 기존 실행 시간 상한300초 안에서 계속 관찰해야 합니다. A 종료 시 B가 차량 정보를 계속 유지하지 않습니다.
- 실제 실행은 공용 DB 업무 이벤트 시험 허용과 카메라 준비 확인 후 진행합니다.

변경 운영 Python8개:
recognition/single_vehicle_handoff.py(신규), live_gate_session.py, run_live_gate.py, vehicle_response.py,
vehicle_delivery_flow.py, vehicle_live_candidate.py, parking/vehicle_space_tracker.py, run_parking_camera.py.
기존 검사6개: test_live_gate_context.py, test_live_gate_session.py, test_run_live_gate.py,
test_vehicle_space_tracker.py, test_vehicle_delivery_flow.py, test_parking_deployment.py.
문서는 HANDOFF.md와 VEHICLE_INTEGRATION.md에 통합했습니다. Boot·화재·프런트·DB·스테이징 변경은 없습니다.

검증 한계: Boot MATCH 요청 계약에는 기대 이용 ID가 없으므로, 다른 관리자가 입출차 기록을 바꾼 경우
응답 이용 ID 불일치를 받은 뒤 후속 전송을 중단하는 보호만 있습니다. 이미 반영된 DB를 되돌리지 않습니다.
따라서 한 대 시연에서 입출차를 한 A 실행이 관리한다는 조건이 필요하며 일반 다중 운영의 원자적 동일 이용 보장은 아닙니다.
다음은 실제 사용 구도/입출차 방향/실행 설정을 확인하고 준비 승인 후 한 번의 실제 흐름을 확인하는 순서입니다.
공용 DB 업무 시험이 보류된 동안 이 실제 성공을 주장하지 않습니다.


추가검증/사용자제한: 사용자가공용DB업무데이터를건드리지말고실제행수정·롤백시험을보류하라고답했습니다.
이허용범위를유지하며업무행UPDATE/INSERT/DELETE·SELECT FOR UPDATE 실행·자동해제활성화를하지않습니다.
실제매퍼lockLinkVersion/releaseAiSpace의SQL은Oracle21c DBMS_SQL.PARSE만호출해유효성을확인했습니다.
DBMS_SQL.EXECUTE는호출하지않았고파싱커서는닫았습니다. 읽기전용트랜잭션종료의rollback은업무행수정시험이아닙니다.
컬럼18/0/NOTNULL/DEFAULT0,제약ENABLED/VALIDATED,트리거VALID/ENABLED,컴파일오류0을재확인했습니다.
진단코드의임시바인드명number가예약어여서ORA-01745가났으나,순번바인드로바꾼최종파싱은두쿼리모두통과했습니다.
실제MyBatis는위임시바인드명을사용하지않으므로이오류는운영매퍼오류가아니며운영코드수정은없습니다.
근거results/link_version_deployment_20261023/mapper_parse_verification.txt.
트리거실제버전증가·제약거절·업무해제/재연결·Oracle롤백동작은여전히미검증입니다.
다음은공용DB업무데이터시험이아닌허용된AI/코드작업을진행하며,AWS적용은별도대상확인·승인후진행합니다.


2026-10-23 DB 적용 완료: 사용자가 컬럼·제약조건·트리거 추가를 명시적으로 요청했습니다.
대상은 기존192.168.0.39:1521:xe 개발DB이며 JDBC메타데이터로Oracle21임을 확인했습니다.
동명컬럼/제약/테이블트리거가 모두 없는 것을 재확인한 뒤 다음3개를 추가했습니다.
PARKING_USAGE.LINK_VERSION NUMBER(18,0) DEFAULT0 NOT NULL,
CK_PUSAGE_LINK_VERSION CHECK(LINK_VERSION>=0), TRG_PUSAGE_LINK_VERSION.
트리거는DECODE없는일반비교/NULL조건을 사용하며 INSERT0, 구획/예약/차량/출차 변경+1, 동일정보유지입니다.
실제메타데이터에서 컬럼18/0/NOTNULL/DEFAULT0, 제약ENABLED/VALIDATED,
트리거VALID/ENABLED와컴파일오류0을확인했습니다. AWSOracle11g에는적용하지않았습니다.
Boot parking-usage.xml의조회/해제조건2곳과기존AiSpaceReleaseTest를LINK_VERSION으로수정했고,
관리자주차검사72개재실행통과입니다. SQL초안도LINK_VERSION/CK_PUSAGE/TRG_PUSAGE이름으로일치시켰습니다.
Java프로퍼티linkVersion과API link_version/linkVersion 계약은변경하지않았습니다.
DDL은커밋됐습니다. 별도입차/예약/구획업무DML이나유효AI POST는수행하지않았습니다.
실제트리거버전증가·해제·재연결·동시잠금·롤백업무시험은아직미검증입니다.
자동해제기본false는그대로이며사용자승인없이활성화하지않습니다. Boot실행중리소스반영여부는확인하지않았습니다.
이번변경Boot파일은resources/mapper/parking-usage.xml,
src/test/java/kr/co/alpharking/service/parking/AiSpaceReleaseTest.java와docs/sql/parking-usage-link-version.sql입니다.
화재·카메라·프런트·스테이징·커밋·푸시는변경하지않았습니다.
이하DB미적용/AI_LINK_VERSION기록은이번적용이전기록이며최신상태는이문단을따릅니다.


최신 실행기 통합 검증: 해제 응답을 제어된 Future로 지연시킨 상태에서
A-02 후보 유지→해제 성공 뒤1회 전송, 관찰 소실→대기 후보 폐기·미전송,
소실 후 복귀→새 LOCAL_SPACE_MATCH만 재연결하는3경로를 기존 실행기 검사에 통합했습니다.
버전없는 MATCH 성공 응답에서 실행기가 APPLIED를 보존하고 DELIVERY_STOPPED로 끝나며
해제 요청0회/현재 연결표시 비움도 확인했습니다. 운영 코드 추가 수정은 불필요했습니다.
이전 버전 준비 차단 수정에 대한 실행기 수준 검사까지 묶어 Python기존검사1개를 수정했고 전체822개 통과입니다.
실제 로컬Boot 입출차/구획연결/해제3경로에 API키없는 빈 요청을 보내 모두401차단을 확인했습니다.
유효 업무 이벤트·자격증명을 보내지 않았고 DAO반영·DB변경 검증은 아닙니다.
카메라·공용DB·Boot·화재·스테이징 변경 없음. 실제 정상 예약 연결/해제/재연결은 여전히 미검증입니다.


최신 구현 후속: 자동 해제 활성화 시 MATCH 성공 응답의 연결 버전이 없거나 증가 불가능하면
기존에는 해제/재연결이 진행되지 않은 채 대기했습니다. SpaceMatchDeliveryFlow에서 이를 검출해
APPLIED/UNCHANGED 반영 기록은 유지하고 blocking_reason=SPACE_RELEASE_VERSION_UNAVAILABLE와 함께
후속 전송을 중단하도록 수정했습니다. 다른 차량 요청·해제·재연결·자동 재시도를 차단합니다.
버전은 검증된 이용 ID와 함께0이상/10^18-1미만이어야 합니다. 최대18자리 값에서는 다음 버전 저장이 불가능합니다.
자동 해제 비활성인 기존 MATCH 동작은 버전 누락을 허용해 호환성을 유지합니다.
보고서 검사도 성공 반영을 불명확으로 바꾸지 않고 별도 중단 이유·검토 필요·재전송 금지를 표시합니다.
기존 검사 파일3개에 회귀4개(상태/버전8조건 포함)를 통합했고 AI전체818개 통과입니다.
Python5개: vehicle_delivery_flow.py, inspect_parking_camera.py,
test_vehicle_delivery_flow.py, test_vehicle_http.py, test_parking_delivery_worker.py.
공용DB·Boot·화재·카메라·스테이징 변경 없음. 로컬 임시HTTP만 사용했으며 실제DB 생애주기 검증은 아닙니다.


최신 환경 확인(2026-10-23): 사용자가192.168.0.39를 팀장님 공용 DB라고 확인했습니다.
권한 있는 실행 환경의 TCP 확인에서 Oracle1521/로컬관리자81/사용자80 연결이 모두 성공했습니다.
HTTP GET은 관리자/사용자 모두403으로 응답했습니다. HTTP 서비스 응답만 확인했으며 AI 인증/API 성공 확인은 아닙니다.
SQLPlus JDBC주소 전달 오류(ORA-12545)와 로컬Windows 인증 오류(ORA-12638)는 DB 장애로 해석하지 않습니다.
기존Gradle캐시 JDBC드라이버로 실제 접속 후 SET TRANSACTION READ ONLY로 메타데이터SELECT만 실행하고 rollback/종료했습니다.
접속 계정의 USER_TABLES에 PARKING_USAGE/PARKING_SPACE/PARKING_RESERVATION이 있었습니다.
PARKING_USAGE.AI_LINK_VERSION은0행, 해당 테이블 USER_TRIGGERS도0행입니다. 대상 트리거 USER_ERRORS도0행입니다.
컬럼/트리거가 없으므로 오류0행은 트리거 유효성 증명이 아닙니다. 다른 계정/스키마 전체를 조회한 것은 아닙니다.
현재 DB에서 버전 기반 자동 해제·재연결을 활성화하지 않습니다. 기존 기본 비활성을 유지합니다.
필요 변경 초안: PARKING_USAGE에 AI_LINK_VERSION NUMBER(18,0) DEFAULT0 NOT NULL,
음수 방지 제약조건, 구획/예약/차량/출차 변경 시 버전 증가 트리거입니다.
초안 apcms_a/docs/sql/parking-usage-link-version.sql은 실행하지 않았습니다.
공용 DB에서 DDL·시험 입차/예약/점유 변경·AI POST를 수행하지 않았습니다. Boot파일/설정도 변경하지 않았습니다.
다음은 격리된 시험 스키마를 우선 확보하고, 사용할 DB·변경 범위에 대한 명시적 승인 후 Oracle 검증을 진행합니다.
이번 추가 점검은 문서2개만 정정했으며 카메라·새 모델·새 설치·스테이징은 사용하지 않았습니다.


최신 우선순위 재점검: 종이 OCR 전처리 반복은 중단하고 핵심 생애주기 계약→실제 서버/DB 검증 준비를 우선합니다.
실시간 인식 실패는 미해결로 명시하되 전체 개발을 그 시험만 기다리게 하지 않습니다.
관리자72개·사용자19개 모의 검사를 재실행해 통과했습니다. 실제 DAO/Oracle 검증과는 구분합니다.
기존 test_vehicle_http.py에127.0.0.1 임시 서버 왕복2개를 통합했습니다.
실제 HTTP 클라이언트→비동기 전송→Boot 형식 응답 판정의 연결/해제/다른 구획 재연결,
잘못된 해제 버전의 전역 차단·재시도 없음까지 검사했고 AI 전체814개 통과입니다.
실제 Boot·DB에는 요청하지 않았으며 기본 HTTP 비활성·해제 비활성을 유지했습니다.
VEHICLE_INTEGRATION.md 상단의 과거 미구현 표·중복 우선순위를 현재 코드 기준 표와 DB 시험 조건으로 통합했습니다.
실제 설정 포트는 관리자81/사용자80입니다. 제한 환경의 리스너 조회만으로 서버 미실행을 판단한 과거 결과는 정정합니다.
팀장님 공용 DB의 읽기 전용 메타데이터 조회는 완료했습니다. 다음은 별도 시험 스키마 또는 공용 DB 변경 범위 협의·승인 후 실제 통합 검증입니다.
AI_LINK_VERSION DDL·트리거는 여전히 초안이며 실행하지 않았습니다. Boot·화재·DB·스테이징 변경 없음.
이 아래의 카메라 우선순위·이전 검사 수는 당시 단계 기록이며 현재 우선순위는 이 최신 문단을 따릅니다.


2026-10-23 현재: 사용자 승인으로 관리자 예약 판정·구획 연결, 관리자 보정 정합성,
사용자 예약 생성·취소의 잠금 처리를 구현했습니다. 관리자 주차 검사는 72개, 사용자 신규 검사는 19개 통과했습니다.
AI 구획 전용 요청 검증·HTTP 클라이언트·응답 판정도 기존 모듈에 통합했고 이번 AI 전체 검사는 844개 통과입니다.

- 관리자 AI는 구획 → 이용 → 예약 순서로 잠그고 유효 예약 한 건만 구획·예약 ID와 함께 연결합니다.
- 관리자 해제는 구획·예약 ID를 함께 비우며 이전 예약은 보정 이력에 남깁니다. 같은 구획 유지·출차는 이력으로 보존합니다.
- 사용자 생성은 같은 PARKING_SPACE 행 잠금 후 중복을 재검사합니다. 취소는 구획 → 예약 잠금 후 엔티티를 refresh합니다.
- 미출차 이용에 연결된 예약 취소는 보류하며, 취소 상태·이력 저장 형식은 유지합니다.
- 실제 Oracle 실행·잠금 경쟁·롤백은 미검증입니다. 모의 DAO/EntityManager 검사 통과를 실DB 검증으로 표현하지 않습니다.
- 기존 VehicleServiceTest는 실제 DB 의존이라 실행하지 않았습니다. 실제 서버·DB 연동은 검증하지 않았습니다. 실제 카메라 후속 결과는 아래 실행 기록과 구분합니다.
- 다른 채팅의 화재 코드·설정 변경은 보존합니다. SecurityConfig.java는 승인받은 해제 POST 경로 한 줄만 추가했습니다.

실시간 로컬 연결 → 요청 후보 → 비동기 단발 전송·응답 기록을 기존 카메라 실행기에 연결했습니다.
HTTP는 기본 비활성입니다. 실제 연결 전송은 점유 전송·허용 구획·카메라 ID와 별도 활성화가 필요합니다.
이동·소실 시 미전송 후보를 버리고, 시작한 요청은 회수합니다. 같은 번호판은 버전 검증된 해제 성공 후에만 재연결합니다.
연결 응답·불명확 상태는 기존 보고서 검사에서 함께 확인합니다. 상세는 VEHICLE_INTEGRATION.md에 통합했습니다.
승인 후 전용 해제 API·연결 버전·비동기 해제→재연결을 구현했습니다. SecurityConfig의 해제 POST 경로 한 줄도 별도 승인받았습니다.
Boot 해제 기본 속성은 parking.ai.space-release-enabled=false이며 AI도 --enable-space-release-http를 명시해야 합니다.
SQL 초안은 apcms_a/docs/sql/parking-usage-link-version.sql에 두었고 실제 실행하지 않았습니다.
기본 비활성 상태에서는 새 컬럼을 조회하지 않아 SQL 적용 전 기존 DB 기능을 유지합니다.
추적·OCR 프로세스 분리 후 20초 재확인에서 1초 초과 수집 공백이 없었습니다. 다음은 간헐 철회 원인 구분·이동/가림/복귀, 그 뒤 시험 DB 연동입니다.
실제 DB 변경은 별도 승인 대상이며 같은 종이 촬영을 반복 요구하지 않습니다.
실제 DB 통합 검증과 실제 입력 차량 탐지 실패도 남아 있습니다. 이번 자동 검사로 해결됐다고 표현하지 않습니다.

### 카메라 없는 철회 원인 구분 작업 (2026-10-23)

연결 철회 이벤트에 reason·근거를 추가했습니다. 관찰 누락은 실제 가림/출차로 단정하지 않으며,
관찰 공백·위치 이동·구획 변경·구획 밖·점유 근거 단절·복수 추적·번호판 충돌·중복 번호를 구분합니다.
관찰 공백에는 실제 경과/허용 간격, 위치 변화에는 이동량/경과 시간/정규화 속도 등을 남깁니다.
번호판 충돌로 기존 연결을 비울 때 MATCH_REVIEW 기록이 빠진 경로도 보완했습니다. 연결 판정 임계값은 유지합니다.
보고서 검사와 저장 영상 요약은 같은 철회 원인 집계를 사용합니다. 실제 DB 반영 확인 상태와는 구분합니다.
과거 reason 없는 이벤트는 UNKNOWN_LEGACY로 집계하며 원인을 역으로 꾸며 넣지 않습니다.
기존 실제 보고서 5개를 읽어 원인 미기록을 확인했으며 당시 간헐 철회의 정확한 원인은 여전히 미확정입니다.
원인별 검사·저장 영상·보고서 호환을 기존 검사 파일에 통합했고 전체 AI 800개가 통과했습니다.

변경 Python 5개: parking/vehicle_space_tracker.py, inspect_parking_camera.py, run_vehicle_space_tracking.py,
tests/recognition/test_vehicle_space_tracker.py, test_parking_delivery_worker.py.
원인 기록뿐 아니라 번호판 충돌 시 철회 이벤트 누락 수정·저장 영상 요약·과거 보고서 대조까지 묶어 수행했습니다.
이번에는 카메라·실제 모델·서버·DB를 사용하지 않았고 Boot·화재·스테이징·커밋·푸시도 변경하지 않았습니다.
다음 실제 확인은 시험 방식과 준비를 먼저 합의한 뒤 이동/가림/복귀 및 간헐 철회 원인을 구분합니다.
사용자가 준비되지 않았다면 카메라를 사용하지 않습니다.

### OCR 프로세스 분리 후속 (2026-10-23)

로컬 plate 추적의 auto OCR을 Windows spawn 작업자 1개로 분리했습니다. 차량 기본 모드·주입 인식기는 thread를 유지합니다.
`run_parking_camera --ocr-execution auto|thread|process`를 제공하며 기본 auto에서 plate 로컬 OCR만 process입니다.
모델 준비·빈 영상 워밍업은 카메라 측정 전에 끝냅니다. 빈 영상은 차량 관찰·정차 근거로 사용하지 않습니다.
OCR 작업 한 건·crop 메모리 한도·원본 시각·동일 정차 세대 검사·종료 시 미적용 결과 폐기를 유지합니다.
작업자 오류는 실패로 전달하고 종료 시 작업자를 회수합니다. 기본 HTTP 비활성도 유지합니다.

실제 카메라 결과는 Git 제외 priority_review_20261023/a01_process 및 a01_process_repeat에 있습니다.
- 첫 20초: 371프레임, 추적 최대 0.084초, 수집 간격 최대 0.156초, 1초 초과 공백 0건.
  OCR 최대 3.289초여도 추적이 진행됐습니다. 중간 연결 철회·A-03 추가 점유 표시가 있었고 종료 연결은 없었습니다.
  실행 후 화면에서는 A-03이 비어 있었습니다. 해당 점유 표시의 정확한 원인은 미확정이며 개선됐다고 표현하지 않습니다.
- 다른 검사와 겹치지 않은 20초 재확인: 371프레임, 추적 최대 0.075초, 수집 간격 최대 0.110초,
  1초 초과 공백 0건, OCR 최대 2.866초. 종료 시 91소6408→A-01, A-01만 OCCUPIED·나머지 EMPTY.
  중간 MATCH_REVIEW 1회 후 재확정이 있어 연결이 전혀 끊기지 않는다고 주장하지 않습니다.
- Windows spawn 전달·한 건 제한·늦은 결과 폐기·작업자 실패·종료·실행 옵션 검사 7개를 기존 검사에 통합했습니다.
  전체 AI 792개 통과. 실제 프로세스 PID 8060/28924는 실행 종료 후 남아 있지 않음을 확인했습니다.

이번 변경 Python 4개: parking/vehicle_space_tracker.py, run_parking_camera.py,
tests/recognition/test_vehicle_space_tracker.py, test_parking_deployment.py.
구현·실패/종료 검사와 다음 실제 카메라 재확인을 묶어 진행했습니다. 저장 영상은 순차 로컬 분석이므로 실행 방식을 변경하지 않았습니다.
Boot·화재·DB·패키지 설치·서버 송신·Git 스테이징/커밋/푸시는 수행하지 않았습니다.
다음 우선순위는 공백 없이도 발생한 간헐 연결 철회 원인 구분 및 이동/가림/복귀 확인, 그 뒤 시험 DB 연동입니다.

### 실제 카메라 우선순위 실행 (2026-10-23)

사용자 준비 확인 후 카메라 1/MSMF 1280×1024의 현재 장면을 직접 확인했습니다.
처음에는 손과 A-03 차량 사진이 남아 있어 빈 기준으로 채택하지 않았고, 사용자가 완전히 치운 뒤 재확인했습니다.
현재 구도에 맞춘 빈 기준·좌표와 실행 결과는 Git 제외 results/parking_checks/priority_review_20261023/에 있습니다.

- empty_session: 실제 모델 12초, 164프레임, 4칸 EMPTY, OCR·연결·HTTP 0건, COMPLETED.
- a01_session: 사용자 A-01 배치 후 20초, 163프레임, A-01 OCCUPIED·나머지 EMPTY.
  실제 OCR 완료 15건 모두 91소6408, 1F-A01 요청 후보 1건(DISABLED), HTTP 0건.
  1초 초과 관찰 공백에서 연결을 철회해 종료 시 현재 연결 없음. 안정적 정지 시험 통과로 표현하지 않습니다.
- a01_profile: 같은 배치에서 실제 추적/OCR 처리 시간만 계측한 20초 실행, 135프레임.
  추적 호출 최대 2.204초, 다른 추적 호출 2.174초와 OCR 2.158초 지연이 인접한 구간에서 발생했습니다.
  실제 수집 간격은 2.203초·2.187초 공백이 있었고 연결 철회 후 새 근거로 재연결했습니다.
  종료 시 91소6408→A-01 연결이 남았지만 처리 지연은 해결되지 않았습니다.
  계측 설정은 OpenCV 1스레드·Torch 8스레드·논리 CPU 24개였습니다. 지연 원인을 CPU/GIL 중 하나로 단정하지 않습니다.

다음 우선순위는 추적과 OCR 동시 처리 지연 해소(별도 프로세스 격리 등 원인별 검증) → 실제 이동/가림/복귀 → 시험 DB 연동입니다.
허용 공백·정차 조건을 완화하지 않았고, 카메라 입력의 시각을 바꾸거나 추적 소실을 출차로 처리하지 않았습니다.
실제 서버 전송·DB 변경·화재/Boot 소스 수정·스테이징·커밋·푸시는 하지 않았습니다.

### 중간점검 결과 (2026-10-23)

실제 코드 대조와 실패 검사로 두 결함을 재현한 뒤 수정했습니다.
1. 저장 영상은 점유를 나중에 대조해 점유 전 OCR·체류 근거가 연결에 섞일 수 있었습니다.
   같은 프레임 점유를 먼저 계산하고 tracker.process의 eligible_spaces에 적용하도록 실시간과 통일했습니다.
   빈자리/미확정 때는 후보 자체를 만들지 않으며 점유 확정 뒤 새 체류·번호판 합의가 필요합니다.
   held_matches는 호환 필드로 유지하지만 차단된 근거를 연결 후보처럼 채우지 않습니다.
2. 구획 송신의 인증 실패·거절·처리 불명확 시 다른 번호판 요청은 계속될 수 있었습니다.
   전송 흐름을 중단 상태로 잠그고 카메라도 DELIVERY_STOPPED로 종료하도록 수정했습니다.
   이미 시작한 요청은 결과를 회수하고, 새 연결·해제 요청은 시작하지 않습니다.

이번 재검증: AI 전체 785개, 관리자 주차 72개, 사용자 예약 19개 통과.
STS DTO·서비스·컨트롤러 클래스 4개에도 Unresolved compilation 표식이 없었습니다.
이번 변경은 Python 운영 3개(run_vehicle_space_tracking.py, run_parking_camera.py, vehicle_delivery_flow.py),
기존 검사 3개(test_vehicle_space_tracker.py, test_vehicle_delivery_flow.py, test_parking_deployment.py)와 기존 문서입니다.
Boot 소스·DB·화재를 추가 수정하지 않았고 스테이징·커밋·푸시하지 않았습니다.

남은 검증은 별개입니다. 저장 사진 20장 위치 관찰·19장 문자 일치는 실시간 정차·이동 성공이 아닙니다.
번호판 위치 모드는 차체 전체가 구획 안에 있다는 보장이 아닙니다. 실제 구도에서 정차/이동/가림/복귀를 확인해야 합니다.
SQL은 미적용 초안이며 Oracle 컴파일·트리거·동시 실행·롤백·실제 예약/해제 연동은 미검증입니다.
기본 해제 비활성 상태를 유지하며 이 기록을 운영 완료·실DB 성공으로 해석하지 마세요.

### 번호판 위치 추적 후속 (2026-10-23)

`--tracking-target plate`를 기존 카메라·저장 영상 실행기에 함께 연결했습니다. 기본값 vehicle은 유지합니다.
기존 번호판 모델의 실제 추적 점수와 원본 crop OCR을 사용하고, 정차·번호판 합의·연속 점유·철회 조건은 유지합니다.
번호판 위치 기준 구획 연결이며 차체 전체의 구획 내 주차를 보장하지 않습니다.
원본 차량 사진 20장 모두 A-01 번호판 위치 관찰, OCR은 19장 91소6408·1장 916408(무효), 빈 장면 12장은 관찰 0건입니다.
사진 위치·문자 검증과 실시간/이동/DB 검증은 구분합니다. 상세는 VIDEO_ANALYSIS.md에 통합했습니다.
변경 Python 5개: parking/vehicle_space_tracker.py, run_parking_camera.py, run_vehicle_space_tracking.py,
tests/recognition/test_vehicle_space_tracker.py, test_parking_deployment.py.
실시간·저장 영상 통합과 SQL 적용 전후 조회 구간 보완을 함께 수행했습니다. SQL은 실행하지 않았습니다.
Boot 소스는 이번 후속에서 추가 수정하지 않았고 실제 카메라·서버 송신도 하지 않았습니다.
사용자는 STS 새로고침·Clean 후 컴파일 오류 해소와 Boot 재실행을 알렸습니다.
STS의 새 DTO·서비스·컨트롤러 클래스 4개에서 Unresolved compilation 표식이 사라진 것을 확인했습니다.
Gradle 성공을 STS 동기화·실제 서버 기동/연동 보장으로 표현하지 마세요. 외부 수정 후 F5·Clean이 필요할 수 있습니다.
다음 순서는 번호판 위치 옵션의 실제 카메라 정차·이동 흐름 확인과 승인된 시험 DB에서 SQL·해제/재연결 검증입니다.
실제 DB 적용은 별도 승인 대상입니다. 동일 사진을 반복 촬영하거나 종이 전용 도구를 추가하지 않습니다.

### 이번 해제·재연결 작업의 파일

- 관리자 기존 8개: `controller/parking/AiVehicleEventController.java`, `dao/parking/ParkingUsageDao.java`,
  `dto/parking/AiVehicleEventResponse.java`, `dto/parking/ParkingUsageRow.java`,
  `service/parking/AiVehicleEventService.java`, `service/parking/ParkingUsageService.java`,
  `security/jwt/SecurityConfig.java`, `src/main/resources/mapper/parking-usage.xml`.
  Java 경로의 공통 루트는 `apcms_a/src/main/java/kr/co/alpharking/`입니다.
- 관리자 신규 3개: `apcms_a/src/main/java/kr/co/alpharking/dto/parking/AiSpaceReleaseRequest.java`,
  `apcms_a/src/test/java/kr/co/alpharking/service/parking/AiSpaceReleaseTest.java`,
  `apcms_a/docs/sql/parking-usage-link-version.sql`(초안, 미실행).
- AI 운영 Python 7개: `recognition/vehicle_contract.py`, `vehicle_response.py`, `vehicle_http.py`, `vehicle_delivery_flow.py`,
  `parking/parking_processor.py`, `run_parking_camera.py`, `inspect_parking_camera.py`.
- 기존 AI 검사 6개: `test_vehicle_contract.py`, `test_vehicle_response.py`, `test_vehicle_http.py`,
  `test_vehicle_delivery_flow.py`, `test_parking_deployment.py`, `test_parking_delivery_worker.py`.
  모두 `apcms_ai/ai_vision/tests/recognition/` 아래이며 검사 등록 파일·새 Python 모듈은 추가하지 않았습니다.
- 기존 설명서 2개: `HANDOFF.md`, `VEHICLE_INTEGRATION.md`.
- 이번 작업에서 사용자 Boot 파일·ParkingSpaceService.java를 추가 수정하지 않았습니다.

### Git 준비 시 Boot 변경 목록 별도 안내

사용자가 Git 업로드 전에 수정한 Boot 파일을 AI 파일과 구분해 알려 달라고 요청했습니다.
현재 관련 Boot 대상은 아래이며, 실제 Git diff와 재대조한 뒤 안내합니다. 지금은 스테이징·커밋·푸시하지 않습니다.

- 관리자 실행 파일: `apcms_a/src/main/java/kr/co/alpharking/` 아래
  `dao/parking/ParkingUsageDao.java`, `dto/parking/ParkingUsageRow.java`,
  `service/parking/AiVehicleEventService.java`, `service/parking/ParkingUsageService.java`, `service/parking/ParkingSpaceService.java`,
  `controller/parking/AiVehicleEventController.java`, `dto/parking/AiVehicleEventResponse.java`, `dto/parking/AiSpaceReleaseRequest.java`(신규),
  `security/jwt/SecurityConfig.java`(해제 POST 경로 한 줄 추가).
- 관리자 매퍼: `apcms_a/src/main/resources/mapper/parking-usage.xml`.
- 관리자 테스트: `apcms_a/src/test/java/kr/co/alpharking/service/parking/` 아래
  `AiReservedSpaceAssignmentTest.java`, `AiVehicleReservationContractTest.java`, `ParkingSpaceReservationCorrectionTest.java`, `AiSpaceReleaseTest.java`(신규).
- DB SQL 초안(신규, 미실행): `apcms_a/docs/sql/parking-usage-link-version.sql`.
- 사용자 실행 파일: `apcms_u/src/main/java/kr/co/alpharking/` 아래
  `service/reservation/ReservationService.java`, `repository/reservation/ReservationRepository.java`.
- 사용자 테스트: `apcms_u/src/test/java/kr/co/alpharking/service/reservation/ReservationConcurrencyTest.java`.

2026-10-22 실제 카메라 후속: 카메라 1/MSMF의 1280×1024를 확인하고 사용자 제거 확인 후
빈 기준과 같은 구획 설정을 `results/parking_checks/live_20261022_174709/`에 보존했습니다.
빈 장면 첫 15초 실행은 초반 일시 점유 후 EMPTY로 복귀해 원인 미확정입니다. 초당 원본을 보존한
12초 재확인에서는 4칸 EMPTY·차량 연결 없음, 오류 없이 종료했습니다.
사용자 A-01 배치 후 실제 20초 실행은 A-01 OCCUPIED·나머지 EMPTY였지만 차량/OCR 작업 0건으로 연결 실패했습니다.
0/10/19초 저장 원본에서 현재 yolo11n은 차량을 못 찾고 일부는 종이 전체를 microwave로 오인했습니다.
배치·정차 시간 부족으로 설명하거나 동일 재촬영을 요구하지 마세요. 다음 수정 대상은 실제 구획 장면의 차량 탐지입니다.
사진 제거 전 구획 밖 프레임은 실제 차량과 91소6408 인식 성공, 구획 후보 없음이었습니다.
전체 흐름 성공이나 실제 차량 주차 성공으로 해석하지 않습니다. 모델·운영 코드·Boot·화재 변경은 없었습니다.

차량 추적 → 번호판 합의 → 정차·연속 점유 → 로컬 구획 연결을 기존 카메라 실행기에 통합했습니다.
이동·짧은 가림·소실·점유 근거 단절에는 연결·번호판 근거를 철회하며, 재등장 시 새 근거가 필요합니다.
과거 비동기 OCR은 새 정차 구간에 사용하지 않습니다. 소실은 출차·EMPTY 판정이 아닙니다.
최신 프레임 한 장만 유지하고 OCR 한 건을 비동기 처리하며 점유·추적은 같은 수집 시각을 사용합니다.
화면에 차량·ID·번호판·구획·진행 상태를 표시하고 종료 시 현재 연결·관찰 표시를 비웁니다.

1. 구현한 해제·재연결의 SQL 초안·배포 조건 검토와 실제 Oracle 검증 준비. 실제 DB 변경은 별도 승인.
2. 예약·이용·구획 연결과 해제를 실제 DB에서 통합 검증할 환경 준비.
3. 보존한 실제 입력의 차량 탐지 실패 수정 후 전체 흐름 확인. 반복 촬영은 우선하지 않습니다.

내부 방어 검사나 모델 비교를 계속 늘리는 것이 다음 목표가 아닙니다.
최신 전체 자동 검사 기록은 792개 통과입니다. 카메라·탐지·OCR 입력을 제어한 통합 시나리오이며
실제 카메라 인식 성공·처리 속도·장시간 안정성을 보장하지 않습니다. 이동·소실·느린 전송·저장 실패·재시작 보고서 사례를 기존 검사 파일에 통합했습니다.

## 설명서와 검사 위치

- [시작 안내](../readme.md): 전체 기능과 설명서 연결.
- [영상 분석](VIDEO_ANALYSIS.md): 촬영·실시간 화면·실행 명령·실제 실패 자료와 모델 비교 기록.
- [입출차 연동](VEHICLE_INTEGRATION.md): Boot 계약·예약/구획 해제 변경안·조회 사본 대조.
- [결과 검토](RESULTS_REVIEW.md): 결과 API·CSV·정답 검토.
- `tests/recognition/test_vehicle_space_tracker.py`: 구획 상태·비동기 관찰·Boot 사본·저장 영상 실행기 통합 검사.
- `tests/recognition/test_parking_deployment.py`: 점유·카메라·화면·촬영과 전체 이동 흐름 검사.

시험 이력과 실행법을 이 문서에 반복 추가하지 말고 해당 설명서에 통합하세요.

## 실제 입력의 남은 문제

휴대폰 시험 실패 이후 종이 사진으로 전환했습니다. 두 시험을 혼동하지 마세요.
휴대폰 20초·30초 영상은 확정 번호·구획 연결이 없었습니다. 차량 ID 변경과 휴대폰 전체 오탐이 있습니다.
종이 원본 3장은 현재 전체 경로에서 차량 미탐지, 구획별 직접 OCR은 ± 오독이 남았습니다.
후보 모델도 안정성이 부족해 운영 모델은 유지했습니다. 단일 성공을 문제 해결로 표현하지 마세요.
종이 전용 구현 2개·검사 2개는 제거했으며 보조 OCR을 공통 인식기에 옮기지 않았습니다.
같은 방식의 반복 촬영이나 종이 전용 도구 확대를 요구하지 않습니다.
자료는 Git 제외 `results/space_recordings`, `results/space_analysis_*`,
`results/paper_stationary_20261022_152443_011374`, `results/vehicle_model_comparison_20261022`에 있습니다.

기존 빈 기준 사진은 640×480, 최근 종이 원본·좌표는 1280×1024이며 해당 폴더에는 빈 기준이 없습니다.
서로 다른 구도의 사진을 확대해 맞추거나 차량이 있는 사진을 빈 기준으로 사용하지 마세요.
준비 화면 R은 기준 사진 겹침 확인, `capture_empty_reference --config`는 구획선·해상도에 맞춘 촬영입니다.
빈 장면은 사용자가 확인합니다. 자동 구도 보정이나 차량 미탐지 시 강제 시작 제한을 추가하지 마세요.

## 작업 규칙

- 한국어 존댓말. 실제 코드·Git과 문서를 대조하고 과거 검증·이번 결과를 구분합니다.
- `1`: 핵심 우선순위 점검 후 실행. Python 변경이 5개 이하이면 연결되는 다음 작업까지 묶어 보고합니다.
- `2`: PR 준비와 관련 AI 스테이징. `3`: PR 준비 후 다음 작업.
- 현재 요청은 문서·테스트 통합 및 PR 준비·스테이징까지 허용합니다.
- 커밋·푸시·브랜치 변경·풀·병합은 사용자가 직접 합니다. stash를 임의 적용·삭제하지 않습니다.
- PR 본문에는 검증 절이나 'sender와 Boot 코드는 변경하지 않음'이라는 참고 문구를 넣지 않습니다.
- Python 파일 첫 줄은 절대 경로 주석, 새 주석은 간단한 한국어 설명을 사용합니다.
- 통합·삭제 전 참조와 검사 등록을 확인하고 검사 사례를 유지합니다.
- 화재는 다른 채팅 담당: safety/, tests/safety/, test_images/safety/ 및 모델을 수정·스테이징하지 않습니다.
- Boot는 변경 파일·방식을 먼저 설명하고 사용자 허락을 받은 범위만 수정합니다. 관리자 예약 연결·보정과 사용자 예약 생성/취소 보완은 각각 파일·범위 설명 후 허용됐습니다. 이동 해제 API·버전 SQL 초안과 SecurityConfig 경로 한 줄은 추가 승인됐습니다. 실제 DB 변경·프런트 등 새 범위는 별도 허락이 필요합니다.
- 다른 담당의 application.properties 등 로컬 변경을 보존하고 `git add .`를 사용하지 않습니다.
- DB 쓰기·외부 이미지 업로드·새 패키지 설치를 임의로 확대하지 않습니다.
- AWS는 필요할 때 사용자에게 시작과 현재 IP를 요청하며 최종 배포 시험은 나중에 진행합니다.

## 환경·Git 확인

작업 루트는 `D:\finalProjectB\back`, Python 작업 폴더는 그 아래 `apcms_ai`입니다.
기존 `.venv312`의 Python 3.12.7을 유지합니다. 가상환경·저장소를 재생성하지 마세요.
작성 시 브랜치는 `feature/ai-vision`, HEAD는 `7ec6112fc`입니다. 실제 상태를 다시 확인하세요.
다른 담당의 화재·Boot 변경이 함께 있으므로 커밋 대상과 분리합니다.

```powershell
Set-Location D:\finalProjectB\back
git status --short
git diff --cached --stat
Set-Location apcms_ai
.\.venv312\Scripts\python.exe -X utf8 -m ai_vision.tests.run_checks
```

로컬 모델은 yolo11n.pt·license_plate_yolov8n.pt이며 OCR 캐시는 사용자 .paddlex에 있습니다.
YOLO_AUTOINSTALL=false와 PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True를 사용해 불필요한 자동 설치·조회에 주의합니다.
기존 pi-heif==1.4.0은 과거 자동 설치 이력이 있습니다. 임의 제거하지 마세요.
제한된 검사 환경의 임시 파일·하위 프로세스 실패는 인터프리터·권한을 확인하고 검사를 우회하지 않습니다.

### A-02 재추적 및 미세 흔들림 보완 (2026-10-23)

준비 승인 후 40초 이동 시험에서 A-01 번호판 91소6408을 연결했습니다. 이후 A-01 EMPTY,
A-02 OCCUPIED였으나 A-02 번호판 재추적은 잡히지 않았습니다. 가림·복귀 단계는 수행하지 못했습니다.
POSITION_MOVED 두 건은 각각 15ms/1.118픽셀, 31ms/1.414픽셀 변화였습니다.
별도 승인받은 A-02 한 장 촬영 후 카메라를 종료했습니다. 사진에서 번호판은 보였으며,
기존 모델의 전체 영상 탐지 점수는 입력 640에서 0.2501, 1280에서 0.8130이었습니다.

plate 모드 기본 입력을 1280으로 바꾸고 --tracking-imgsz 640/960/1280 선택을 두었습니다.
vehicle 기본은 640입니다. 탐지 신뢰도 .25와 기존 OCR 판정·재시도는 유지합니다.
plate 이동 속도는 최근 실제 관찰 약 0.1초의 변위를 평가하며, 속도 기준 .025는 유지합니다.
구획 변경·점유 소실·관찰 누락 시 즉시 철회와 이전 OCR 폐기는 그대로입니다.
실시간·저장 영상 실행기에 함께 적용했고 기존 검사 파일에 6개 회귀 검사를 통합했습니다.
전체 AI 806개 통과. 저장 사진 3장 실제 모델 추적: A-01 0.9108, A-02 0.8130, 빈자리 탐지 0개.
정지 사진을 모델 준비 후 반복 입력한 결과이며 실제 이동 재추적·장시간 성능 증명은 아닙니다.
새 1280 설정의 실제 A-01→A-02 재연결과 가림·복귀, 수집 간격은 미검증입니다.
다음 우선순위는 사용자 준비 확인 후 이 실제 연결 흐름 검증, 그 뒤 승인된 시험 DB 연동입니다.
이번 후속은 AI Python 4개와 기존 문서만 변경했고 Boot·화재·DB·스테이징은 변경하지 않았습니다.
근거는 Git 제외 priority_review_20261023/movement_review, a02_detection_review.json,
saved_size1280_review.json입니다. 추가 카메라 사용은 다시 준비 답변을 받아야 합니다.

### 1280 실제 이동 시험 결과 (2026-10-23)

사용자가 A-01 배치·손 치움·카메라 켜기를 명시한 뒤 60초 실행했습니다.
movement_1280_review/parking_camera_check.json은 COMPLETED, HTTP0, 작업자 종료 확인입니다.
A-01은 5.093초에 91소6408 연결, 25.156초 이동 시 철회, A-02는 26.125초부터 추적했습니다.
A-01 완료 OCR22개 중 최종91소6408 21개/916408 1개입니다. 별도 한 표본은 첫916408→재시도91소6408로 복구됐습니다.
A-02는 완료 OCR2개가 91소6408/91스6408로 갈려 28.515초 PLATE_CONFLICT가 됐습니다.
두 결과 모두 기존 형식 판정 KOREAN_VALID여서 재시도는 실행되지 않았습니다.
특수문자 문제가 아니며 소/스를 임의 치환하거나 A-01 번호를 그대로 복사해 확정하면 안 됩니다.
충돌 이후 현 구현은 해당 정차 세대의 OCR을 중단하므로 이후 안정화 여부는 관찰되지 않았습니다.
수집 최대간격0.312초, 1초초과0건, 추적최대0.271초, OCR최대3.463초입니다.
새 설정의 실제 A-02 재탐지는 확인했지만 동일 번호 재연결은 실패/보류이며 가림·복귀 시험도 수행하지 않았습니다.
다음 최우선은 형식상 유효한 한글 오독 및 충돌 후 회복 정책을 기존 OCR·합의 경로에서 검토하는 것입니다.
서버/DB 전송보다 이 핵심 연결 문제를 먼저 해결합니다. 재촬영은 별도 준비 확인을 받아야 합니다.

### 충돌 후 새 관찰 회복 구현 (2026-10-23)

plate 모드의 실시간·저장 영상 경로에서 충돌 뒤 OCR 관찰을 계속하도록 보완했습니다.
충돌 이전 표본은 회복에 쓰지 않습니다. 이후 최근5개 표본 모두 유효·같은 번호이며,
서로 다른 프레임/최소0.25초 간격/전체2초 이상일 때만 PLATE_RECOVERED와 로컬 연결을 허용합니다.
최신5개 안에 판독 실패·상이한 번호가 있으면 계속 보류합니다. 기존 번호를 복사하거나 소/스를 치환하지 않습니다.
차량 기본 모드의 기존 충돌 보류는 유지합니다. 중복 차량 번호 보류는 회복 대상으로 풀지 않습니다.
이동·구획 변경·점유 소실·관찰 누락에서는 기존 세대 근거를 폐기하고 늦은 OCR도 적용하지 않습니다.
기존 통합 검사에 회복·반복 충돌·실패·시간 부족·점유 소실 및 비동기 계속 실행 6개 검사를 추가했습니다.
전체812개 통과. Python3개(추적기/저장 영상 실행기/기존 검사 파일)를 수정했습니다.
카메라·Boot·DB·스테이징 변경 없음. 이번 검사는 모의 관찰이며 실제 A-02 회복 성공을 뜻하지 않습니다.
형식상 유효한 오독의 기존 1차/재시도 정책은 변경하지 않았습니다. 동일 오독이 반복될 위험은 남아 있습니다.
다음은 저장 자료로 OCR 한글 오독 개선을 검토한 뒤, 사용자 준비 확인 후 실제 재연결을 검증합니다.

### 저장 사진 OCR 전처리 비교 (2026-10-23)

카메라 없이 기존 A-02 a02_scene.png와 A-01 a01_frames/00.png를 실제 로컬 OCR로 비교했습니다.
A-02 실제 탐지 상자428,258,514,285에 여백0/2/4픽셀을 각각 적용했지만 최초/기존 재시도 모두91±6408 REVIEW였습니다.
A-01은 여백0/2/4 모두 최초91소6408이며 강제 재시도는916408 REVIEW로 악화됐습니다.
A-02를2배/4배 확대해 색상/흑백/이진화6가지로 추가 대조했습니다.
색상/흑백은91±6408, 이진화는9130001 또는911M081로 개선되지 않았습니다.
따라서 전역 강제 재시도·전처리 변경·문자 치환은 적용하지 않았습니다. 실제 효과 없는 후보를 기본값으로 넣지 않습니다.
기존 cleanup은 구분자 제거 후 온전한 형식일 때만 채택하므로 빠진 한글을 ±에서 추정하지 않는 동작이 맞습니다.
근거 saved_ocr_comparison.json / saved_ocr_preprocessing.json은 기존 Git 제외 결과 폴더에 저장했습니다.
주의: 이 A-02 사진은 앞선 한 장이며60초 이동 시험의 소/스 충돌 원본 프레임은 저장돼 있지 않습니다.
따라서 이번 비교는 당시 한글 오독의 정확한 원인이나 충돌 회복 성공을 증명하지 않습니다.
다음 최우선은 새 회복 코드의 실제 A-02 정지 재연결 검증이며, 준비 확인 후 짧게 실행합니다.
그때도 충돌하면 해당 실제 OCR 입력 근거를 확보해 비교해야 합니다. 반복 종이 준비나 무근거 모델 변경은 하지 않습니다.
이번에는 운영 코드·Boot·DB·Git 스테이징을 변경하지 않았습니다.

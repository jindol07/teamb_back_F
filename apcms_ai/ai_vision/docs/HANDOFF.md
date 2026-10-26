# AI Vision 작업 인수인계 — 2026-10-23

## 카메라 사용 규칙

최신 사용자 지시: 카메라를 켜면 준비 미리보기만 표시합니다. 각 창에서 SPACE를 눌러야 해당 시험을 시작합니다.
SPACE 전에는 인식·관찰 집계·HTTP 전송을 시작하지 않습니다. Q는 준비 중 취소, 시작 후 사진 저장·종료입니다.
두 카메라 전체 시험은 두 창의 SPACE 입력과 B 빈자리 검사 통과 후에만 DB 시험행을 준비하고 전송을 허용합니다.
과거 자동 시작 시험 스크립트는 당시 결과의 근거로만 보존하며 다음 시험에 그대로 재사용하지 않습니다.
준비 시간은 관찰 제한 시간에서 제외합니다. 현재 준비된 재시험은 이 수동 시작 방식이며 실카메라 재검증 전입니다.

사용자는 촬영 화면을 함께 보면서 배치합니다. 두 카메라는 독립된 미리보기 창으로 표시하고 자동으로 닫지 않습니다.
각 창에서 Q를 누르면 해당 카메라의 마지막 원본 프레임을 저장하고 그 카메라만 해제합니다.
다른 카메라는 유지하며, 촬영 종료 후 저장 사진을 먼저 확인하고 불필요한 재촬영을 요청하지 않습니다.

사용자 책상은 고정된 시험 환경이 아닙니다. 카메라를 쓰기 전에 목적·배치·움직임·예상 시간을 설명하고,
해당 시험 방식으로 준비됐다는 답변을 받은 뒤 시작합니다. 한 장의 구도 확인 촬영도 포함합니다.
이전 배치 확인이나 단순 `1` 요청만으로 현재 준비 상태를 가정하거나 카메라를 켜지 않습니다.
실제 시험 때마다 그 시점의 준비 상태를 확인하며, 준비를 기다리는 동안 카메라 없는 작업을 진행합니다.

## 현재 상태와 다음 순서

### 2026-10-26 기능 재점검 결론: 현재 한 대 시연의 필수 신규 기능 없음

사용자가 ‘기능을 더 만들 것이 없는지, 누락이 없는지 다시 점검하고 처음부터 만든 기능을 설명’하도록 요청했습니다. 인식/OCR재시도·합의, A 방향통과, B점유·정차, 한대신원전달, Boot예약검증·입출차·연결, 관리자판정저장·5초조회표시, 현재이용표시, 출차·재입차, 운영보호·검토도구·설치배포 경로를 현재 소스와 대조했습니다. 현재 합의한 차량1대/A+B카메라/예약자리 판정 시연의 필수 신규 구현 누락은 찾지 못했습니다. 기존 시험을 계속 확대하거나 새 기능을 임의로 추가하는 것을 다음 기본 작업으로 삼지 않습니다.

구분해야 할 미완료: 복수차량 카메라간Re-ID, 무기한 신원유지·재시작복원, 영속UUID중복처리·장애자동복구, 오주차 자동알림·제재업무, 정상연결 후 자리이동 자동해제(보류), B독립재인식 옵션의 실카메라 검증, 최종배포환경·AWS DB 적용범위/Boot·Redis·로그인 연동입니다. 이 중 최신팀코드 실제동기화/실행환경확인·배포인계는 마무리 작업이며 새 AI인식 기능 구현과 구분합니다. Kubernetes는 팀장님담당, AWS는 지금필요한검증이있을때만 요청합니다.

핵심 실검증은 이용92의 다른자리→예약자리(14조건), 이용94/95의 동일실행 두회차(13조건), 시험잔여0/기존이용4보존입니다. 최신 격리통합 결과 Vision955/관리자주차86/두Boot컴파일 통과를 유지합니다. 기능표의 과거 ‘연속재입차미검증’ 및 새ID계약 이전이라는 우선순위 문구를 현재 상태로 수정했습니다. 이번 점검에서는 운영 코드·서버·DB·Git 업로드를 변경하지 않았습니다.

### 2026-10-26 최신: 최신 develop과 격리된 소스 통합 검사 통과

origin/develop 076a897d1의 Git 추적 소스를 별도 results/integration_9cf62311/back에 추출하고 현재 AI 변경을 덮어 합친 뒤 검사했습니다. 현재 브랜치/인덱스/실행 서버를 바꾸거나 실제 병합하지 않았습니다. Vision 전체955개/36.279초, 관리자 주차86개(5개 검사 클래스), 관리자 Boot compileJava/compileTestJava, 사용자 Boot compileJava 모두 통과했습니다. Gradle은 기존 캐시만 사용하는 offline 모드였습니다. 검사 중 카메라/모델추론/실제HTTP/공용DB/Redis 연동은 하지 않았습니다.

첫 Vision 검사는 모의 YOLO 검사1개가 Git 제외 yolo11n.pt의 존재에 의존해 실패했습니다. test_deployment_runtime.py의 해당 검사에 임시 모형 파일을 만들고, 실제 파일이 없을 때 모델 로더/카메라를 호출하지 않는 검사도 추가했습니다. 운영 모델 파일 검증은 완화하지 않았으며 다운로드하거나 실제 가중치를 복사하지 않았습니다. 모델 없는 격리 복사본에서 전체955개가 통과했습니다. 당시 기존954개 통과는 로컬 모델이 이미 있는 환경 결과였으므로 새 기록과 구분합니다.

이번 누적 변경은20개(Python16/Java시험도구1/PowerShell1/문서2)입니다. 새 Boot 운영·프런트·화재 변경은 없습니다. 최신 팀 로그인 코드는 JWT_SECRET_BASE64와 Redis 실행 설정을 사용하므로 실제 동기화 후 서버 기동/로그인 검증은 별도로 남습니다. 비밀값은 읽어 출력하지 않았습니다. 결과 admin_parking_checks.log/user_compile.log/vision_checks_final.log 및 INTEGRATION_REPORT.md를 같은 격리 폴더에 보관합니다. PR은 보류, 스테이징/커밋/푸시/브랜치변경/서버재시작 없음.

### 2026-10-26 최신: 한글 안내 포함 동일 실행 두 차례 입출차 실제 성공

사용자 준비 확인 후 reentry/e2e_manual_357687c7을 실행했습니다. 원본 TEST_SUCCESS=True, 완료조건13개 전부 통과, incomplete_reasons 없음. ENTRY94→MATCHED94→EXIT94→ENTRY95→MATCHED95→EXIT95를 동일 A/B 프로세스에서 확인했습니다. 각 요청 expected_parking_usage_id와 검증된 응답 이용ID 일치, 서로 다른 이용94/95 사용, 실제DB LINKED_ROWS=2/OPEN_ROWS=0/총6건모두출차, B신원EMPTY·retained없음, 두프로세스 종료0/0입니다. A의 실제 방향 관찰은 DOWN/UP/DOWN/UP, HTTP4회입니다.

소유 시험17행 삭제·잔여0·기존 이용4건 보존을 확인했습니다. 한글 회차별 행동 안내가 포함된 실행이며, 이전 ‘두 회차 실제 검증 미수행’ 기록은 이 결과로 갱신합니다. 실제 재입차 시연 검증을 위해 같은 시험을 더 반복하거나 도구를 확대할 필요는 현재 없습니다. 기본 입차/예약 판정/구획 연결/출차와 잘못된 자리→예약자리 이동·재입차의 현재 한 대 시연 범위가 실제 확인됐습니다. 다중차량/Re-ID·일반 환경 정확도·무기한 복구·정상연결 후 자리이동 자동해제까지 완성됐다는 뜻은 아닙니다.

전체954개 회귀 통과 근거 유지, 이번 종료 후 운영 소스 변경 없음. 새 Boot/프런트/화재/DB구조 변경과 스테이징·커밋·푸시·PR생성 없음. PR은 사용자 지시대로 보류하며, 이후 필수 작업은 최신 팀 코드 동기화 시 통합 실행 확인과 변경 정리입니다. 카메라는 두 창 종료로 해제됐고 임시 매핑은 프로세스와 함께 소멸했습니다.

### 2026-10-26 최신: 재입차 시험의 회차별 행동 안내 보완

사용자는 2회차 안내가 없어 헷갈렸다고 지적했습니다. 기존 코드는 CYCLE 2/2 - 1 ENTRY 등 짧은 영문 한 줄만 표시했고 행동·방향·종료 여부를 명시하지 않았습니다. reentry/e2e_manual_1b84eeeb에서는 이용93의 첫 입차/MATCHED/출차만 확인되었고 두 번째 ENTRY는 없습니다. 최종 단계는 CYCLE 2/2 - 1 ENTRY, 원본 TEST_SUCCESS=False가 맞습니다. 소유 시험15행 정리·잔여0·기존 이용4건 보존, B신원EMPTY 및 두 프로세스 종료0/0 확인. 원인 전체를 사용자 동작으로 단정하지 않습니다.

두 미리보기에 같은 회차/현재 행동/종료 여부의 한글 안내판을 추가했습니다. 2회차 입차는 사진을 화면 밖으로 뺐다가 A 위쪽2초→아래쪽2초, 주차는 B A-01에서 대기, 출차는 아래쪽2초→위쪽2초를 표시합니다. 첫 출차 안내는 Q 금지·2회차 대기를 명시하고 최종DONE만 종료를 안내합니다. 준비 중에는 아직 시작하지 않은 창에서만 SPACE·두 화면 비우기를 안내합니다. 화면 폭 줄바꿈/한글 글꼴 없는 환경의 영문 대체/원본 보존을 적용했습니다. 같은 단계 안내판을 캐시해 매 프레임 글꼴 측정·렌더링을 반복하지 않습니다.

Python 5개: demo_session.py, parking_preview.py, gate_runner.py, parking_runner.py, 기존 test_parking_deployment.py. 공식954개/40.417초 통과(cycle_guidance_final_cached.log), 원본보존/회차별지시/글꼴대체/줄바꿈/캐시 검사 포함. 정지 이미지 second_entry/second_park/second_exit.png 생성 및 입차 안내 한글 표시 확인. 실카메라는 다시 켜지 않았으며 안내 보완 후 실제 두 회차 성공은 아직 남았습니다. 새 실제HTTP/공용DB 작업 및 Boot/화재/Git업로드 변경 없음.

### 2026-10-26 중간점검: 현재 시연 범위와 남은 검증

현재 파일·결과를 재확인했습니다. 실제 두 카메라 e2e_manual_090d1c21은 이용92의 입차→WRONG_SPACE/미연결→MATCHED→출차/B신원EMPTY, 완료14조건 통과, 시험18행 정리·잔여0·기존이용4보존입니다. 최신 회귀952개 통과이며 local/correction/reentry 전 영역의 미정리 매니페스트는0입니다. 같은 실행의 두 차례 입출차는 코드·모의 검사·별도 프로필 준비까지이며 실카메라/실제DB 검증은 아직 남았습니다. 카메라 화면 문구 별도 촬영, 다중차량 재식별, 다양한 실제차량 환경 정확도까지 검증한 것은 아닙니다.

Git 재확인: 백엔드 feature/ai-vision-demo-validation의 AI 변경18개(Python14/Java시험도구1/PS1/문서2), +1370/-82 기준입니다. 스테이징0, 미커밋 상태 유지. 최신 origin/develop 076a897d1을 다시 가져와 수정 파일 교집합0 확인. 실제 병합·최신 로그인/신고 코드와 결합 실행은 아직 안 했습니다. 프런트 develop은 작업 파일 변경 없이 최신 원격보다8커밋 뒤입니다. 별도 화재 미추적 파일1개는 수정·편입하지 않았습니다. 이번 변경의 Boot운영/프런트/화재/DB구조 변경0입니다.

우선순위: (1) 준비 확인 후 한 실행의 정상 입차→주차→출차를 두 회차 실제 확인하고 소유 시험 이용2건 정리 검증, (2) 최신 팀 코드 동기화 시 기존 Git 규칙에 따라 승인 범위 내에서 통합 실행 확인, (3) 문서·변경 범위 정리 후 사용자가 정한 시점에 PR 준비/진행. 추가 테스트 도구나 새 기능을 계속 늘리는 것을 기본 다음 작업으로 삼지 않습니다. 정상 연결 후 구획 이동 자동 해제는 보류하며 필요해질 때 다시 문의합니다. AWS는 즉시 필요한 검증이 있을 때만 요청하고 Kubernetes는 팀장님 담당으로 유지합니다.

### 2026-10-26 최신: PR 보류·같은 실행의 두 차례 입출차 검증 준비

사용자가 PR은 나중에 작업물이 더 쌓이면 진행하도록 지시했습니다. 자동 구획 이동 해제 확장은 계속 보류합니다. 현재 미검증인 동일 실행의 연속 재입차를 확인하기 위해 기존 시연 도구를 cycles=2 선택 실행으로 확장했습니다. 기본은 cycles=1이며 normal 시나리오에서만 2회를 허용합니다. 별도 Git 제외 프로필 results/parking_demo/reentry 사용, 기존 local/correction 프로필 설정은 그대로 유지했습니다.

각 회차는 ENTRY→동일 이용의 MATCHED→EXIT 순서여야 하며, 새 회차는 다른 이용 ID로 확인합니다. 첫 출차 후에는 B 신원 정리가 확인될 때까지 기다리고 CYCLE 2/2 안내를 표시합니다. 두 회차의 연결·출차·B 신원 해제와 DB의 시험 연결 2건을 모두 확인해야 DONE/최종 성공입니다. 미확정 응답·겹친 입차·이용 ID 재사용·다른 이용 출차·부분 완료는 성공으로 처리하지 않습니다.

정리 매니페스트는 cycles=2에서 검증된 usage_ids 목록만 기록하며, 단일 usage_id와 혼합하거나 중복/외부 ID를 포함하면 정리하지 않습니다. Java 시험 도구는 두 소유 이용을 개별 검증·삭제하고 외부 이용/예약 참조가 있으면 중단합니다. 기존 업무 행이나 DB 구조를 변경하는 기능이 아닙니다. 중단된 1회차의 소유 기록만 확정된 경우에도 확정된 ID만 정리하고 전체 성공은 거절합니다.

이번 묶음 Python 5개: demo_session.py, controller.py, 기존 검사 test_parking_deployment.py/test_live_gate_context.py/test_vehicle_delivery_flow.py. Java 시험 도구/PowerShell 안내/문서도 수정했습니다. 공식952개/42.125초, 관련229개, 실제controller+모의장치·DB 3경로, Java 소유ID 검사11개, 기존 제어기 모의10경로 및 normal/correction/reentry CheckOnly 모두 통과. 근거 repeat_trial_final.log/repeat_controller_b61563bf/result.json. 실제 카메라·HTTP·공용 DB는 이번에 사용하지 않았으므로 실제 두 차례 입출차 성공으로 표기하면 안 됩니다. 실제 시험 전에는 카메라 준비와 시험 이용2건 생성·정리 범위를 안내합니다. Boot 운영 소스/프런트/화재/스테이징/커밋/푸시/PR 생성 없음.

### 2026-10-26 최신: 최근 수정 포함 두 카메라 최종 시험 성공

사용자 준비 확인 후 correction/e2e_manual_090d1c21을 실행했습니다. 원본 http_e2e_result.json 자체가 TEST_SUCCESS=True이며 완료 조건 14개 전부 통과, incomplete_reasons 없음입니다. 이용92번 ENTRY → Z02 WRONG_SPACE/DB TEST_USAGE_UNLINKED=1·연결버전0 → Z01 MATCHED/같은 기대이용92·correction_of_event_id 일치 → EXIT92·OPEN_ROWS=0·연결버전2를 확인했습니다. B 신원 EMPTY/retained 없음, A/B 정상 종료0/0, 시험18행 정리·잔여0·기존 이용4건 보존입니다. 최초 이용91 시험과 달리 집계 후 재평가가 필요하지 않았습니다.

최근 현재 이용 표시 코드가 포함된 실제 실행의 정상 종료와 전송/DB 결과를 확인했습니다. 화면 문구를 별도 촬영·육안 검증한 증거와는 구분하며, 한 실행에서 두 차례 연속 재입차를 한 시험은 아닙니다. 연속 재입차 보완은 기존 모의 통합 검사 결과를 유지합니다. 임시 매핑은 두 자식 프로세스 종료로 소멸했고 기존 normal 프로필은 유지했습니다. 자동 구획 해제 확장은 보류, Boot 설정·DB 구조·화재·스테이징·커밋·푸시 변경 없음. 현재 코드 전체 회귀945개 통과 근거 유지. 다음은 사용자 요청에 따른 변경 정리/Git 반영 준비이며 새 기능 확장을 우선하지 않습니다.

### 2026-10-26 현재 우선순위 확정·누적 변경 호환성 점검

사용자는 정상 연결 후 구획 이동 자동 해제보다 현재 한 대 시연의 필수 작업을 먼저 진행하도록 지시했습니다. 이 확장은 보류이며 필요할 때 다시 설명·확인합니다. Boot 실행 옵션 space-release-enabled 활성화는 승인받지 않았고 변경하지 않았습니다. 기본 입차→예약 판정→연결→출차 흐름을 우선합니다. 아래 자동 해제 미완료 설명은 현재 필수 구현 지시가 아닙니다.

최신 origin/develop 076a897d1을 fetch 후 비교했습니다. 로그인·신고 원격 변경 21개 파일과 현재 AI 미커밋 18개 파일의 교집합 0, 공통 조상 기준 merge-tree 텍스트 충돌 없음. 실제 병합/체크아웃은 하지 않았습니다. 원격 관리자 SecurityConfig의 occupancy/vehicle/space-match/space-release AI 허용 경로 4개 유지 확인. 실행 결합 검증을 완료했다는 뜻은 아니며 원격 변경 후 재확인이 필요합니다. 로컬 HEAD 9959891a8, 브랜치 feature/ai-vision-demo-validation 유지.

누적 18개는 Python 14/Java 시험 도구 1/PowerShell 1/문서 2입니다. AST 14개 및 diff 형식 검사 통과. 운영 코드 추가 수정 없이 기존 성공 기록 재평가/실제 controller 모의 6경로+두 구획 모의 4경로/normal·correction CheckOnly를 다시 확인했습니다. 가장 최근 전체 회귀는 945개/38.592초 통과이며 이후 운영 소스 변경 없음. 두 구획 실제 시험 성공과 재입차·현재 이용 표시의 모의 검증을 구분합니다. 실제 연속 재입차·최신 표시의 카메라 확인은 아직 미검증입니다.

다음 순서: 현재 기능 검토·인계 정리 → 필요 시 최근 수정에 한정한 사용자 준비 확인 후 실검증 → 사용자가 요청할 때 Git 동기화·PR 진행. 문서/패치 백업은 Git 제외 결과 폴더의 기존 followup_delivery에 갱신합니다. 스테이징은 사용자 명시 요청 때만 하며 이번에는 스테이징/커밋/푸시/PR 생성하지 않았습니다. 별도 화재 미추적 파일은 열거나 변경하지 않았습니다.

### 2026-10-26 최신: 현재 이용에 맞는 주차 판정 표시

이전 표시 함수는 차량 번호/추적 ID/구획만 비교해, 같은 차량이 같은 구획에 재입차하면 이전 이용의 MATCHED를 표시할 수 있었습니다. B 관찰 progress에 현재 parking_usage_id를 포함하고 현재 관찰/기록/요청/응답의 이용 ID가 일치할 때만 판정합니다. 요청·응답 이벤트 ID/유형/상태/실제 요청 여부도 대조합니다. 현재 이용의 미전송 억제는 이전 실제 판정을 가리지 않으며, 현재 이용의 미확정 요청은 UNDETERMINED로 표시해 이전 성공으로 돌아가지 않습니다. 독립 OCR 경로의 이용 ID 없는 관찰은 유지하되 handoff 이용이 붙은 과거 기록을 재사용하지 않습니다.

Python 5개: run_parking_camera.py, vehicle_space_tracker.py, 기존 검사 test_parking_deployment.py/test_vehicle_space_tracker.py/test_vehicle_live_candidate.py. 공식 945개/38.592초 통과(current_decision_final.log), 변경 형식 검사 통과. 실제 저장 응답 3개와 모의 현재 관찰을 조합해 WRONG_SPACE 유지/MATCHED 표시/이전 이용 숨김/새 요청 대기 시 성공 숨김 4경로도 확인(current_decision_saved_records.json). 새 카메라 촬영·실제 HTTP·DB 작업은 하지 않았으며 실제 UI 재촬영 검증과 구분합니다. Boot/프런트/화재/스테이징/커밋/푸시 변경 없음.

### 2026-10-26 최신: 출차 후 다음 입차를 막는 잔여 상태 보완

최종 공식 회귀 944개/39.908초 통과(reentry_final_regression.log), 변경 형식 검사 통과.

두 구획 실시험 다음 우선순위로 반복 사용 경로를 점검했습니다. 마지막 실제 연결/보류 응답 뒤 HELD_RELEASE_REQUIRED 미전송 기록이 있으면 acknowledge_gate_exit가 그 기록만 보고 출차 억제 해제를 거절하는 문제를 수정했습니다. 미전송·응답 없음·차단 사유 없음인 억제만 건너뛰고, 동일 이용의 검증된 실제 응답을 확인합니다. WRONG_SPACE 등 검증된 미연결 보류도 같은 이용의 출차 확인 후 새 입차를 받을 수 있습니다. 미검증/다른 이용/전송 중/전송 불명확은 해제 근거가 아닙니다.

B가 EMPTY 파일을 읽기 전에 다음 ACTIVE가 저장된 경우도, 이전 보관 신원과 일치하는 last_exit, 출차 이후의 새 관찰 시각, 다른 이용 ID와 새 입차 이벤트 ID가 모두 있어야 신원을 전환합니다. 단순 신원 교체·이전 이용 재사용·시간 역전·다른 이용 출차·BLOCKED 전환은 계속 차단합니다. 무기한 복구나 다중 차량 기능을 추가한 것은 아닙니다.

Python 5개: vehicle_delivery_flow.py, single_vehicle_handoff.py, 기존 검사 test_vehicle_delivery_flow.py/test_live_gate_context.py/test_vehicle_space_tracker.py. 관련 173개 통과. 실제 writer→reader→B observer→전송 흐름을 모의 연결해 중간 EMPTY 미관찰, 미전송 억제 이후 출차, 새 이용의 새 정차 후 전송, 오래된 출차의 새 이용 해제 거절까지 검사했습니다. 실카메라/실제 HTTP/공용 DB는 사용하지 않았으며 반복 입차 실시험 성공으로 표기하지 않습니다. Boot/프런트/화재 및 스테이징·커밋·푸시 변경 없음.

### 2026-10-26 최신: 두 구획 실제 이동 확인 및 최종 집계 오류 수정

최종 공식 회귀 939개/40.825초 통과(two_space_receipt_final.log), git diff --check 통과. 화재 영역의 별도 미추적 파일은 열거나 수정하지 않았습니다.

사용자 준비 확인 후 correction/e2e_manual_70d47333 실행. 실제 입차/WRONG_SPACE/예약 구획 MATCHED/출차 모두 이용 91번입니다. Z02 판정 후 DB TEST_USAGE_UNLINKED=1, WRONG_SPACE_LINKED_ROWS=0, LINK_VERSION=0 확인 후 이동 안내. Z01 정상 연결 후 출차 OPEN_ROWS=0, LINK_VERSION=2, B 신원 EMPTY, 자식 종료 0/0 확인. 소유 시험 18행 삭제·잔여 0·기존 이용 4건 보존 확인. 테이블/컬럼 변경 없음.

최초 TEST_SUCCESS=False의 원인은 _parking_summary가 정상 HELD_RELEASE_REQUIRED 기록의 receipt=null을 손상으로 취급한 집계 오류입니다. 실제 기록은 WRONG_SPACE → 같은 자리 미전송 억제 → correction_of_event_id가 원래 요청과 같은 MATCHED였습니다. null을 허용하는 상태를 명시하고, 미완료/전송 불명확/비활성 요청은 최종 성공을 막는 space_requests_resolved 검사를 추가했습니다. 실제 전송 성공의 null 응답이나 잘못된 자료형은 계속 거절합니다. controller의 스냅샷은 엄격한 기존 JSON 읽기 함수를 사용합니다.

Python 5개 묶음: demo_session.py/controller.py와 기존 검사 test_parking_deployment.py/test_vehicle_delivery_flow.py/test_vehicle_live_candidate.py. 저장 자료만 재평가한 http_e2e_review.json에서 성공 조건 14개 전부 통과. 원본 http_e2e_result.json은 당시 실패 결과 그대로 보존하고 SHA256을 재검토 보고서에 기록했습니다. 재촬영·실제 DB 재호출 없이 재검토했으며, 실제 controller 모의 4경로와 CheckOnly도 다시 통과했습니다. 실제 기능 성공과 최초 보고서 집계 실패를 구분해야 합니다. 두 카메라 종료로 프로세스 전용 매핑은 소멸했고 기존 normal 프로필을 변경하지 않았습니다. 스테이징/커밋/푸시 없음.

### 2026-10-26 최신: 임시 두 구획 이동 시험 준비 완료

사용자가 두 구획 시험을 승인했고 매핑의 임시 적용·복원을 요구했습니다. 기존 normal 프로필은 유지하고 선택 scenario=wrong_space_correction을 추가했습니다. 별도 Git 제외 프로필 results/parking_demo/correction에서 A-02→999F-Z02(비예약), A-01→999F-Z01(예약)만 시험 프로세스에 매핑합니다. 종료 시 매핑을 복원하며 운영 구획 파일은 변경하지 않습니다. SPACE 전 DB 생성 없음, 두 창 시작·빈자리 검사 뒤 시험 층/구역/두 구획/예약 5행을 생성합니다.

순서: 입차 → 2A A-02 WRONG_SPACE → 같은 이용의 DB 미연결 확인 → 2B A-01 이동 → 이전 요청과 연결된 MATCHED → 출차 → DONE 후 5초 → 각 창 Q. DB 조회 실패·이미 연결·필수 단계 생략은 성공 처리하지 않습니다. 정리 도구는 두 구획의 소유·외부 참조를 검사하고 각각 이력/판정/구획을 삭제합니다. 기존 업무 행은 삭제 대상이 아닙니다. 테이블/컬럼/Boot 운영 소스 변경 없음.

이번 묶음 Python 5개: demo_session.py, controller.py, parking_runner.py, test_parking_deployment.py, test_vehicle_live_candidate.py. Java 시험 정리 도구와 PowerShell 안내, 문서도 수정했습니다. 공식 938개/40.500초 통과, 실제 controller를 모의 자식·DB로 실행한 4경로 통과(완료/조기 연결/미검증 응답/단계 생략), javac 및 별도 프로필 CheckOnly 통과. 근거 two_space_final_regression.log, two_space_controller_f25f4dd3/result.json. 실제 카메라/HTTP/공용 DB는 아직 사용하지 않았으며 실이동 성공을 뜻하지 않습니다. 다음은 사용자 배치 준비 확인 후 실제 1회 시험입니다. 스테이징/커밋/푸시 없음.

### 2026-10-26 최신: 신원·관찰 시각 검증까지 Python 5개 묶음 완료

이번 묶음은 vehicle_live_candidate.py, vehicle_delivery_flow.py와 기존 검사 test_vehicle_live_candidate.py, test_vehicle_delivery_flow.py, test_parking_deployment.py의 Python 5개입니다. 문서는 개수에 포함하지 않습니다. 후보 생성부터 expected_parking_usage_id를 요청에 포함하고 양의 Java Long 범위를 검사합니다. WRONG_SPACE 이후 다른 구획의 새 후보는 이전 요청보다 실제 관찰 시각이 나중이어야 하며, 같은 시각·과거 시각·시간대 표기만 다른 동일 시각은 차단합니다. 허용한 재판정의 로컬 기록에 correction_of_event_id로 원래 요청을 연결합니다.

전체 933개 검사 통과(40.736초), 근거 results/requirements_audit/correction_identity_time_final.log. 이번 검증은 모의 관찰·통신이며 실카메라/실제 HTTP/공용 DB를 사용하지 않았습니다. 이미 연결된 차량의 이동·재연결 기능은 미완료입니다. Boot·프런트·화재 변경 및 스테이징·커밋·푸시 없음. 다음 우선순위는 두 구획에서 다른 자리→예약 자리 재판정의 실제 통합 검증이며, 고정 A-01 시연을 그대로 재사용하지 않고 시험 구획과 DB 범위를 먼저 안내해야 합니다. 아래 이전 단계의 파일 수와 검사 수는 당시 기록입니다.

### 2026-10-26 다른 자리 보류 후 새 구획 판정 보완

사용자가 PR업로드는아직이르므로다음작업을요청했습니다. 핵심 이동경로 점검에서 서버WRONG_SPACE/HELD로DB미연결인차량도 _plates에남아올바른자리의새후보까지HELD_RELEASE_REQUIRED로막히는것을확인했습니다. 기존연결을해제해야하는경우와연결되지않은다른자리보류를구분하도록AI전송흐름을수정했습니다.

조건: 이전 실제전송의HELD/receipt_verified/request_attempted/parking_decision=WRONG_SPACE, 이전·현재·서버응답의동일입차ID, 다른space_code인새후보일때만새전송허용. 이미APPLIED/UNCHANGED인차량,같은자리반복,이용변경,예약없음/판정불가,미검증응답,통신불명확/차단은기존대로억제. 전송하지않은HELD_RELEASE_REQUIRED기록은최근실제응답을가리지않습니다. 새UUID/새관찰후보의다른자리판정이며동일요청자동retry아닙니다. 실제서버가재검증하고AI가기존DB연결을임의해제하지않습니다.

기존전송검사에WRONG_SPACE→같은자리억제→다른자리MATCHED→성공후다른자리억제와ID/응답불일치조건을추가. 기존주차통합검사에실제후보변환/전송흐름/표시함수로WRONG_SPACE→이동중과거판정제거→새자리MATCHED까지연결검사. 해제클라이언트호출0확인. 기존hand-off와자동해제동시불가제한은유지하며이미연결된차량의구획이동기능완성이아닙니다.

수정5파일: vehicle_delivery_flow.py/기존test_vehicle_delivery_flow.py/기존test_parking_deployment.py/기존문서2. 새모듈없음. 최종공식931개/39.157초통과(wrong_space_correction_final.log). 중간930공식/통합63검사는최종통합검사추가전결과. 모의AI전송/표시시험이며새실카메라/실제HTTP/공용DB를사용하지않았습니다. 실제다른자리→올바른자리주행성공으로표기하지않습니다. Boot/프런트/화재/AWS변경없음/스테이징·커밋·푸시없음. 고정demo는A01단일시험구획만허용하므로이이동시험에그대로사용할수없으며실시험은구획2개준비·허용목록범위를안내후진행해야합니다.


### 2026-10-26 controller 묶음 모의 실행 검증 완료

단위함수검사 이후 실제 controller.py를 runpy로 실행하고 자식카메라 프로세스/DB java호출만 mock으로 대체해6경로를 확인했습니다. 준비취소/자식실패는 mock DB호출0, 손상journal은controller중단/정지flag/최종실패, 쓰는중journal은WAIT, 구획전송실패는STOP/소유검증후mock정리, 응답대기는WAIT를 확인했습니다. 저장된 실제정상시연 c1308f85도 현재 evaluate_success로 전체통과를 재확인했습니다. 원본성공보고서는수정하지않았습니다.

결과 results/requirements_audit/controller_failure_harness_fdb07d50/result.json. 6건PASS. 이 검증은 실제카메라/HTTP/DB가아닙니다. 손상/미완성/미확정입출차기록은 이용소유를추측할수없어정리보류이며, 실제DB에시험잔여를만든것이아닙니다. 시험코드는Git제외results의기존후속검증묶음에보관했습니다. 운영소스추가수정없이이전928검사결과유효. 이단계에서파일수를맞추기위한운영코드수정은하지않았습니다.

최신누적후속은10파일이며 PR초안/패치백업갱신. 스테이징/커밋/푸시/브랜치변경없음. 다음은추가기능확대보다후속Git반영준비입니다. 기존프런트6오류는담당전달범위로유지합니다.


### 2026-10-26 장애 처리 묶음 후속 완료(Python7개)

사용자가 파일5개미만에서끊지말고연관된다음작업을묶도록지시했습니다. 기존 실패STOP보완에 이어 Python7개를 함께 보완했습니다: demo_session/controller/gate_runner/parking_runner/vehicle_delivery_flow/기존test_parking_deployment/기존test_vehicle_delivery_flow. 파일수만 늘리는 새모듈은 만들지 않았습니다.

실제 변경: 실시간 journal은4MiB제한/엄격한중복키·비정상숫자·객체검증을사용하고 완결된손상줄을무시하지않습니다. 쓰는중마지막줄은None으로반환해 WAIT HTTP JOURNAL UPDATE이며완료근거를재사용하지않습니다. 새입출차/구획요청이응답대기면이전DONE대신WAIT를표시합니다. A/B 모두read_demo_phase를사용해정지flag우선,읽기실패/빈/깨진/과도한안내를WAIT로표시하고과거문구유지안함. controller는정지사유를기록하며신규최종조건session_not_aborted가성공을차단합니다. blocking_reason있는연결기록도성공근거에서제외합니다. 전송executor.submit자체실패시DELIVERY_UNKNOWN과blocked를설정해다음후보재전송을막습니다(연결/해제공통).

서버/카메라를실제로고장내지않고실행중기록·응답·저장안내·executor실패를모의했습니다. 오래된B스냅샷의시간기반TTL을새로추가한것은아닙니다. B읽기실패는정상주차근거없음으로진행하지않으며장치실패는기존STOP입니다. JSONL은미완성줄이있으면대기하고확정손상시controller실패/관찰중단·소유권확인정리경로로갑니다. 불명확한실제DB결과를추정삭제하지않습니다.

검증: 최종공식928개/39.083초통과(failure_chain_final_regression.log), Python7개AST/실제런처CheckOnly/diff--check통과. 기존6개모의사례가불명확출차응답에서3REMOVE를기대하던것은새WAIT동작으로수정했습니다. 기존정상시연DONE은유지검사통과. 앞선923검사는이번추가이전결과입니다. 카메라/실제HTTP/공용DB/AWS/Boot/프런트사용·변경없음. 스테이징/커밋/푸시없음. 현재누적후속은Python7+PS1+문서2=10파일이며기존원격피처반영과구분합니다.


### 2026-10-26 실패 상황의 화면 단계 보완

사용자가 추가 작업 후 PR 진행을 요청했고 실제 원격 피처 푸시는 사용자가 수행했다고 알렸습니다. 현재 feature/ai-vision-demo-validation의 미커밋 후속을 유지하며 커밋/푸시하지 않았습니다. 실패 처리 검토에서 demo_phase가 실패 응답을 건너뛰고 과거 성공만으로 DONE을 유지할 수 있는 안내 불일치를 확인했습니다.

이제 같은 인쇄 차량의 전송기록에서 DELIVERY_UNKNOWN/AUTH_REQUIRED/REJECTED가 있으면 STOP DELIVERY FAILED, B 보고서 FAILED/error_type이면 STOP B CAMERA FAILED, 구획 전달 실패/차단사유가 있으면 STOP SPACE DELIVERY FAILED로 중단합니다. 이전 MATCH/입출차 성공이 이를 가리지 않습니다. 입차 전 B실패도 1 ENTRY 안내보다 우선합니다. 자동 재시도나 DB 상태 추측은 추가하지 않았습니다. controller는 기존 STOP분기로 관찰 중단 요청을 생성하며 시험행 정리는 기존 소유권 검증을 유지합니다.

수정 demo_session.py/기존test_parking_deployment.py와 기존문서. 공식923개/40.988초 통과, 최종 실패검사순서 보완 후 DemoSessionRecoveryTests32개/0.482초 재검증. 근거 failure_phase_regression.log/failure_phase_final_targeted.log. 서버 지연 자체를 새로 재현한 실험이 아니라 응답실패·장치실패의 모의 보고/기록 검증입니다. 새 카메라/HTTP/DB/AWS/Boot/프런트 사용·변경 없음. diff검사정상/스테이징·커밋·푸시없음.


### 2026-10-26 최신 통합 실제 두 카메라 시연 성공

사용자 준비 승인 후 프로필 기본 실행(dshow/A1/B0/.venv312/SPACE 시작)으로 e2e_manual_c1308f85를 수행했습니다. http_e2e_result.json TEST_SUCCESS=True, match_contract_version=2, 완료조건9개 전부참/미완료없음. 입차·MATCH요청 expected_parking_usage_id·전송기록 기대ID·서버응답·출차 모두 이용90번. 실제 서버 판정 MATCHED/APPLIED/receipt_verified=true를 확인했습니다. B독립OCR꺼진 ENTRY_HANDOFF 한대시연입니다.

DB종료검사 OPEN_ROWS=0/동일이용연결확인/LINK_VERSION=2, B신원 EMPTY/retained없음, 두프로세스 종료코드0. 소유시험행11개정리/잔여0/기존이용4보존. 최신 ID계약/정상주차 완료조건을 적용한 실제전체시연 미검증이라는 이전기록은 이 결과로 갱신합니다. 웹 화면을 이번 회차 중 직접 확인한 것은 아니며 이전 웹표시7건 실검증과 구분합니다. 이번 회차판정 이력은 소유시험데이터 정리대상에 포함돼 종료후 남지 않습니다.

근거 results/parking_demo/local/e2e_manual_c1308f85/http_e2e_result.json. 카메라 재촬영·재시험을 이어서 요청하지 않습니다. DB스키마/기존업무기록/Boot/프런트/화재/AWS변경없음. 후속8파일은 미커밋 상태로 유지, 스테이징/커밋/푸시없음.


### 2026-10-26 통합 완료 스태시 삭제 / 실제 실행기 사전 차단 검증

사용자가 이미 적용한 스태시 삭제를 지시했습니다. 백업 manifest의 stash_sha와 stash@{0}의 b6c757ae7d1768ee7e2a0ce25dc7bd7376278779 일치를 재확인한 후 해당 항목만 drop했습니다. 현재 stash목록0개. 통합 작업8파일과 backup_132357는 그대로 유지합니다. 아래 스태시 보존 기록은 삭제 이전입니다. 스테이징/커밋/푸시/브랜치변경 없음.

다음 작업으로 실제 pwsh -File run_parking_demo.ps1 -CheckOnly를 분리된 임시 프로필에서8회 호출했습니다. 저장 dshow/명시적msmf우선/구형프로필msmf는 정상통과. invalid backend/같은 A-B 장치번호/손상 reference/해상도불일치/이전 미정리 fixture는 모두 비정상종료·PREFLIGHT_OK없음 확인. 실제 pwsh 프로세스의 종료코드/출력으로 확인했으며 카메라·HTTP·DB 경로는 호출하지 않았습니다. 기존 공식921검사 이후 운영 소스 변경 없음.

근거 results/requirements_audit/launcher_contract_e5a62e48/result.json(8건PASS) 및 각 실행로그. 임시 프로필의 pending 표식은 오류경로 검증용 파일이며 실제 DB시험행이 아닙니다. 원래 local 프로필과 기준사진/좌표는 변경하지 않았습니다. Boot/프런트/화재/AWS변경없음. 현장 시연 자체의 재검증은 별도 준비 필요. 현재 후속 기능은 통합·검증됐고 추가 기능 확대 전에 PR병합 상태/팀 작업을 확인합니다.


### 2026-10-26 사용자 승인 후 두 후속 작업 통합 완료

사용자가 충돌을 피하는 방식으로 통합을 승인했습니다. stash pop/apply 없이 검증된 임시 통합본의8파일을 실제 작업 파일에 반영했습니다. 반영 직전 원본은 results/requirements_audit/followup_integration/backup_132357에 보존했고 stash@{0} 원본도 유지했습니다. 이후 같은 stash를 다시 통째로 적용하면 중복되므로 별도 승인 없이 pop/apply하지 않습니다.

반영 내용: 프로필 backend 기본선택/CLI우선/runner연결/설정 결과기록/기준사진 읽기·해상도 사전검사 + MATCHED 및 요청·입차 이용ID 일치 완료판정/과거성공기록 보존. 중복 backend 검사는 더 포괄적인 기존검사로 통합했습니다. 문서의 과거 별도보관/미반영 기록보다 이 최신 상태를 우선합니다.

실제 작업 경로 공식921개/39.294초 전부통과. 근거 followup_integration/applied_regression.log. -CheckOnly의프로필기본dshow/A1/B0 및 명시적msmf선택 통과. diff--check/충돌표식없음, 프런트변경없음. 스태시삭제/브랜치변경/스테이징/커밋/푸시/PR추가반영없음. Boot/DB/카메라/AWS사용없음. PR#100/#83과 별개인 로컬 후속8파일입니다.


### 2026-10-26 AI 범위 후속: 정상 주차 완료 조건 강화

사용자가 팀원 영역의 기존 프런트 오류는 전달용으로 남기고 본인 범위 작업을 진행하도록 요청했습니다. 프런트/Boot 파일을 수정하지 않고 AI 시연 완료 판정을 새 주차 계약에 맞췄습니다. 이전 verified_demo_match는 APPLIED/UNCHANGED 및 응답 이용ID만 확인해 명시적 MATCHED나 요청 기대ID가 없어도 다음단계/DONE 근거로 인정할 수 있었습니다.

새 실행은 receipt.parking_decision=MATCHED, 요청 payload.expected_parking_usage_id와 전송기록 expected_parking_usage_id가 검증된 입차 이용ID와 같은 정수일 때만 연결 완료로 인정합니다. 누락/다른ID/bool/정상판정아님은 2 PARK에 머물고 최종 성공에서 제외합니다. controller와 새 최종보고에 match_contract_version=2/expected_plate_number를 기록하고 normal_parking_verified 완료 조건을 추가했습니다. 검사 실패가 소유 확인된 시험 기록 정리를 막지 않습니다.

과거 이미 정리된 성공보고서는 당시 계약으로 유지하며 새 기준의 성공으로 재해석하지 않습니다. 해당 경로는 DB를 호출하지 않는 검사를 포함합니다. 현재 local demo.local.json에는 이전 후속의 camera_backend=dshow가 남아 있으나 PR코드의 엄격한 필드 검사와 맞지 않아 사전검사 차단 조건이 있었습니다. 선택 필드로 검증해 호환되게 보완했습니다. 현 실행 런처는 여전히 명시적 -CameraBackend dshow를 사용합니다. 스태시에 보관된 자동 backend 선택/기준사진 검사 전체를 임의 복원한 것은 아닙니다.

중요 Git 상태: 기존 승인대기 후속8파일(이전919검사)은 사용자 로컬 stash@{0}('임시')에 보관돼 있음을 읽기 확인했습니다. 꺼내기/삭제/스테이징을 하지 않았습니다. 현재 새 작업은 PR커밋9b126a44f의 기존915검사를 기준으로3개 검사를 추가한918개이며40.374초 통과. 이전919개와 현재918개는 서로 다른 미커밋/스태시 작업 구성이므로 단순 감소로 해석하지 않습니다. 향후 stash 적용 시 demo_session/controller/기존검사/문서가 겹치므로 승인 없이 pop/apply하지 않고 선별 통합이 필요합니다.

검증: normal_parking_completion_regression.log 공식918통과. 저장된 실제HTTP7사례를 오프라인 adapter로 새 판정함수에 연결해 MATCHED/MATCHED_REPEAT만 수락, 이전ID/누락/다른자리/예약없음/연결후이전ID의5건 거부. 원본 직접HTTP 도우미의 receipt에는 request_attempted가 없어 저장된 HTTP200 근거로 transport표시를 연결했으며, 이 변환을 결과에 명시했습니다. 실제 새 카메라/HTTP/DB 시험은 아닙니다. 근거 normal_parking_completion_saved_receipts.json. -CameraBackend dshow -CheckOnly 통과. PR/스테이징/커밋/푸시/브랜치 변경 없음.
### 2026-10-26 PR 승인 대기 중 후속 작업

사용자가 back/front PR을 올린 후 승인 대기 중 할 수 있는 작업을 요청했습니다. GitHub 연결에서 back PR#100(feature/ai-vision), front PR#83(feature/parking-decision-ui)의 열린 요청을 확인하고 채팅에 연결했습니다. 이 PR들에 댓글/커밋/푸시/병합을 하지 않았습니다. 현재 back HEAD9b126a44f/front HEADb6ec733 이후의 로컬 미커밋 후속 작업입니다. 새로운 브랜치로 분리한 것은 아니므로 향후 커밋 전에 사용자의 브랜치 지시를 확인합니다. 프런트와 Boot는 변경하지 않았습니다.

선택한 우선순위는 재현성 보완입니다. 기존 성공 방식 dshow 옵션을 빠뜨리면 MSMF로 실행되던 경로를 보완했습니다. demo.local.json에 선택 camera_backend(msmf|dshow)를 허용하고 현재 로컬 프로필에는 dshow를 저장했습니다. 런처 기본은 profile이며 명시적 CLI선택 우선, 필드 없는 구형 프로필은 msmf 유지. 각 runner는 프로필을 기본값으로 사용하며 controller 최종 결과에 backend/A번호/B번호 기록. 장치번호가 재연결로 바뀌는 문제를 자동 해결한 것은 아닙니다.

같은 사전검사에서 reference 사진이 실제로 읽히고 spaces 좌표 해상도와 같은지 확인해 손상/크기불일치를 카메라·DB 실행 전에 거부합니다. 사진이 존재한다는 조건만으로 통과시키지 않습니다. 좌표와 실제 종이 구도가 맞는지까지 자동 판정하는 기능은 아닙니다. 새 테스트 파일은 만들지 않고 기존 test_parking_deployment.py를 보완했습니다.

실제 -CheckOnly: 현재 프로필 기본 dshow/A1/B0와 명시적 msmf 우선 선택 통과, 호출 후 기존 환경변수 복원 확인. Git 작업 후 도우미 소스의 수정시각이 바뀌어 기존 캐시만으로 -Prepare 재컴파일 후 검사했습니다. 이는 카메라/HTTP/DB 없는 준비 작업입니다. 원본 기준 사진·기존 구획 좌표는 유지했습니다.

공식 검사919개/41.028초 통과, 근거 results/requirements_audit/profile_preflight_regression.log. 문법/diff-check 정상. 이번 후속의 Python5개(demo_session,controller,gate_runner,parking_runner,기존검사)+PS1+기존문서2개=8파일입니다. 모델설치/실카메라/DB/AWS/Boot/프런트 수정 없음. 스테이징·커밋·푸시 없음.


### 2026-10-26 Git 업로드 전 검토 / PR 준비

사용자 다음 진행 승인 후 front/APCMS에서 feature/parking-decision-ui 브랜치를 생성·체크아웃했습니다. 기존 TSX2개 변경 유지/스테이징0/diff--check 통과. back은 feature/ai-vision 그대로입니다. 아래 프런트 develop/브랜치 미생성 기록은 생성 이전입니다. 커밋·푸시·PR 생성은 하지 않았습니다.

두 저장소 git ls-remote로 원격develop 해시를 읽어 확인했습니다. back HEAD/원격develop=513010a49, front HEAD/원격develop=3287771. 현재 새원격커밋과 겹침은 없으며 업로드 직전 다시 확인해야 합니다. fetch/merge/checkout/stage/commit/push/PR 생성은 하지 않았습니다. back feature/ai-vision 변경26개(신규4포함;Java12/Python11/PS1/문서2), front develop 변경2개(TSX)입니다. 프런트는 커밋 전에 피처브랜치가 필요하며 생성하지 않았습니다.

리뷰에서 공용 ObjectMapper의 INDENT_OUTPUT 설정이 유형 문자열검색과 어긋날 수 있음을 확인해 저장 writer만 compact형식으로 고정했습니다. 기존 검사 파일에 전역 pretty 설정 사례를 추가했고 Boot 주차86개/실패0으로 재검증했습니다. SQL·API계약·스키마는 바꾸지 않았으며 DB/카메라 재시험은 하지 않았습니다. 사용자 추가 PS1 주석 문구를 보존하고 끝공백만 제거, 양쪽 diff--check 통과. API키/로컬사진/시험결과는 Git제외 확인. 화재 변경 없음.

기존 전체TS6오류는 이번파일 변경전과 동일하고 이번파일 오류0이며 Vite/프런트계약25건 성공 근거를 PR에 명시합니다. 백엔드API 먼저/프런트 다음 적용하도록 두 저장소의 PR 초안을 results/requirements_audit/pr_preparation_20261026.md에 준비했습니다(Git제외). 자동 스테이징하지 않았습니다. 마지막 compact writer 변경은 실행중STS의 기존기본compact출력과 결과동일하며 전역pretty설정 보호를 추가한 것으로 다음 빌드/배포시 반영됩니다.


### 2026-10-26 관리자 웹 주차 판정 표시 완료

사용자가 Boot5개 운영 파일/프런트2개 변경안과 기존 이벤트 테이블 사용을 승인했습니다. 기존 AI_DETECTION_EVENT의 RAW_PAYLOAD에 event_type=PARKING_DECISION/decision 스냅샷을 저장합니다. 새 테이블·컬럼·트리거는 없습니다. 기록 저장은 기존 MATCH 트랜잭션에 참여하며 실패하면 연결도 롤백합니다. 등록되지 않은 구획은 저장하지 않습니다. 입출차 UUID 영속 중복 처리 기능으로 해석하지 않습니다.

운영 Boot: AiVehicleEventService.java/ParkingUsageController.java 변경, AiParkingDecisionService.java/AiParkingDecisionDao.java/AiParkingDecisionRow.java 신규. 관리자 JWT/ADMIN principal 확인 후 GET /api/parking/usages/ai-decisions로 최근 저장200건 조회. Oracle11g 호환 ROWNUM/DBMS_LOB.INSTR 사용, 화재 DAO·사건·알림·점유 상태 처리 변경 없음. 기존 CameraE2EFixture.java는 소유 시험 구획의 점유/판정 이벤트 정리만 허용하도록 보완했고 모르는 이벤트/알림/사건 참조는 계속 차단합니다.

프런트: front/APCMS/src/pages/admin/parking/parkingUsage/{ParkingUsageAdmin,parkingUsageApi}.tsx. 기존 화면 상단에 최근 AI 주차 판정 목록 추가, 차량·관찰 구획·네 판정·연결 처리·한국 시각 표시/5초 조회/갱신 실패 시 이전 결과 경고/빈 목록·초기실패 구분/좁은 화면 가로 스크롤. 과거 판정을 현재 점유/위반 확정으로 표시하지 않습니다. 적용 이전 판정은 소급 생성하지 않습니다.

검증: Boot 주차85개/실패0, AI공식915개/38.220초, 실제TS 모듈·React 서버렌더 검사25건 통과. npm run build는 기존 가입/사용자주차/예약 타입오류6건으로 실패. 변경전 HEAD의 두 파일을 메모리상으로 대체해 대조한 오류6건과 동일, 신규/변경파일 오류0. Vite build:deploy 통과. 기존6건을 이번 범위에서 무단 수정하지 않았습니다. 근거 web_decision_{boot,ai,front_build,front_vite}.log 및 web_decision_front_{types,contract}.json.

사용자 STS Clean/81 재시작 후 실제 HTTP7건/DB 저장·운영 DAO/서비스 조회7건 확인. 첫 회차 run_0fa227ff는 자동 정리까지 성공. 화면 확인 회차 results/requirements_audit/parking_decision_live_cases/run_b12c5139는 사용자 직접 로그인한 앱 브라우저에서 관리자 웹의7행·정상/다른자리/예약없음/판정불가·연결상태 표시를 직접 확인했습니다. 실제 DOM텍스트와 admin_decisions.png 저장. 확인 후 정리, 최종 잔여0/기존이용4 보존, 웹 빈목록 재확인. 카메라 사용 없음. 운영 코드를 넣기 전의 웹미연결/새HTTP미검증 표기는 이 결과로 갱신됩니다.

서로 다른 두 Git 저장소(back/front)에 미커밋 작업이 있습니다. 자동 스테이징/커밋/푸시 없음. 작업 중 run_parking_demo.ps1 첫줄에 외부 추가 주석이 생긴 것을 확인했고 보존했습니다(끝공백1곳 diff-check 경고). 프런트 전체 빌드 때 생성된 vite.config.js/.d.ts 변경은 원래 내용/줄바꿈으로 복원했습니다. 다음은 추가 기능 확장보다 변경 검토·팀 변경과 충돌 확인·PR 준비가 우선입니다. 스테이징은 사용자 명시 요청 시에만 수행합니다.


### 2026-10-26 최신 이용 ID 계약 실제 검증 완료

사용자 진행 승인과 공용 DB 시험 범위 안내 후 기존 소유 시험 도우미를 재사용했습니다. 결과: `results/requirements_audit/parking_decision_live_cases/run_bb5d5dc9/result.json`, STATUS=PASS. 카메라·DDL·운영 코드 추가 변경 없음.

별도 합성 이용84번을 출차 처리하고 새 이용85번을 생성한 조건에서 실제 HTTP7건을 확인했습니다. 이전84번/누락 ID는 PENDING/UNDETERMINED이고 현재85번의 구획·예약 NULL 유지. 정상85번으로 다른자리 WRONG_SPACE/예약취소 NO_VALID_RESERVATION도 PENDING/미연결 유지. 정상85번은 PROCESSED/MATCHED와 DB연결 성공, 반복 요청은 UNCHANGED/MATCHED. 연결 후 이전84번 재요청도 PENDING/UNDETERMINED이며85번의 정상 연결 유지. 전 응답 AI receipt 검증 통과.

시험 도우미는 소유84번 종료행과 추가구획을 정리한 뒤 기본 소유5행을 정리했습니다. 최종 잔여0/기존이용4 보존. 실제 카메라 통과 대신 합성 시험행의 출차·재입차 조건으로 검증했으며 최신 계약으로 두 카메라 전체 시험을 다시 한 것은 아닙니다. 기존 전체 카메라 성공과 이번 새 HTTP계약 검증을 함께 근거로 사용합니다. 정상/이전ID의 실제DB 미검증이라는 아래 과거 기록은 이 결과로 갱신됩니다.

다음 우선순위는 실행·인계 정리입니다. 현장 명령은 `run_parking_demo.ps1 -CameraBackend dshow`(A1/B0, .venv312, SPACE 시작)를 명시합니다. 현재8000/8001 모두 통합main:app이며 단독 Vision app:app과 혼동하지 않습니다. 통합API가 필요하면 main:app 하나를 선택, 전용Vision이 필요하면 ai_vision.app:app을 선택하되 지금 실행 중 프로세스를 임의 종료하지 않습니다. 웹 판정 표시나 구획 이동이 현재 시연 범위로 필요해지면 먼저 변경안을 설명합니다. 새 카메라/AWS 반복 시험은 우선하지 않습니다. 스테이징/커밋/푸시 없음.


### 2026-10-26 중간 자가점검 결론

우선순위1: 새 expected_parking_usage_id 계약 적용 후 실제 정상 ID 연결·이전 ID 보류 및 기존 예약 판정 유지 확인. 구현/AI915개/Boot77개/실제 누락 요청 차단은 확인됐으나 새 계약으로 정상 DB 연결을 다시 확인한 것은 아닙니다. 시험 DB 범위를 먼저 안내하고 기존 업무 데이터는 보존합니다. 카메라 전체 반복보다 HTTP 계약 검증을 먼저 합니다.

현재 확인: feature/ai-vision, HEAD513010a49 및 git ls-remote의 develop 동일. 미커밋20파일(Java6/Python11/PS1/문서2), 스테이징0. 최신 상태 재확인은 업로드 직전 다시 필요합니다. 별도 fire/frontend 변경 없음. 공식 검사915개와 Boot77개는 현재 변경 뒤 보관 결과, 이번 점검에서 불필요하게 재실행하지 않았습니다. 두 Python 환경 pip check는 이번에 재실행해 정상, 로컬 프로필 pending manifest 0개입니다. 이는 실제 DB 전체 잔여 행을 새로 조회한 결과가 아니라 소유 표식 확인이며, 최근 회차 DB 정리 잔여0 근거와 구분합니다.

80/81/8000/8001 TCP 응답 확인. 8000과8001의 OpenAPI는 모두 통합 AI 앱(main:app), recognize 존재/ready 없음. Vision 전용 app:app의 ready 검증 결과를 이 두 프로세스에 그대로 적용하지 않습니다. 8000외부접속/8001로컬바인딩은 의도에 따라 가능하나 중복 실행의 역할 정리는 남았습니다. 자동 종료/재시작하지 않았습니다.

구획 이동은 handoff와 중간 해제 동시 활성 불가로 미완료입니다. 한대 입차→예약 주차→출차만 시연한다면 필수 확장 아님. 프런트에서 parkingDecision/WRONG_SPACE/NO_VALID_RESERVATION 참조 검색 결과 없음, 웹 판정 표시는 미연결입니다. B 프리뷰 코드와 웹 UI 완료를 구분합니다.

의존성: 통합 requirements를 재사용하는 개발용 Vision requirements와 CPU서버용 runtime 분리를 유지합니다. 새 Windows 환경 설치/원본 실제 인식·AWS Ubuntu Docker 인식/재시작의 과거 근거는 문서 경로에 존재합니다. 최신 Boot 변경과 AWS11g/전체통합/Kubernetes가 검증됐다는 뜻은 아닙니다. 모델·로컬 좌표/기준/비밀설정은 이미지·Git에서 제외되므로 배포 때 별도 모델/설정/결과 저장소를 전달해야 합니다. Kubernetes는 팀장님 담당, 현재 AWS를 켤 필요 없음.

후순위: 런처 명령은 현 장치에서 -CameraBackend dshow 명시(A1/B0; 재연결시 다시 확인), 기본 msmf는 유지. 구도 원본/좌표는 로컬 프로필이고 Git만으로 동일 시연을 복원할 수 없음. 영속 UUID 중복방지·프로세스 재시작 신원 복원·다중차량 ReID·야간/반사 실제차량 정확도는 미완료로 유지합니다. 별도 리커버리 워커는 사용자 결정으로 제외, 구현 대기 항목으로 다시 추가하지 않습니다. 화재는 별도 범위/이번 점검은 소스 변경 없음을 확인한 것이며 새 실제 성능 검증 아님.

문서 기능 표의 구현 완료 항목을 미완료로 표시하던 두 행을 갱신했습니다. 다음 작업은 위 우선순위1이며 새 기능을 임의 확장하지 않습니다.


### 2026-10-26 MATCH 이용 ID 사전 검증 구현

최신 반영 확인 완료: 사용자 STS Clean/재시작 후 bin/main 및 Gradle build/classes 모두 새 가드 문구 존재. 실제81 HTTP에서 expected_parking_usage_id 누락 MATCH 1건이 새 문구와 200/PENDING/UNDETERMINED를 반환하여 실행 서버 반영을 확인했습니다. expected_usage_live_contract.json의 success=true가 이전 반영 실패 기록보다 우선합니다. 갱신 서비스 호출 전 보류 분기이며 카메라/업무 데이터 변경 없음. 정상 ID·불일치 ID의 모의 검증과 이번 실제 누락 요청을 구분합니다. 새 가드 적용 후 전체 카메라 시연을 다시 완료한 것은 아닙니다.

후속 우선순위 검토: 현재 단일 차량 handoff와 enable_space_release_http는 run_parking_camera의 조합 검증에서 동시 사용이 금지돼 있습니다. 따라서 구획 이동 해제·재연결은 옵션만 켜면 되는 상태가 아니며, 현재 시연의 자동 출차 해제와 구획 이동 해제를 구분해야 합니다. 기존 입차→예약 주차→출차 범위에는 이동 확장을 필수로 넣지 않습니다. 다음 실제 검증은 필요 시 정상 ID 일치/불일치의 별도 시험 데이터로 한정하며, 추가 카메라 반복이나 자동 해제 활성화를 임의 수행하지 않습니다.


서버 반영 후속 점검: 사용자 재시작 후 JWT 서명 오류는 재로그인으로 해결됐습니다. 실제 HTTP에서 ID 누락 MATCH는 200/PENDING/UNDETERMINED였으나 detail이 이전 코드 문구라 새 가드 반영은 확인되지 않았습니다. 대상은 이전에 부재 확인한 999999F-Z99이며 실제 응답도 구획/활성 이용 부재로 연결 보류입니다. 무갱신 확인 1건, 카메라 사용 없음. 근거 expected_usage_live_contract.json(success=false는 새 코드 반영 확인 실패를 뜻함).

class 직접 대조: Gradle build/classes/java/main의 AiVehicleEventService.class에는 새 가드 문구가 있고 STS bin/main에는 없습니다. STS apcms_a F5 → Project Clean/재빌드 → 관리자81 재시작 후 같은 무갱신 요청으로 재확인해야 합니다. 컴파일 통과와 실행 서버 적용을 구분합니다. bin 파일을 수동 덮어쓰거나 서버를 자동 재시작하지 않았습니다.


사용자 승인 후 요청 DTO에 `expected_parking_usage_id`를 추가했습니다. MATCH에서 ID가 누락되거나 현재 유일한 활성 이용 ID와 다르면 연결 서비스 호출 전에 PENDING/UNDETERMINED로 보류합니다. 0/음수 ID 및 입출차 요청에 연결 ID 혼용은 400입니다. 기존 입출차 생성자는 유지합니다. 기존 MATCH 클라이언트는 필드를 보내도록 함께 갱신해야 하며, 누락 요청을 과거 방식으로 자동 연결하지 않습니다.

AI는 입차 handoff의 expected_parking_usage_id를 실제 HTTP payload에 넣고, 로컬 근거와 요청값 충돌·bool/문자열/정수 범위 오류를 차단합니다. 응답 이후 ID 대조도 유지합니다. 조회된 동일 ID를 기존 잠금·갱신 경로에 전달하므로 출차·재입차로 새 이용이 생겨도 새 ID로 대체 연결하지 않습니다. DAO/매퍼/DDL 변경은 없습니다.

Boot 운영 변경: AiVehicleEventRequest.java, AiVehicleEventService.java. 기존 AiVehicleReservationContractTest.java에 사전 차단 검사를 추가하고, AiSpaceReleaseTest.java의 기존 MATCH 예제 1곳에 ID를 보정했습니다. AI 기존 vehicle_contract.py/vehicle_delivery_flow.py와 기존 검사 두 파일을 수정했습니다. 새 검사 파일은 만들지 않았습니다.

검증: AI 공식 915개/38.369초, Boot 컴파일·주차 검사 통과. 근거 results/requirements_audit/expected_usage_{ai,boot}.log. 카메라·실제 HTTP·공용 DB 사용 없음. 실행 중 Boot의 반영은 미확인으로 다음 실제 연동 전 관리자81 재시작 필요. 바로 전 카메라 성공은 이 사전 검증 변경 이전입니다. 스테이징/커밋/푸시 없음.

다음은 관리자81 새 코드 반영 후 실제 요청 계약 확인입니다. 새 카메라 전체 시험은 우선 반복하지 않습니다. 공용 DB 시험이 필요하면 범위를 먼저 안내합니다. 이후 시연에서 구획 이동이 필요한지 결정한 뒤 자동 해제·재연결 활성화를 검토합니다.


### 2026-10-26 두 카메라 실제 연동 성공

`results/parking_demo/local/e2e_manual_830a2474/http_e2e_result.json`에서 TEST_SUCCESS=True, 완료 조건 8개 전부 참을 확인했습니다. DirectShow/A=1/B=0, 기존 .venv312, 갱신된 로컬 빈 기준·좌표로 실행했습니다. 입차→구획 연결→출차가 동일 이용 ID 83이며, B MATCH 실제 HTTP 응답은 APPLIED/receipt_verified=true/parking_decision=MATCHED입니다. B 독립 OCR은 사용하지 않은 한 대 통제 ENTRY_HANDOFF 모드입니다. 화면의 정상 주차 문구를 사람이 확인했는지는 별도이며, 실제 응답 판정 전달은 확인됐습니다.

종료 전 DB 출차/미출차 0건·B 신원 EMPTY를 확인했고 두 프로세스 정상 종료했습니다. 소유 시험 행 10개 정리, 잔여 0개, 기존 이용 4개 보존. DB 구조·기존 업무 기록 변경 없음. 이 성공 기록이 아래의 준비 중/실카메라 미완료 기록보다 우선합니다.

앞선 e2e_manual_f8d1f1c6은 A CLI에 미지원 camera-backend 인자를 전달해 준비 중 실패했고 DB 시험행은 생성되지 않았습니다. 해당 인자를 제거하고 기존 capture wrapper에서 DirectShow를 선택하도록 수정한 뒤 위 재실행에 성공했습니다. 수정 전 공식 회귀 912개 통과(41.145초), 수정 후 구문·diff 검사와 실제 전체 시연 성공을 확인했습니다. 자동 스테이징/커밋/푸시는 하지 않았습니다.

다음 필수 우선순위는 MATCH 기대 이용 ID를 Boot 갱신 전에 검증하는 보호입니다. 현재 성공은 응답 이후 동일 이용 검증을 포함하며, 사전 검증이 구현됐다는 뜻은 아닙니다. Boot 추가 수정은 파일·변경안을 먼저 제시하고 승인받습니다. 독립 B OCR/추가 AWS/카메라 반복 시험은 우선하지 않습니다.


### 2026-10-26 카메라 복구 확인

DirectShow로 A 입출차=1, B 주차면=0을 동시에 1280×1024로 확인했습니다. A 627프레임, B 633프레임에서 수신 실패 0회이며 두 장치 모두 Q 종료·해제를 확인했습니다. 근거는 `results/requirements_audit/dual_dshow_20261026_111716/camera_{0,1}.json`과 저장 원본입니다. 최초 MSMF 실패 원인은 확정하지 않았습니다.

저장된 B 빈 원본으로 로컬 `reference.png`를 교체하고 네 구획 좌표를 소폭 조정했습니다. 기존 좌표도 대체로 칸 내부에 있었으며 크게 어긋났다는 의미는 아닙니다. 겹쳐 그린 `parking_spaces_overlay.png`에서 네 칸 내부 정합을 확인했습니다. 이전 기준/좌표는 같은 결과 폴더의 `profile_before_recalibration`에 보관했습니다. 인식·HTTP·DB 시험은 하지 않았습니다.

다음 실제 시험은 `run_parking_demo.ps1 -CameraBackend dshow`를 사용합니다. 전체 시연 준비 확인 후 SPACE 시작으로 정상 주차 표시와 입차→연결→출차를 확인합니다. 현재 결과는 영상 수신/구도 확인이며 실제 인식 성공을 의미하지 않습니다.


카메라재연결점검(2026-10-26): 초기MSMF영상깨짐/수신실패로전체시험이준비단계중단,DB시험행생성없음. 기존.venv312에서도B단독실패했고USB재연결후DirectShow기본640x480단독영상확인. 재연결후현재A입출차=1/B주차면=0(저장영상직접대조),로컬demo.local.json만갱신. 장치번호는고정식별자가아니므로다음재연결후역할재확인필요. 런처에 -CameraBackend msmf|dshow 추가(기존msmf기본유지),양쪽runner에전달. dshow CheckOnly/구문점검통과. 현재기존좌표1280x1024에서DirectShow동시미리보기만진행중이며아직성공판정전. 인식/HTTP/DB없음. 초기실패원인을번호변경만으로확정하지않습니다.

### 2026-10-26 예약 주차 판정 후속

실제3판정HTTP/DB검증완료: 사용자에게범위를안내한뒤별도999층Z01/Z02·예약·이용만생성. WRONG_SPACE/PENDING과NO_VALID_RESERVATION/PENDING에서동일시험이용의구획/예약NULL유지, MATCHED/PROCESSED에서해당예약·구획연결확인. 세응답의이용ID동일/AI receipt검증·판정파싱통과. 취소된시험예약으로NO_VALID_RESERVATION확인후시험예약만복원. 임의업무행수정없음.
시험extra구획1행+기존도우미소유5행정리/잔여0/기존이용4보존. 카메라/AWS없음/스키마변경없음. 근거 results/requirements_audit/parking_decision_live_cases/run_d487f365/result.json. 없는구획UNDETERMINED까지포함해네종류실제HTTP확인완료. 시각입력은합성시험이며실카메라움직임·B화면의실제관찰검증은별도입니다. 아래3판정실제DB미완료표기는이검증이전입니다. 새시험도우미/결과는Git제외results에만존재하며제품Boot/AI소스를추가수정하지않았습니다.

실제HTTP후속완료: 구획조회403은관리자인증경로라보안설정유지. 기존설정의공용DB에SET TRANSACTION READ ONLY/SELECT COUNT로999999F-Z99부재확인후ROLLBACK. 그구획MATCH1회로HTTP200/PENDING/parkingDecision=UNDETERMINED 확인, AI receipt_verified=true/parking_decision=UNDETERMINED. 실제응답+합성관찰로표시함수전달확인. 새코드의Boot실행반영확인완료이나나머지3판정의실제업무DB/실카메라검증아님. 소스상구획없음분기로갱신없으며업무데이터생성/변경/삭제없음. 근거 results/requirements_audit/parking_decision_live_contract.json. 재시작반영미확인/무갱신HTTP미완료라는아래기록은이검증이전입니다.

실행서버점검: 사용자관리자Boot재시작후STS DTO class갱신확인. actuator/health는404이며이는주차API전체실패의증거가아닙니다. 공개구획목록GET /api/parking/spaces/public이403으로차단돼없는구획사전확인불가, 예정했던무갱신MATCH POST는전송하지않았습니다. 새parkingDecision의실제HTTP확인은미완료입니다. 임의인증우회/DB데이터변경/카메라사용없음. 다음은허가된조회경로확인후무갱신응답검증또는범위를안내한별도시험데이터검증으로진행합니다.

후속자가점검: B의현재상태가LOCAL_MATCH인경우만예약판정을표시합니다. 움직임/점유근거상실/번호·추적·구획변경시과거판정제거, 최신응답대기·차단·이용ID불일치시UNDETERMINED. 최신미확정응답이있을때이전성공으로돌아가지않습니다. 기존검사에현재근거변경사례를추가했습니다. 실제카메라/업무전송없음.

사용자가 Boot4개파일/AI연결수정을승인했습니다. latest develop513010a49의Oracle11g·상태확인변경을기준으로진행했고매퍼/DB구조/데이터/화재/프런트는변경하지않았습니다.
Boot응답 parkingDecision 추가: MATCHED/WRONG_SPACE/NO_VALID_RESERVATION/UNDETERMINED. 기존생성자·outcome(PROCESSED/UNCHANGED/PENDING)호환유지. 기존잠금/유효예약쿼리로현재차량예약과대상구획의다른차량예약을구분하며, 중복/상태충돌은판정불가입니다. 유효예약없음은취소·기간외세부사유를구분하지않습니다. 다른자리/예약없음/판정불가는DB연결하지않습니다.
AI는응답신원과판정/outcome일관성을검사하고기록하며, 현재관찰의차량·추적·구획과맞는검증응답만B미리보기에표시합니다. 구형서버판정없음은UNDETERMINED. LOCAL_MATCH는로컬연결표시이고정상예약판정과구분됩니다.
Boot수정파일: dto/parking/AiVehicleEventResponse.java, service/parking/{ParkingUsageService,AiVehicleEventService}.java, 기존검사AiVehicleReservationContractTest.java (모두apcms_a). 사전제안4개범위입니다.
Boot컴파일/주차모의검사75개·AI공식회귀911개(36.989초)통과. 근거 results/requirements_audit/{parking_decision_boot_online.log,parking_decision_final.log}. develop추가Actuator미캐시로최초offline검사차단후선언된의존성을받아검증. 실제카메라/HTTP업무전송/DB/AWS시험없음. 실행중서버를자동재시작하지않았습니다. 실제연동시관리자Boot81의새코드반영을확인해야합니다.
스테이징/커밋/푸시없음. Git업로드직전최신develop fetch/겹침·충돌과팀변경보존을반드시다시확인합니다. 다음우선순위는업무판정의실제연동필요성판단후필요한시험1회이며선택B재인식·AWS확장은하지않습니다.


최신 Git 요청: 사용자가 마지막 PR#88 이후 작업을 정리해 직접 커밋·푸시·PR 생성까지 요청했습니다. 이번 요청에 한해 수행합니다. 기본 규칙(명시 요청 없는 스테이징 금지)은 유지합니다. 대상은 시연 단계/최종판정 보완, 기본꺼진 선택적B번호판대조, 기존검사/기능점검문서입니다. 예약 주차 판정용 Boot4개파일 변경은 여전히 미승인·미수정입니다. 다음 재개 때 필요한 실행환경 안내와 Boot 변경 여부 재질문 지시는 유지합니다.

### 다음 출근 시 재개 지시 — 사용자 PC 완전 종료 예정

사용자가 여기서 작업을 마치고 PC를 완전히 종료합니다. 다음 재개 시 이 지시를 먼저 따릅니다.

1. Git 상태·현재파일·실행프로세스를 다시 확인하고, 이번에 필요한 것만 켜도록 안내합니다. Boot/FastAPI/가상환경/DB/AWS가 계속 실행 중이라고 가정하지 않습니다.
2. Python 기본 시연 환경은 `apcms_ai/.venv312`이고, 통합+runtime 새 검증 환경은 `.venv-vision-audit`입니다. 실제 명령에서 사용할 interpreter를 명시합니다. 활성화는 현재 터미널에만 적용되며 직접 python.exe를 지정하면 activate가 필요 없습니다. 기존 환경을 재설치하지 않습니다.
3. 주차 API 실제 연동을 할 때는 공용 DB 연결과 관리자 Boot(기존81/context `/alpharking/admin`)를 확인한 뒤 안내합니다. 사용자 Boot80은 필요한 기능을 시험할 때만 안내합니다. DB 비밀번호를 출력하거나 업무데이터를 변경하지 않습니다.
4. FastAPI는 API 인식 시험이 필요한 경우에만, 실제 작업에 맞는 `main:app`/`ai_vision.app:app`과 Python을 골라 안내합니다. 일반 모의검사에 Boot/FastAPI를 켜야 한다고 안내하지 않습니다. 카메라는 별도 준비 확인 후에만 사용합니다.
5. AWS는 즉시 원격 검증이 필요한 경우에만 이유를 설명하고 인스턴스 시작을 요청합니다. 새 퍼블릭IP/연결을 확인하며 과거IP를 현재로 가정하지 않습니다. 나중에 팀 배포 때 확인할 항목은 보류합니다. Kubernetes는 팀장님 담당입니다.
6. **예약 주차 판정의 Boot 수정은 아직 승인되지 않았습니다. 다음에 다시 물어본 뒤 진행합니다.** 사용자가 변경안을 보여달라고 요청해 설명만 했으며 파일은 아직 수정하지 않았습니다. 일반 `1`/재개 지시를 이 변경의 승인으로 해석하지 않습니다.
7. 재확인할 변경안: AiVehicleEventResponse.java에 parkingDecision 추가(기존생성자유지), ParkingUsageService.java에서 기존예약조회근거로 MATCHED/WRONG_SPACE/NO_VALID_RESERVATION/UNDETERMINED 구분, AiVehicleEventService.java에서응답전달, 기존 AiVehicleReservationContractTest.java 보강. 모두 apcms_a/src/main/java/kr/co/alpharking/{dto,service}/parking 또는 src/test/java/kr/co/alpharking/service/parking 아래의 앞서 제시한4개파일입니다. 기존PROCESSED/UNCHANGED/PENDING·검증·잠금유지. DDL/매퍼추가/실제DB/화재/프런트변경없음. 승인후AI JSON기록/B미리보기표시연결. 구형PENDING응답은오주차로추측하지않고판정불가표시합니다.
8. 현재 미커밋 작업은 앞선 시연판정 보완과 선택적B재인식 및 문서/검사입니다. B재인식은기본꺼짐이고한대통제시연의필수기능이아닙니다. 회귀909개통과/원본정지사진실제모델대조통과, 새기능의실카메라검증아님. 기존변경을보존하며자동스테이징하지않습니다.


전체기능재점검/시연범위정정: 차량1대통제시연에서는B독립재인식이필수가아닙니다. “동일차량을독립확인”과“한대조건으로연결”을구분합니다. 전체기능25개항목의구현/활성/실검증/미완료를VEHICLE_INTEGRATION.md의 “전체 기능 점검과 한 대 시연 기준”에통합했습니다.
현재필수순서: 정상주차/다른자리/판정불가의업무판정·표시 → MATCH기대이용ID사전검증 → 시연에필요할경우구획이동해제·재연결. Boot/프런트수정은사전설명/승인필요. 독립B재인식·다중차량·상시운영확장은선택후순위이며추가확장중단합니다.
이번에추가한B독립OCR확인은옵션이며기본꺼짐입니다. run_parking_camera의 --verify-handoff-plate와런처 -VerifyHandoffPlate로선택가능하고확인근거를전송기록/최종시연판정까지연결했습니다. 신규코드의회귀909개통과(39.281초). 실제YOLO/OCR·기존원본정지사진반복으로일치수락/불일치차단확인. 실카메라/HTTP/DB/AWS검증아님. 근거 results/requirements_audit/{full_function_audit_regression.log,identity_saved_model_result.json}. 기존성공시연기본모드는유지합니다. 기본꺼진옵션을실제시연완료로보고하지않습니다.
기존진행안내/최종판정보완은유지하며같은차량·이용·구획의응답만확인합니다. 이번변경전체는스테이징하지않았습니다. 아래이전완료/순서기록보다위시연범위판단을우선합니다.


최신 Git 상태: PR#88로 주차·의존성·이번 예외 화재 변경이 develop에 병합됐습니다. 이후 변경부터 화재는 다시 별도 범위입니다.
기본은 PR 준비까지이며, 스테이징은 사용자가 명시적으로 요청한 경우에만 합니다. 커밋·푸시·브랜치 변경·병합은 직접 진행합니다.
Kubernetes는 팀장님이 일괄 진행합니다. AWS는 현재 변경에 즉시 원격 검증이 필요한 경우에만 이유를 설명하고 인스턴스 시작을 요청합니다. 팀 배포 시 확인해도 되는 항목은 보류하며 반복 시험·클러스터 준비·배포를 임의 진행하지 않습니다. 배포 인계는 readme.md에 통합했습니다.

1. **이번 완료:** 시연 진행 안내와 최종 연결 판정이 같은 번호판·이용ID·시험구획의 검증된 응답만 인정하도록 공통화했습니다. 다른 이용의 출차는 STOP/전송중단 요청, 검증되지 않은 연결은 EXIT/DONE 단계로 넘기지 않습니다. 손상된 B 내부 결과는 연결 미확인으로 취급해 실행 중 속성 오류를 방지합니다.
2. **검증:** 관련복구27개/공식회귀899개(37.416초) 통과. 저장된 실제 성공2회는DONE 유지, 실패2회는출차대기 유지. 근거 results/requirements_audit/demo_identity_{guard_targeted.log,guard_regression.log,archived_replay.json}. 카메라/HTTP/DB/AWS 사용없음. 새 코드로 실제 카메라 재촬영은 하지 않았습니다.
3. **연결된 실행 점검:** Git 작업 후 Java helper가 소스보다 오래됐다는 사전차단 확인. 기존 Gradle캐시로 -Prepare 재생성 후 새환경 -CheckOnly 통과. 로컬 class/classpath만 갱신했고 Boot소스·DB 변경없음.
4. **남은 범위:** 현재 한 대 시연의 입차→연결→출차는 기존 실제성공을 유지합니다. 자동 구획해제 활성·다중차량·영속중복방지·MATCH 기대이용ID 계약은 별도 후속이며 이번에 확장하지 않습니다. 추가 카메라 시험은 필요성이 확인되고 사용자 준비가 된 경우에만 진행합니다.
5. 이번 수정은 Python3개와 기존 문서이며 스테이징·커밋·푸시하지 않습니다. UI의 DONE은 동일이용의 입차/연결/출차 응답 확인이며 최종 TEST_SUCCESS는 DB·B신원정리·장치종료·시험행정리까지 확인한 뒤 결정합니다.

<details>
<summary>최근 환경·AWS 검증 및 워커 제외 기록 (증빙, 다음 작업 지시는 위 순서 우선)</summary>

최신 AWS Linux 검증 완료(2026-10-23): 사용자 제공 IP로 Ubuntu24.04/amd64 접속, 기존 서비스 healthy 확인 후 별도 requirements-check-20261023 이미지를 실제 Dockerfile로 빌드했습니다. 최신 runtime/pi-heif 포함 pip check/API·Vision·OCR import 통과. 화재 코드·비밀설정·로컬 프로필/카메라 자료는 업로드하지 않았습니다. car12.png 한 장은 현재 AWS 전송을 사용자에게 명시적으로 승인받은 후 업로드했습니다.
서버 관련73개 수집 중72개통과/1개제외(운영 이미지에서 의도적으로 제외한 GUI 개발 도구 검사). 첫 실행 실패는 GUI개발도구 누락/Windows MSMF 고정/모의검사의 OCR 환경변수 영향으로 구분했습니다. 취소검사를 공통 auto backend로 정정했고 Windows에서도21개통과. Linux 모의검사는 OCR 경로를 격리하고 실제 인식에는 로컬 모델 경로를 명시했습니다. 실패 로그도 보존했습니다.
별도 컨테이너 network none/CPU2/메모리·스왑포함4GiB/비root/모델·OCR캐시읽기전용 조건. health·ready·실제HTTP 인식 모두200/91소6408, 서버프로세스 재기동 후 동일 성공. 컨테이너 자체 재시작 후에도 전체 점검과 인식 재성공(9.94초/서버재기동10.15초), cgroup최고2,289,393,664바이트(약2.13GiB)/oom0/oom_kill0. 시험컨테이너 Exit0/OOMKilled=false, 기존 apcms-vision-service healthy 유지. 새이미지를 기존 서비스에 적용하지 않았습니다.
근거 results/deployment_checks/20261023_requirements/{source_manifest.json,build_final.log,results/linux_result.json,results/regression.log,check_container_restart.log}. 최종이미지 sha256:c54f5ef286c7f3d3229eb0d90c87d0da48da7cfe76585dffb03f1f254b15e40f.
다음: Kubernetes 대상 클러스터·레지스트리·스토리지 및 현장카메라/서버역할 확인 후 배포 설정 준비. 현재 AWS호스트에서 kubectl/kubeadm/k3s 경로는 없었지만 이것만으로 다른 관리형 클러스터가 없다고 판단하지 않습니다. 클러스터설치/서비스교체/DB/카메라/Git스테이징 작업은 하지 않았습니다. 이미지범위는 Vision API·주차이며 화재 검증/통합문의추천 검증이 아닙니다.


실행 전제 후속점검(2026-10-23): 모델2개/OCR로컬파일/결과저장소 검사 통과. 로컬 프로필·기준사진1280×1024·네 구획 좌표크기 일치/A BoT-SORT 확인. Java25와 기존 helper class major69 일치이며 새 PC에서는 class 복사 대신 해당 JDK로 -Prepare 재생성이 필요합니다.
런처에 선택적 -PythonExe를 추가해 기본 .venv312 유지/새 .venv-vision-audit 선택 모두 -CheckOnly 통과했습니다. PowerShell 구문 및 diff 공백 검사 통과. 카메라/HTTP/DB 작업 없이 확인했으며 새 환경의 실제 카메라 시연은 미검증입니다.
근거 results/requirements_audit/non_package_preflight.json. 로컬 Docker 엔진은 중지 상태입니다. 기존 apcms-aws 별칭에 BatchMode/8초 제한으로 읽기 전용 SSH를 시도했으나 TCP22 연결 시간초과라 최신 Linux 재빌드/Kubernetes 조회는 진행하지 못했습니다. 업로드/원격 변경 없음. 기존 별칭의 현재 유효 여부·EC2 실행 및 네트워크 접근 확인이 다음 Linux 검증의 전제입니다.


사용자 결정(2026-10-23): 별도 화재 리커버리 워커를 제외합니다. `safety/fire_recovery_worker.py`와 전용 검사 파일을 제거했습니다.
기존 화재 감지·송신기의 재시도/ACK 기록은 유지하며 Kubernetes 배포에 별도 자동 복구 워커를 추가하지 않습니다.
주차 시연의 시험 데이터 정리·복구 모듈은 별개이므로 유지합니다. 기존 사건 기록·결과 파일은 삭제하지 않습니다.

</details>

이 절을 현재 판단 기준으로 사용합니다. 아래 접힌 과거 기록의 “최신·다음 순서·미적용” 문구는 당시 기준입니다.

| 항목 | 확인된 결과 | 아직 남은 확인 |
|---|---|---|
| A 번호판·입차/출차 단독 | 인쇄91소6408, DOWN/UP 각각 실카메라 성공 | 실제 차량 환경 일반화 |
| A→B 신원 전달·예약/구획 연결 | 실제동시시험 동일이용80의 ENTRY/MATCH/EXIT APPLIED | 반복·환경변화 일반화 |
| 동시 전체 시연 | 69b2ea8f 최초성공/3fa3892b 취소후재성공,각완료조건8개통과 | 상시운영·환경변화 검증은아님 |
| 추적·성능 개선 | A BoT-SORT 유지,명시960옵션. 원본추적/6개OCR확인 | 카메라·UI·HTTP 포함 실시간 관찰간격 |
| 최신 동시부하 재생 | A960/OCR모델상주+B1280/점유,각79장,양쪽1초초과0 | 실제OCR호출·카메라·UI·HTTP를 포함한 시험은 아님 |
| B 점유 | 최신회차 A-01만 EMPTY→OCCUPIED→EMPTY, 다른3칸변동없음 | 반복·조명/구도변화 안정성 |
| DB 생애주기 | 서비스/매퍼22검사,실HTTP11항목 과거통과 | 자동해제HTTP활성·AWS11g·실동시잠금 |
| 자동 구획 해제 | 버전보호 구현,실행서버/현재A→B시연에서는 비활성 | 활성화 필요 시 범위설명·승인·시험 |
| 시험 정리 | 최근회차 시험잔여0/기존이용4보존. 이번 로컬매니페스트 미정리0 | 신규DB조회로 다시 확인한 것은 아님 |

### 지금 우선순위

현재 우선순위는 위 “현재 상태와 다음 순서”의 최신 사용자 결정을 따릅니다. 배포 조건은 readme.md에 통합했고, 아래 기록은 당시 판단의 근거로만 보존합니다.

<details>
<summary>이전 점검·작업 순서 기록 (추가 AWS/Kubernetes 지시로 사용하지 않음)</summary>

#### 전제 재점검 및 우선순위 정정 (2026-10-23)

**후속 실행 결과:** 통합 목록과 Vision runtime을 함께 참조하도록 Vision 개발 requirements를 통합했습니다. 상위 파일에는 Windows pip의 cp949 해석 오류를 막는 UTF-8 선언만 추가했습니다.
기존 `.venv312`는 변경하지 않고 `.venv-vision-audit`를 새로 생성해 통합+Vision 전체 패키지를 설치했습니다. 최초 해석247패키지/직접조건51개 충족, 실제 검사에서 누락 pi-heif를 확인해 runtime에 기존 성공 환경과 같은1.4.0을 명시·추가설치했습니다. 최종 직접조건52개 충족/pip check 통과입니다.
Windows 샌드박스의 asyncio·파일교체 접근거부로 첫 실행이 실패했고 제한 밖에서 같은 새 환경으로 재검증했습니다. 재검증에서 실제 누락 pi-heif로 회귀2개 실패한 뒤 보완했고 최종895개/41.682초 모두 통과했습니다. 실패 로그도 보존합니다.
두 진입점 `main:app`, `ai_vision.app:app` 각각 uvicorn 임시 localhost 포트로 실제 기동·health200·HTTP `/recognize`200·car12.png의91소6408 인식을 확인하고 시험 서버를 종료했습니다. 별도 ASGI 검사도 통과했습니다. 첫OCR91소66408→재시도91소6408이므로 재시도까지 검증했습니다.
근거는 `results/requirements_audit/`의 clean_install.log, clean_installed_requirements.json, clean_freeze.txt, clean_api_inference.json, clean_http_inference.json, clean_regression_final.log입니다. 가상환경/로그/결과는 Git 제외입니다.
**검증 경계:** 통합 파일만 단독 설치한 환경이 아니라 통합+runtime 동시 설치 환경입니다. 기존 로컬 가중치/OCR 캐시를 명시해 재사용했으며 모델 없는 새 PC의 전체 초기 구성, Linux/Docker runtime 단독 설치, Kubernetes, 실차/카메라/공용DB는 이번에 검증하지 않았습니다. 문의/추천의 실제 서비스 기능도 health 성공으로 완료 처리하지 않습니다.
**다음 우선순위:** 모델·프로필·Java/Gradle 등 패키지 외 실행 전제 점검 → 필요 시 준비 후 카메라 확인 → Git 범위 정리 → Linux 이미지 실제 설치·추론 → Kubernetes 설계/검증. requirements runtime은 전체 전이 의존성을 고정한 lock이 아닙니다.
이번 변경 파일은 통합 requirements(인코딩), Vision requirements(참조 통합), runtime(pi-heif), 기존 README/HANDOFF입니다. Boot/화재/카메라/DB/스테이징 변경은 없습니다.

아래 전제 점검의 미검증 표기는 위 후속 결과 이전 상태입니다.

아래 과거의 “시연 재실행 후 Git”보다 이 순서를 우선합니다. 통합 requirements 기준 새 환경 설치 검증이 기존 중간점검에서 누락됐습니다.

1. 통합 `apcms_ai/requirements.txt`를 기준으로 Vision 개발·runtime·Docker 의존성을 대조하고 중복 선언·버전 차이·전이 의존성을 정리합니다. 문의/추천/화재 의존성을 임의 삭제하지 않습니다.
2. 성공한 `.venv312`는 보존하고 별도 깨끗한 환경에서 설치합니다. resolver 성공, 실제 설치, pip check, import 성공은 각각 기록합니다. Windows 결과를 Linux 결과로 대체하지 않습니다.
3. 같은 새 환경에서 통합 `main:app`과 Vision 전용 `ai_vision.app:app` 기동을 구분해 검사하고, 저장 이미지로 실제 YOLO/OCR 및 `/recognize`를 확인한 뒤 공식 회귀를 실행합니다. 외부 서비스·키·모델 부재는 패키지 오류와 구분합니다.
4. 실행 파일뿐 아니라 모델 가중치/OCR 캐시·설정, 기준사진/좌표, Java/JDK/Gradle 캐시, Boot API/키·DB 조건, 결과 저장 권한까지 새 PC 재현 전제로 점검합니다. 비밀값은 기록하지 않습니다.
5. 카메라가 필요한 변경인지 먼저 판단하고 필요한 경우에만 사용자 준비 후 실제 시연합니다. 그 다음 Git 포함범위·팀 변경·비밀/로컬 파일 제외를 확인합니다. 커밋/푸시는 별도 지시를 따릅니다.
6. Kubernetes는 별도 Linux 이미지 실설치/추론 검증 이후 진행합니다. 카메라 현장처리와 Pod 역할, 단일 worker/Pod 상태 제약, 재시작·저장소·probe·자원·Secret 및 AWS11g/Boot 배포 호환을 확인합니다.

현재 확인: 기존 환경 pip check 통과. 그러나 기존 감사 기록상 pandas3.0.6은 통합 pandas<3 조건 불일치, 통합 패키지 일부 미설치, Vision 개발 YOLO8.4.177/runtime8.4.178 불일치입니다.
이것은 기존 설치 메타데이터의 일관성과 requirements 준수가 다름을 뜻합니다. 새 환경 설치·통합 서버 기동·같은 환경 실제 인식은 아직 미검증입니다.
공식 895개 검사는 DB·실제 모델·카메라 없는 회귀이며 새 설치/실제 인식을 보증하지 않습니다. `/health`는 프로세스 확인, `/ready`는 파일·저장소 확인이고 실제 추론 준비 완료 보증이 아닙니다.
과거 단일 차량 종이 시연 성공은 보존하되 실제 차량·다중 차량·영속 중복 방지·자동 해제 활성·AWS11g·Kubernetes 성공으로 확장하지 않습니다.
이번 재점검은 읽기 및 이 문서 정정만 수행했습니다. 패키지 설치·카메라·DB·Boot/화재 코드·Git 스테이징 변경은 없습니다.


실행의존성 정리: `parking/demo_tools/`에검증된A/B/컨트롤러·Java소스·Gradle초기화·빈프로필예제를정식경로로이동했습니다.
고정런처는날짜가붙은results의Python/기존class를사용하지않습니다. 새로컬프로필은 `results/parking_demo/local/`.
기존사진/좌표를보존복사했으며Java는명시한번호판·예상DB대상/매니페스트만사용합니다. 비밀번호는소스/프로필에추가하지않았습니다.
`-Prepare`는이미설치된Gradle캐시만사용해클래스패스/도우미를재생성하며다운로드/Boot컴파일/DB접속을하지않습니다.
재생성·CheckOnly통과,프로필/복구31개와공식회귀895개통과(41.083초). 원본성공회차/취소회차기록은그대로보존했습니다.
Git포함후보는소스·기존검사·문서·예제이며로컬프로필/사진/좌표/결과/class/classpath는ignore확인. 목록은results/parking_demo/git_scope_review.json.
스테이징·커밋없음. 화재변경보존/Boot소스변경없음. 새실행경로이동후실카메라·DB재검증과새PC설치검증은아직전입니다.
다음은현재PC에서이동된진입점의실제전체시연1회확인후Git정리로진행합니다. Kubernetes매니페스트작업은그후입니다.

취소후전체재실행성공: e2e_manual_f4d6f683 준비Q취소뒤 e2e_manual_3fa3892b에서 TEST_SUCCESS=true 재확인.
새공통정리모듈로 동일이용81 ENTRY/MATCH/EXIT APPLIED, 정리전OPEN0/버전2/B신원EMPTY/완료조건8개true.
시험10행정리/잔여0/기존4건보존, 두장치정상종료. B는A-01만OCCUPIED변경, 최종4EMPTY입니다.
이로써 최초전체성공69b2ea8f와취소후재성공3fa3892b를확인했습니다. 실제강제종료·DB장애복구·환경변화일반화검증은아닙니다.
다음은반복카메라시험보다검증된실행설정·로컬의존성정리와Git포함범위점검을우선합니다. Kubernetes배포는그후순서입니다.

실제준비취소검증완료: e2e_manual_f4d6f683에서SPACE없이각창Q, 두프로세스종료0/카메라해제,
A관찰0·전송0/B관찰0·전송0/매니페스트없음/NO_DB_FIXTURE_CREATED를확인했습니다.
이취소회차의success=false는전체업무시험을시작하지않았다는뜻이며취소경로실패가아닙니다.
취소후고정런처-CheckOnly통과/미정리차단없음/A BoT-SORT960·공통정리모듈연결을재확인했습니다.
다음은사용자준비후같은런처로전체시연을재실행해취소후복귀와성공의반복재현을확인합니다.

안정성 후속검증: B결과의내부자료형손상으로정리가생략되던경로수정. 복구23개/공식회귀887개통과(39.111초).
과거실제결과4회(실패3/성공1)를모의DB콜백으로각3회재생한12건이기존판정과일치했습니다.
근거 `results/camera_layout_checks/parking_recalibration_5190f156/recovery_archived_replay.json`, `results/parking_recovery_regression.log`.
실제카메라·공용DB·Kubernetes사용없음. 다음은준비미리보기에서SPACE전Q취소/장치해제/DB무작업을사용자준비후확인합니다.

배포 방식은 사용자 지정에 따라 Kubernetes를 기준으로 합니다. 배포 매니페스트 작성·클러스터 변경은 안정성검증 이후입니다.
카메라 현장처리와 서버Pod의 배치, 재시작 시 신원파일·결과보관, CPU/메모리자원, 설정·키주입, 상태확인 방식은 이후설계항목입니다.
현재Windows로컬공유파일·메모리상태를 그대로다중Pod에서쓸수있다고가정하지않습니다. 실제클러스터/DB/Boot변경없음.

실패후재실행 점검: 내부자료형이손상된B결과가정리를막던경로수정. 정리실패→재시도,미확정응답→확인후복구,
다른이용/미확인소유권차단,손상매니페스트차단을기존검사에통합했습니다. 복구검사23개통과이며 실제업무DB장애시험은아닙니다.

실행·복구 정리 진척: 고정진입점 `ai_vision/run_parking_demo.ps1`과 공통종료모듈 `parking/demo_session.py` 추가.
기존start_e2e.ps1도고정진입점을호출하며 `-CheckOnly`로로컬파일·미정리상태만확인가능합니다. 현재미정리0/사전점검통과.
중단·미확정응답·정리오류·이미정리된성공재점검 등17개검사를기존주차파일에통합, 해당파일129개/공식전체881개통과(39.455초).
실제카메라/DB재실행은없고 성공69b2ea8f 결과는보존했습니다. 새중단처리를실제DB강제종료로검증한것은아닙니다.
프로필·사진·좌표·JavaDB도우미/클래스패스는현재PC로컬의존이남으므로3번을전체완료로보고하지않습니다.
정리불명확시결과파일에보류이유를남기고다음실행차단, 실행중카메라/미확정이용을추정해삭제하지않습니다.

최신 완료: `e2e_manual_69b2ea8f`에서 A BoT-SORT960의 입차→B연결→출차와 B신원정리를 실제확인했습니다.
동일이용80, 정리전DB OPEN_ROWS=0/EXITED_ROWS=5/버전2, 완료조건8개모두true, 시험10행정리/잔여0/기존4건보존입니다.
B는A-01만점유변동했고최종4EMPTY, A-04의추가오점유는이번회차없었습니다. A수집공백1초초과3회/최대5.234초는남은성능제약입니다.
아래1번은최초전체성공기준충족,2번은이번회차충족입니다. 다음작업은3번 실행재현성·정리와 장애복구검증을 우선합니다.
이1회결과를자동구획해제/다중차량/실차/AWS성공으로확장하지않습니다.

0. 새 전체시험 전에 성공판정의 신뢰성을 유지합니다. 응답의 동일이용뿐 아니라 정상프로세스/B상태, B신원정리, 정리전DB의열린이용0·출차반영, 시험정리완료를 모두 검사합니다.
   e2e_template/controller.py에 completion_checks/incomplete_reasons를 추가했고 완전성공·실패조건6종·과거실제실패3회 등10검사를 통과했습니다.

1. A BoT-SORT+960으로 실제 동시 입차→A-01연결→출차를 완성합니다. 최대관찰간격과 동일이용 EXIT APPLIED를 함께 확인합니다.
   관찰간격1초 초과가 남으면 저장원본으로 분석하며 무작정 재촬영하거나 임계값만 완화하지 않습니다.
2. 같은 기준에서 B의 A-04 오점유변동과 차량사진 제거 후 EMPTY 안정성을 검증합니다. 빈기준 재설정은 구도·빈장면 확인 후에만 합니다.
3. 동작이 확인된 시험 실행코드를 Git제외results에서 재현가능한 실행경로로 정리합니다. 한 번만 쓰는 실험·원본·키·DB접속정보는 커밋하지 않습니다.
4. Boot 실행클래스 Git제외, 새PC시작방법, AWS11g DDL/트리거·API배포 설정을 팀과 정리합니다. Boot수정은 파일·이유 사전설명/승인 후입니다.
5. 자동해제/구획이동재연결,재시작복구,다중차량·다중세션,영속중복방지·기대이용ID MATCH 계약은 별도 후속입니다.
   현재 MATCH 요청에는 기대이용ID가 없어 응답사후검사만으로 잘못된DB연결을 되돌릴 수 없습니다. 한대통제시연을 일반운영완료로 보고하지 않습니다.

</details>

### 전체 범위 재점검에서 빠뜨리면 안 되는 항목

- 시연의 사진제거/점유EMPTY, 버전보호구획해제, EXIT에의한이용종료는 서로다릅니다. 현재자동해제는비활성이므로 한흐름으로완료처리하지 않습니다.
- A확정출차후B신원·진행중연결후보정리가 실제로완료되는지 확인합니다. 파일보관과 신규연결허용도 다릅니다.
- A관찰은최대300초이며5초신호소실/중단시 B신규연결은보류합니다. 파일에신원이남아도 재시작복원·출차까지무기한운영이구현된것은아닙니다.
- 잘못된유효형식번호/복수차량/예약없음·취소·시간외/구획이동/중복·순서뒤집힘의 실제검증범위는 단일번호통제시연성공과 분리합니다.
- 전송타임아웃/서버중단/촬영중강제종료는 결과불명확과 DB반영실패를 구분합니다. 자동재시도하지않으며 복구·소유권검증을 유지합니다.
- DONE안내와 최종TEST_SUCCESS는 다른단계입니다. 현재DONE은EXIT응답안내이고 최종성공은DB확인·장치종료·정리까지 완료해야 합니다.
- 테스트DB정리는 업무출차가 아닙니다. 삭제후열린이용0만으로출차성공을주장하지않고 반드시정리전DB를검사합니다.
- 저장사진부하검사에는 카메라드라이버/창표시/HTTP/실제OCR호출·결과저장이모두포함되지않으므로 실시간최종보장은아닙니다.
- 실제차량/다른번호/조명·야간/반사·가림은 일반화검증후속입니다. 종이91소6408성공을실제차량전체성능으로확장하지 않습니다.
- 배포준비에는 실행진입점·모델파일/버전·카메라선택·기준사진/좌표·포트/context/API키·DB버전·실행클래스와 로그/결과보관정책을 포함합니다.

### 현재 실행·검증 기준

- 고정 런처: `ai_vision/run_parking_demo.ps1`, 소스 `parking/demo_tools/`, 기본 로컬 프로필 `results/parking_demo/local/`. 기존 `results/camera_layout_checks/parking_recalibration_5190f156/start_e2e.ps1`도 호환됩니다.
- A0/MSMF1280×1024/plate/BoT-SORT/추론960, B1/MSMF1280×1024/plate/추론1280.
- 각창 SPACE 전 준비미리보기만, 양쪽시작+B빈검사통과 뒤 시험DB준비. Q사진저장·종료 후 콘솔정리출력까지 기다립니다.
- 종이A-01은 해당시험에서만999F-Z01로전송. 기존업무행·실제1F-A01·화재를 수정하지 않습니다.
- 공식회귀895개통과: `results/parking_packaging_regression.log`. 광범위discover의 과거OCR실험7개 오류는 별개로 남습니다.
- 동시부하근거: `results/camera_layout_checks/parking_recalibration_5190f156/dual_runtime_check/{A,B}_result.json`.
  A최대0.25초/B최대0.282초는 저장사진 분석구간 결과이며 전체시연성공을 의미하지 않습니다.
- 현재브랜치 feature/ai-vision-parking. AI주차 변경에는 운영Python·기존검사·기존문서와 새공통종료모듈/고정PS진입점이 포함됩니다. 미스테이징·미커밋.
  화재파일변경은 다른담당작업으로보존. 현Boot수정없음. 로컬실행클래스2개는Git제외상태입니다.

<details>
<summary>과거 작업·시험 기록 (당시 기준, 현재 상태는 위 표 우선)</summary>

### 과거 상태 기록

### A 추론 크기 옵션·지연 표시 추가 (최신)

BoT-SORT 유지, 일반 plate1280/vehicle640 기본 유지. 명시 --tracking-imgsz 960 옵션을 A 로컬번호판모드에 추가했습니다.
vehicle/합성demo의크기지정은카메라전거절, boolean/잘못된크기거절, 원본입력·상자좌표·OCRcrop유지, 결과tracking_imgsz저장입니다.
실제최근원본79장 비교:1280 중앙0.190초/추적61,960 중앙0.107초/추적61,640 중앙0.061초/추적60.
960 입차·출차각3개원본crop OCR6표본모두91소6408. 저장자료단일프로세스 성능이며 실시간동시지연해소 확정아닙니다.
e2e_template/gate_runner.py는A960을명시하며 화면에추론시간/관찰간격과1초초과경고를표시합니다. 1초연속성제한과B설정은유지합니다.
관련70개통과, 공식 ai_vision.tests.run_checks 864개통과(62.266초), 로그results/parking_regression_960.log.
광범위discover는과거실험7개import오류가있어전체통과로보고하지않습니다(results/current_regression.log). 별도의존성설치없음.
이번수정은production Python4개(처리기/CLI/기존검사2개),문서2개,Git제외시험템플릿입니다. Boot/화재미수정,커밋·스테이징없음.
다음은기존start_e2e.ps1로수정된BoT-SORT+960의실시간입차/연결/출차와관찰간격을확인합니다. 새카메라사용은준비확인후.

### BoT-SORT 실제 동시시험: ID유지되나 1초공백초과 (최신)

e2e_manual_36f63c5e는 실제tracker=botsort 적용. ENTRY/MATCH APPLIED 동일이용79, EXIT0입니다.
출차ID2는 프레임58~79에서 아래Y725.5→위Y247로 유지됐습니다. 이번 원인은 ID분리로 보고하지 않습니다.
출차구간 처리약1.2~1.4초, 전체수집공백1초초과49회/위치버퍼공백초기화21회입니다.
기존 max_gap_seconds=1.0 때문에 위치이력이 끊깁니다. 실제기록재생1초제한 DOWN1/UP0, 진단2초제한 DOWN1/UP1로 차이를 재확인했습니다.
2초값은 원인검증용 비교이며 운영·시험 판정에는 적용하지 않았습니다. 추가연결오류 검증 없이 조용히 완화하지 않습니다.
시험10행정리/잔여0/기존4건보존/두장치정상Q종료. BoT-SORT 유지.
다음우선순위는 분석시간 단축으로1초연속성을확보하거나, 검증된설정으로관찰간격을명시적으로지원하는 것입니다.
저장원본으로 우선검증하고 새촬영요청은 그후입니다. 카메라/DB재실행없음.

### 이전 시험 미정리 차단 복구

e2e_manual_226cfa55에 committed=true/cleaned표시없음으로 start_e2e.ps1이 차단됐습니다.
두 장치 해제 로그/해당회차 프로세스없음/A HTTP시도0·저널없음을 확인했습니다.
공용DB 조회에서 기존이용4/열린이용0/연결0을 확인하고 매니페스트의 시험소유5행만 정리했습니다.
잔여0/기존이용4건보존, cleaned=true 저장. recovery_result.json에 근거를 보존했습니다.
카메라는 켜지 않았으며 차단 조건을 우회하거나 삭제하지 않았습니다. 이전 controller 종료 원인은 결과파일 부재로 확정하지 않습니다.

### 사용자 지정 추적 방식: BoT-SORT 유지

사용자가 앞으로도 BoT-SORT로 진행하도록 지정했습니다. 이후 A 입출차 시험의 추적기는 botsort로 유지합니다.
현재 start_e2e.ps1은 e2e_template/gate_config.json의 tracker=botsort를 회차별로 복사합니다.
과거 ByteTrack 설정을 복사해 새 A 시험에 사용하지 않습니다. 단독 A 진단도 새 회차 설정에 botsort를 명시합니다.
B 주차면 추적기와 일반 운영 기본값 변경은 이번 지정만으로 확장하지 않습니다.
저장 원본 검증 성공과 실시간 두 카메라 전체 시험 성공은 계속 구분합니다.

### 저장 원본 추적 재생 검증과 A 시험 설정 수정 (최신)

e2e_manual_1cf0d9e2의 실제 출차 원본91장을 실제 모델로 탐지 재생:87장탐지/기존추적71장, 탐지있고ID없는프레임16장입니다.
동일탐지·동일촬영시각 비교에서 ByteTrack기본 UP0, 연결임계값0.95도UP1뿐이라 이 완화는 채택하지 않았습니다.
기존 지원 BoT-SORT는 동일탐지/원본/시각의출차2회를모두UP으로복구했습니다.
추가로 전체원본220장을 실제 YOLO.track(botsort.yaml)로 재실행하고 기존 LineCrossingCounter·원촬영시각으로 DOWN1+UP2를 확인했습니다.
통과선/ROI/안정화3프레임/여유12px/공백1초/속도검사는 바꾸지 않았습니다. 서로다른ID를 임의합치지 않습니다.
재생결과 botsort_full_replay.json, 탐지 detection_replay.json, 연결비교 association_replay.json에 보존했습니다.
따라서 e2e_template에 A전용 gate_config.json(tracker=botsort)을 추가하고 gate_runner와 start_e2e.ps1의설정복사를수정했습니다.
일반운영기본과 B/Boot/DB구조/화재는 변경하지 않았습니다. 기존사용자명령은 그대로이며 다음회차부터 A시험설정만 적용됩니다.
병렬모델 CPU비교에서4스레드제한은 더느렸으므로 채택하지 않았습니다. 초기단일벤치 첫항목은 모델설정의스레드변경영향이있어 설정근거로 쓰지 않습니다.
이 검증은 저장자료재생이며 실시간동시카메라/HTTP/DB출차성공은 아직 확인 전입니다. 카메라·DB를 사용하지 않았습니다.

### 동시 시험 출차2회 미검출 확인 (최신)

e2e_manual_1cf0d9e2: ENTRY APPLIED 이용78, B MATCH APPLIED 동일78, DB LINKED1/OPEN1/버전1입니다.
사용자는 출차를2회 시도했습니다. 원본116/177번을 직접 확인했고 위치 이력 재생은 DOWN1/UP0입니다.
첫 출차 아래쪽ID6(97~112)→위쪽ID13(120~155), 두 번째ID15→17→19→20으로 단절됐습니다.
ID20 최초Y523.5는 여유영역(500~524)이며 아래쪽확정 이력이 없어 UP이 생성되지 않았습니다.
동시220처리프레임/165관찰/공백초기화9/처리최대2.217초. 원본으로 움직임은 확인되며 원인 전부를 사용자 조작으로 돌리지 않습니다.
DONE 미표시는 EXIT HTTP0이기 때문입니다. 오류없이 Q 종료/두장치해제, 시험10행정리/잔여0/기존4건보존.
다음 작업은 새 촬영보다 저장된 gate_frames와 실제 모델로 이동 중 추적 단절을 재현·분석하는 것입니다.

### A 단독출차 진단 성공 (최신)

gate_exit_diagnostic_fa59df60은 SPACE 후103프레임/통과1/OCR3표본모두91소6408 CONFIRMED입니다.
당시 실행로그 UP, 실제 위치이력 재생도 ID2의 UP1건으로 일치합니다. 분석 원본102장 존재를 확인했습니다.
Q 정상종료/error_type=null/cleanup_errors0/HTTP0/장치해제완료입니다.
입차와 출차는 각각 단독 환경에서 확인됐으며 두 카메라 동시실행의 출차 안정성이 해결됐다는 의미는 아닙니다.
다음 우선순위는 전체회차에서 출차까지 확인하는 것이며 추가수정 전 동시처리 지연과 ID연속성을 기록해야 합니다.

### 출차 추적 진단 준비

직전 전체 시험 A 처리최대4.039초/1초초과수집공백37회로 지연 영향 가능성이 있지만 원인 확정은 아닙니다.
thread_benchmark.json은 저장된 실사1장의 단일프로세스 비교이며16스레드중앙값0.170초,4스레드0.260초입니다.
단일 시험만으로 두 프로세스 자원경합 해소를 주장하지 않으며 기본 스레드 설정은 유지했습니다.
gate_exit_diagnostic_fa59df60에 A 단독60초 무전송 진단을 준비했습니다. SPACE 후 분석 원본JPEG/시각/ID를 최대128MiB·1200장 보존합니다.
실행하지 않았으며 사용자 준비 후 아래→위 출차만 확인합니다. 저장 프레임은 재생·원인검증용이며 전체프레임 동영상이 아닙니다.

### 수동 전체 시험 e2e_manual_13736305 (최신 결과)

실제 A ENTRY HTTP200/APPLIED 이용77, B VEHICLE_SPACE_MATCH HTTP200/APPLIED 동일이용77로 확인했습니다.
B 자체OCR0이며 A 신원으로 연결했습니다. 정리 전 DB LINKED_ROWS=1/OPEN_ROWS=1/LINK_VERSION=1.
EXIT 요청·응답은0이라 전체success=false입니다. 오류 종료가 아니라 두 프로세스 Q 정상종료입니다.
A 출차 구간 추적기록은 ID11이 아래쪽Y약683~686(프레임97~106), ID15가 위쪽Y약273(111~119)입니다.
두 위치가 같은 ID로 이어지지 않아 출차 통과가 생성되지 않았습니다. 그 사이 탐지 공백/ID 변경 원인은 아직 미확정입니다.
초기 입차는 ID8의Y352→558.5로 통과1을 생성했습니다. 결과를 전체실패로 뭉뚱그리지 않습니다.
시험10행정리/잔여0/기존이용4건보존. B A-04 점유변동도 남아 실시간 안정성 전체 완료로 보지 않습니다.
다음 우선순위는 출차 중 연속 추적 확보이며, 서로 다른 ID를 무조건 이어 붙이는 변경은 하지 않습니다.

### SPACE 직후 종료 대응 (최신)

18:56~18:58 수동 시험3회 모두 NO_DB_FIXTURE_CREATED/양쪽종료1입니다.
빈 저장사진을 이전 기준과 비교하면 A-03/A-04 점유가 재현됐습니다(변화비율 약0.052~0.056).
empty_start가 빈 기준 불일치에 RuntimeError를 발생시키고 A도 협력 중단시키던 코드를 수정했습니다.
지금은 불일치시 NOT EMPTY 안내와 Q취소를 유지하며 빈 검사 통과 전 DB 준비·전송을 막습니다.
직접 확인한 최신 빈 사진을 별도 empty_reference_20261023_185806.png로 보존하고 템플릿 기준만 갱신했습니다.
기존3개 실제 빈 사진은 새 기준으로 모두4EMPTY, 합성 A-01 가림은 점유로 검사 차단을 확인했습니다.
실카메라 재시험 전이며 카메라는 다시 켜지 않았습니다. 기존 start_e2e.ps1 명령으로 수정 템플릿이 복사됩니다.

### 반복 실행 진입점 정리 (최신)

사용자 직접 실행은 results/camera_layout_checks/parking_recalibration_5190f156/start_e2e.ps1을 사용합니다.
동일 폴더 e2e_template의 5개 파일만 매번 새 회차로 복사하고, 기존 committed/미cleaned 매니페스트 발견 시 시작을 막습니다.
런처 중복 실행은 로컬 mutex로 차단합니다. 수동으로 이전 controller를 직접 실행하는 경우까지 막는 것은 아닙니다.
SPACE 전 관찰·DB 준비 차단, 시험 구획 범위와 소유권 검사 유지. 단계 파일 잠금도 준비 표시로 대기합니다.
실시간 결과 파일 잠금/불완전 JSON은 건너뛰고 다음 주기에 읽습니다. 선택적 DB 조회 실패는 정리를 막지 않습니다.
Python3개/PowerShell 문법검사와 스냅샷·저널5검사를 통과했습니다. 수정 후 실카메라·DB 재시험 전입니다.
새 실행은 카메라·종이 구도가 기준과 같을 때 사용자 본인이 런처로 시작하거나, 준비 확인 후 에이전트가 시작합니다.

### 수동 실행 파일 잠금 오류 복구 (최신)

e2e_manual_47975e24에서 B 원자적 결과파일 교체와 controller 읽기가 겹쳐 PermissionError가 발생했습니다.
A ENTRY APPLIED 이용76 확인. 프로세스 종료 확인 후 DB 조회에서 동일 시험 구획·예약 연결1/버전1을 확인했습니다.
출차는 미확인이므로 전체 성공이 아닙니다. 검증된 시험10행을 정리하고 잔여0/기존이용4건 보존을 확인했습니다.
controller의 실시간 B 스냅샷 읽기는 OSError/불완전 JSON이면 다음 주기에 재시도하도록 수정했습니다.
다른 controller 오류 시에도 중단 플래그와 최대45초 협력 종료 후 기존 소유권 검증 정리 절차로 진입합니다.
사용자 실행 명령의 원본 e2e_guided_bf7abf5c/controller.py도 수정했고 이전 버전은 별도 보존했습니다.
잠금/불완전JSON/정상읽기 모의검사 통과. 수정 후 실카메라 재시험은 아직 하지 않았습니다.

### A 안내 영역 적용 시험 성공 (최신 확인)

사용자가 지정한 재실행 전 gate_guided_d93be2c3/session/summary.json을 직접 확인했습니다.
SPACE 시작 후 121프레임, 기준선 통과1, OCR3표본 모두91소6408, CONFIRMED, review_reasons=[]입니다.
당시 실행 stdout의 방향은 DOWN입니다. summary에는 방향 필드가 없으므로 구분합니다.
HTTP 비활성/시도0, Q 종료, error_type=null, cleanup_errors=0이며 카메라 해제 로그를 확인했습니다.
단독 A의 실제 통과·OCR 확인 성공이며, B 연결·예약·DB 입출차 전체 성공은 아닙니다.
처리 최대1.638초/수집공백1초초과2회가 있으므로 성능 문제가 모두 해소됐다고 보지 않습니다.
뒤에 다시 띄운 gate_guided_3fae3947의 결과와 혼합하지 않습니다.
다음 우선순위는 안내 영역을 두 카메라 시험에도 적용하고, 새 B 기준으로 실제 신원 전달·구획 연결·출차를 확인하는 것입니다.

### A 단독 위치 이력 진단 (최신)

gate_continuity_ae59513b: SPACE 후 210프레임, 관찰209, ID는 모두1, 통과0/OCR0/HTTP0, Q 종료·장치해제 완료.
실제 기록의 번호판 중심 Y=507~702이며 위쪽 확정 조건 Y<500 관찰은0회입니다(선512, 여유12).
따라서 위쪽 최초 위치가 확정되지 않아 통과가 생성되지 않았습니다. 이번 관찰은 ID 단절이 원인이 아닙니다.
관찰 시간 기록으로 기존 LineCrossingCounter를 재생해 통과0을 재확인했습니다. OCR 오류로 분류하지 않습니다.
진단 화면에 위쪽 시작·아래쪽 도착 안내와 여유 경계선을 추가했습니다. 생산 판정 조건은 변경하지 않았습니다.
다음에는 번호판 중심을 위쪽 영역에 충분히 둔 뒤 아래쪽으로 이동하는 A 단독 무전송 확인이 우선입니다.
직전 두 카메라 시험의 원인까지 소급 확정하지 않습니다. 새 촬영은 별도 준비 확인 후 수행합니다.

### 새 구도 전체 시험 결과: A 통과 미발생 (최신)

parking_recalibration_5190f156/e2e_manual_retry는 전체 성공이 아닙니다(success=false).
두 창 SPACE 후 B 네 칸 EMPTY 검사 통과, 합성 준비 4행 생성 후 실행했습니다.
A는 351프레임/번호판 관찰109/기준선 통과0/OCR0/HTTP0, 사용자 Q 종료이며 cleanup_errors=0입니다.
관찰 공백 초기화7회와 최대 처리3.292초가 있으나, 통과 누락의 단일 원인으로 확정하지 않습니다.
B는 A-01 EMPTY→OCCUPIED→EMPTY를 관찰했고 A-04 점유 변동도 있어 실제 안정성은 미완료입니다.
A 입차가 없어 B 신원 EMPTY, 차량 구획 연결0이며 입출차 전체 성공으로 보고하지 않습니다.
시험 소유 행9개 정리 후 잔여0, 기존 이용4건 보존. DB 구조 변경 없음. 두 장치 해제 완료.
다음 최우선은 A 통과 추적 연속성·구도 확인입니다. DB 전체 시험 반복 전 A 단독 무전송으로 통과 근거부터 확보합니다.
카메라 사용은 다시 목적과 방식을 알리고 사용자 준비 답변을 받아야 하며 SPACE 시작을 유지합니다.

### B 카메라 이동 후 재설정 (최신)

SPACE 후 Q로 저장한 parking_recalibration_5190f156/camera_1.png(1280×1024)를 확인했습니다.
손·차량 사진 없이 네 구획이 보이며 새 spaces.json의 네 다각형을 구획 안쪽으로 다시 설정했습니다.
parking_regions_review.png에 좌표를 표시했습니다. 저장 사진 자체 비교는 5회 연속 네 칸 EMPTY입니다.
이는 실시간 흔들림·조명 안정성 검증이 아닙니다. 다음 실행에서도 SPACE 후 빈자리 검사를 유지합니다.
새 준비 경로는 results/camera_layout_checks/parking_recalibration_5190f156/e2e_manual_retry입니다.
이전 e2e_retry_preparation_f19a02d2 실행은 중단됐고 NO_DB_FIXTURE_CREATED이며 두 카메라는 해제됐습니다.
A 카메라 설정은 이전 것을 복사했으며 A 구도가 유지된 경우에만 유효합니다. 새 전체 시험은 아직 실행하지 않았습니다.

### 두 카메라 전체 시연 1차 결과: 부분 성공·정리 완료 (2026-10-23)

camera_e2e_5260f400은전체성공이아닙니다.입차HTTP200/APPLIED(새이용75)와B의동일이용신원수신만성공했습니다.
B는ENTRY_HANDOFF/ACTIVE·OCR0건이지만구획연결요청0건,출차HTTP0건이며최종success=false입니다.
A는411프레임/TIME_LIMIT/입차1건,B는721프레임/COMPLETED로둘다180초기한에종료됐습니다.
B는실제마지막사진이빈장면인데네구획모두OCCUPIED로판정됐습니다.저장사진비교로이전빈기준불일치를재현했습니다.
B의복수점유안전조건때문에AMBIGUOUS_OBSERVATION으로매칭을보류한것입니다.조건을완화해강제연결하지않습니다.
최종DB조회는신규이용1건열림·연결없음·버전0이었고,소유가검증된시험7개행을삭제/커밋한뒤잔여0건을확인했습니다.
기존91소6408의이용4건은보존됐고실제1F-A01은시험전송대상이아닙니다.당해프로세스만A-01→999F-Z01매핑을사용했습니다.
DB구조변경·기존업무행수정·운영설정수정은없습니다.카메라종료와기존기록보존은최종읽기전용조회로재확인합니다.
재시험은e2e_retry_preparation_f19a02d2에준비만했습니다.실행/추가DML/카메라재사용은하지않았습니다.
검증된마지막빈사진을기준으로사용하되실제첫5연속빈관찰을통과해야B의HTTP가시작됩니다.불일치시전송전실패합니다.
A도B빈검사완료전입차전송을차단하며한쪽실패시다른쪽다음카메라읽기전에협력중단합니다.
시험창에WAIT→ENTRY→PARK IN A-01→EXIT→DONE단계를실제검증응답에따라표시하도록준비했습니다.
최대300초이며독립Q종료/사진저장/회차별정리매니페스트를사용합니다.준비코드는문법검사만통과했고아직실카메라검증전입니다.
다음은사용자준비확인후위수정된단계별전체시연을1회진행하는것입니다.성공전에는핵심전체흐름완료로보고하지않습니다.
근거Git제외results/camera_layout_checks/layout_20261023_4ddb9676/camera_e2e_5260f400/http_e2e_result.json,
reference_mismatch_check.json,gate/summary.json,parking/parking_camera_check.json.


### B 카메라 A-01 실제 정차·점유 확인 (2026-10-23)

사용자준비후카메라1/MSMF1280×1024,tracking-target=plate,현재빈기준·spaces.json으로실제관찰했습니다.
parking_observation_aad696f3:476프레임,사용자Q종료(STOPPED),error_type없음,HTTP0회,장치해제·종료사진저장완료입니다.
구획점유는4칸EMPTY확정→A-01만OCCUPIED→사진제거후A-01 EMPTY이며다른3칸의오점유변경은없습니다.
32.765초에LOCAL_SPACE_MATCH:91소6408→A-01이생성됐고62.906초사진제거관찰때MATCH_REVIEW/TRACK_NOT_OBSERVED로철회했습니다.
OCR작업은45개제출/45개완료/미완료0이며일부916408 REVIEW가있지만잘못된유효번호로확정하지않았습니다.
현재연결과종료시관찰연결은모두빈 리스트이며이는사진제거후의정상종료결과입니다.
카메라수집최대공백1.36초/1초초과1회,OCR최대2.63초가관측됐으므로성능문제전체해결로보지않습니다.
이시험은독립OCR의로컬차량·구획연결확인입니다.예약확인/DB반영/A→B신원전달성공이아닙니다.
이로써A입차방향·출차방향과B정차/빈자리복귀를각각실제로확인했습니다. 다음은동일실행의A→B/Boot/DB전체흐름입니다.
실제인쇄번호91소6408의기존업무기록충돌을먼저읽기전용으로확인하고,DB시험행·점유변경·정리범위를실행전에알립니다.
근거Git제외results/camera_layout_checks/layout_20261023_4ddb9676/parking_observation_aad696f3/parking_camera_check.json.


### A 카메라 실제 입차·출차 방향 관찰 확인 (2026-10-23)

현재 A는카메라0/MSMF1280×1024,현재구도gate_config.json,tracking-target=plate입니다.
사용자준비확인후미리보기와동시에관찰했고DB/HTTP는비활성으로유지했습니다.
첫관찰gate_observation_180ca24a:278프레임/통과1건,실행로그DOWN,91소6408표본3개전부일치/CONFIRMED.
두번째gate_exit_observation_6cd3efb5:64프레임/통과1건,실행로그UP,91소6408표본3개전부일치/CONFIRMED.
두실행모두USER_INTERRUPTED(Q),cleanup_errors0,request_attempts0이며종료사진저장·카메라해제를확인했습니다.
이전gate_passage_0a242f0f는SPACE준비단계종료로관찰0프레임이므로통과실패로세지않습니다.
방향은현재summary결과항목에저장되지않고실행stdout에서확인했습니다. 새결과파일을만들어방향을관찰된필드처럼위장하지않습니다.
입차·출차는각각다른실행에서확인한것이며,동일실행의A→B신원전달/DB입출차전체흐름성공을의미하지않습니다.
근거Git제외results/camera_layout_checks/layout_20261023_4ddb9676/ 아래두관찰폴더summary.json,last_frame.png.
B카메라1의빈구획사진과현구도spaces.json은같은상위폴더에준비되어있습니다. 카메라·종이이동시다시대조합니다.
다음최우선은B의실제A-01정차/점유판정확인후두카메라신원전달·실제Boot연결을묶는것입니다.
매촬영준비확인과DB변경내용사전안내규칙은유지합니다.


### 인쇄 사진의 실제 입출차 추적 실패와 명시적 번호판 모드 (2026-10-23)

최종 AI 전체861개 검사 통과(기존검사파일3개에8개추가). 저장실사사진의실제모델검사도별도로통과했습니다.

사용자가 각 카메라 미리보기에서Q로 저장한1280×1024 사진2개를 재사용했습니다. 카메라는 다시 켜지 않았습니다.
일반 recognize_image뿐 아니라 실제 LiveGateProcessor._track도 두 사진에서 차량0건입니다.
기존 번호판 직접 탐지/OCR은 두 사진 모두 첫시도91소6408이며, 기존 번호판 추적은 겹친 상자2개씩이었습니다.
입출차 run_live_gate에 --tracking-target plate를 추가했습니다. 기본 vehicle은 유지합니다.
plate는실제번호판모델/1280추론/클래스무관NMS IoU0.5를 사용하며, 번호판 중심의 실제 기준선 통과를 검사합니다.
OCR은원본상자10%여백을 포함한crop을직접읽고, 표본에 원래번호판탐지점수를보존합니다. 점수는OCR정답확률이아닙니다.
기존다중프레임합의/ROI/속도/시각출처/미확정전송차단은유지합니다. 관찰만으로입출차를만들지않습니다.
plate+원격OCR은미지원이므로카메라를열기전에거절합니다. 독립기본원격OCR/비동기호출계약은변경하지않습니다.
B의plate모드에도같은중복상자억제설정을반영했고vehicle설정은유지했습니다.
실제저장사진의A/B번호판추적은각1개상자이며,A의새crop경로는두사진모두91소6408로읽혔습니다.
단일정지사진이므로실제이동/통과/OCR합의/HTTP/DB성공을뜻하지않습니다.
근거Git제외results/camera_layout_checks/manual_20261023_102773c4/의tracking_path_comparison.json,
plate_gate_option_check.json,parking_plate_nms_check.json. 저장사진을움직임자료로위장하지않았습니다.
다음은B카메라1에서주차구획종이전체와빈장면을확보하고,A카메라0에서번호판이기준선을넘을공간을맞추는것입니다.
촬영은사용자준비확인후독립미리보기/Q저장을사용하며,현재입차/예약업무시험데이터는만들지않았습니다.
운영Python변경3개:recognition/live_gate_processor.py,run_live_gate.py,parking/vehicle_space_tracker.py.
기존검사3개:test_live_gate_processor.py,test_run_live_gate.py,test_vehicle_space_tracker.py. 새검사파일은없습니다.


### 실제 HTTP·인증·공용 DB 왕복 확인 완료 (2026-10-23)

사전 안내 후 합성 차량999하9999와 층999/구역Z/구획01/예약/이용, 총5개 행을 사용했습니다.
HTTP 요청 간 데이터 가시성을 위해 준비4개 행을 커밋했고, 실행 중인 관리자81의 실제 서비스가 이용1개 행을 생성·변경했습니다.
인증 예비 확인: 키 누락3경로401, 정상 키+빈 요청은 입출차/구획400, 해제503(기본 비활성).
AI 운영 VehicleHTTPClient·SpaceMatchHTTPClient로 입차/중복 입차/구획 연결/출차/지연 입차를 실제 전송했습니다.
11개 확인 항목 통과: HTTP200·검증된 응답·동일 이용 ID, DB 독립 조회의 구획/예약 동시 연결과 출차,
지연 ENTRY의HELD/이용 추가0, 마지막 합성 행 정리까지 포함합니다. 버전은입차0→연결1→출차2입니다.
별도JDBC연결에서 데이터 반영을 확인했으므로 이전 단일 트랜잭션 검증과 달리 커밋 가시성도 확인했습니다.
finally에서 소유 ID·표식·차량·입차시각을 확인한 합성5개 행만 삭제/커밋했고 잔여0건을 검증했습니다.
이번에는 시퀀스NEXTVAL5회 사용됐으며 되돌리지 않습니다. 기존 사업장 ID는 참조만 했고 기존 업무 행은 변경하지 않았습니다.
테이블/컬럼/제약/트리거/운영설정 변경, 카메라, 화재 수정, Git 커밋/푸시는 없습니다.
해제503은 활성 해제 성공 검증이 아닙니다. 실제 활성 해제는 앞선 별도 Spring 컨텍스트22개 검사에서만 확인했습니다.
카메라 인식·A→B 실시간 전달·전체 시연·동시 세션 잠금 경쟁·AWS11g는 아직 미검증입니다.
다음 최우선은 사용자 준비 확인 후 실제 한 대 입차→B 정차/예약 구획 연결→출차 시연입니다.
카메라별 용도·배치·동선·시간과 DB 변경/정리 범위를 먼저 설명하고 해당 시점의 준비 답변을 받습니다.
근거 results/shared_db_verification_20261023/http_result.json 및 http_fixture.properties(cleaned=true), 모두Git제외입니다.


### 공용 Oracle 실제 서비스·매퍼 검증 완료 (2026-10-23)

사용자가 공용 DB에서 시험하라고 지시했으며, DDL 여부와 데이터 변경도 먼저 알리라고 요청했습니다.
이후 DB 작업은 기존 업무 데이터 보류 기록만 따르지 말고 이번 허용 범위와 사전 안내 조건을 함께 확인합니다.
이번 범위는 합성 차량999하9999, 층999/구역Z/구획01·02, 예약2개·이용1개를 포함한 총7개 신규 행입니다.
기존 사업장 ID는 FK 참조만 했고, 기존 차량·예약·구획·이용 기록은 수정하지 않았습니다.
테이블·컬럼·제약·트리거 추가/변경 없이 기존 TRG_PUSAGE_LINK_VERSION과 운영 parking-usage.xml을 사용했습니다.
현재 실행 서버에 HTTP 요청을 보내지 않고, 별도 검증용 Spring 컨텍스트에서 실제 서비스 프록시·MyBatis·Oracle을 연결했습니다.
해제 플래그 true는 검증 프로세스에만 주입했으며 운영 파일·실행 서버의 기본 false는 유지합니다.
첫 시도는 검증 컨텍스트의 @Value 기본값 덮어쓰기로 버전 응답 검사에서 중단했고, 해당 합성 행을 모두 롤백·잔여0 확인했습니다.
검증 컨텍스트 설정을 고친 재실행에서 총22개 검사 통과입니다. 운영 Boot 소스 수정은 없었습니다.
정상 입차/중복 입차/예약·구획 동시 연결/동일 연결 유지/오래된 해제 버전 보류/정상 해제/다른 예약 재연결/출차/지연 입차 차단을 확인했습니다.
실제 트리거 버전은0→1→2→3→4이며, 해제 시 구획·예약 둘 다 비고 이용은 미출차로 유지됐습니다.
모든 합성 DML은 하나의 외부 Spring 트랜잭션에서 수행한 뒤 rollback-only로 종료했습니다. COMMIT은 하지 않았습니다.
별도 연결로 합성 이용·예약·층·구역·구획 잔여0을 확인했습니다. 기존 시퀀스 NEXTVAL은 두 시도에서 총14회 사용됐고 롤백되지 않습니다.
이 결과는 실제 SQL·트리거·서비스 트랜잭션 내 동작 검증입니다. HTTP 인증/운영 서버 연결/트랜잭션 간 커밋 가시성/
동시 세션 잠금 경쟁/실제 예외 주입 롤백/카메라 전체 흐름/AWS11g 검증을 대신하지 않습니다.
임시 검증 Java·결과는 Git 제외 results/shared_db_verification_20261023/에 있습니다. 새 운영·테스트 파일은 추가하지 않았습니다.
다음은 실제 HTTP 경로와 AI 응답 처리의 왕복 검증이며, DB 변경 범위를 실행 전에 다시 구체적으로 알립니다.
카메라는 별도 준비 확인 후 사용하며 화재는 기존 제외 범위를 유지합니다.


### 입차 신원 보관과 카메라 가용성 분리 (2026-10-23, PR #82 이후)

검증: 기존 검사 파일2개에 회귀9개를 추가하고 AI 전체853개 통과. B 실행기 정상 출차·수집 종료 경로도 함께 확인했습니다.

A의 정상 입차 응답으로 확인한 차량·이용 ID는 수집 종료 시에도 active에 남깁니다.
업무 상태(status)와 수집 상태(source_status)를 분리하며, 출차가 아닌 종료는 STOPPED로만 기록합니다.
B는 보관된 신원을 진단용 retained_identity로 유지하고, 동일 이용·차량의 검증된 출차일 때만 비웁니다.
단순 EMPTY/다른 이용 출차/파일 손상/소유 실행 변경으로 보관 중인 신원을 지우거나 덮어쓰지 않습니다.
A 신호 만료·정상 종료·차단 상태에서는 read()가 신규 매칭 신원을 반환하지 않습니다.
B 결과의 entry_handoff에 보관 신원과 usable_for_matching을 분리해 기록합니다.
동일 A 실행이 일시 중단 뒤 정상 heartbeat로 돌아오면 기존 신원을 다시 사용할 수 있습니다.
종료한 A 객체는 다시 쓰지 못하며, 새 A 실행이 이전 파일을 자동 인계받는 기능은 구현하지 않았습니다.
300초 촬영 상한과 5초 신규 전송 보호는 유지합니다. 정보 보관과 무중단 자동 전송은 다릅니다.
이미 시작된 HTTP 요청은 취소/롤백하지 않으며, Boot의 기대 이용 ID 조건부 MATCH 계약은 아직 없습니다.
카메라·Boot·DB·화재·Git 스테이징/커밋/푸시는 변경하지 않았습니다.
다음은 승인된 시험 환경의 실제 업무 연동 확인이며, 공용 DB 업무 데이터 시험 보류는 유지합니다.


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
A 종료/손상 파일/다른 실행/5초 heartbeat 만료는 B 신규 신원 사용을 중단합니다. 신원 보관은 위 최신 절을 따릅니다. 새 입차에는 새 정차 근거가 필요합니다.
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
- A는 기존 실행 시간 상한300초 안에서 계속 관찰해야 합니다. A 종료 시에도 보관 신원은 남지만 B 신규 연결은 보류합니다.
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


</details>

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
- `2`: PR 준비까지. 스테이징은 사용자가 명시적으로 요청할 때만 진행합니다. `3`: PR 준비 후 다음 작업.
- 기본 Git 작업 범위는 변경 점검·검사·PR 제목/본문 준비까지입니다. PR 준비 요청만으로 스테이징하지 않습니다.
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

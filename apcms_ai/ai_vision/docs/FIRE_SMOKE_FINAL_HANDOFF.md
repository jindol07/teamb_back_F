# APCMS FIRE/SMOKE 최종 검증 인수인계

## 2026-10-28 최종 두 창·서버 자동 수명주기·AWS 선택 송신 실제 성공

사용자A송신60초준비/전송승인후 final_two_window_aws_lifecycle_20261028 실행.
서버자동주차준비→공유화재A/B→통합두창→A시험전이송신→60초뒤전체정상종료.
A수신93/추론89/의심5건/ACK10개,B수신85/추론69/의심2건/실제송신0.
B양성영상제시는사용자가종료전충분히못했으며이번송신승인범위는A뿐입니다.
네작업모두alive=false/exit_code0,양쪽STOP_REQUESTED/error_type=null/직접카메라개방0,
주차OBSERVE_ONLY/HTTP0,공유TEST_HTTP_ENABLED/send_role=gate.
실제AWS읽기전용대조:이벤트44~53 10개 모두IS_TEST=Y. 이번세션시간대알림22~26
총5개확인. 신규사건12(SMOKE)·13(FIRE) 외 기존미해결사건9·10갱신도포함됩니다.
같은source_group에연결된과거사건/누적알림수를이번신규개수로합산하지않았습니다.
시험기록은DB보존,삭제/구조변경/업무기록임의수정없음. 감지정확도완료주장없음.
테스트result.scope의이전DRY_RUN문구는실행기메타데이터잔재이며 aws_send=true 및
실제ACK·DB근거를우선합니다. 최종요약verified_final_summary.json에명확한범위기록.
코드회귀화재298개/18.797초·Vision1027개/53.643초통과후운영소스수정없음.
근거 result.json,shared_runs/8f2e0cf4f0ab434bbc0530405937dc7b/shared_safety/
gate/fire_alert_sent_state.json 및 results/deployment_audit_20261028/schema_apply/
final_integrated_db_audit.json. 기존동일전이중복방지는직전실제시험에서검증완료.
오늘기능검증의다음단계는실행구성고정/문서·PR준비이며불필요한전체촬영반복은중단합니다.

## 2026-10-28 두 창 자동 수명주기 선택 송신 구현 — 실제 미검증

기본SAFETY_SHARED_SEND_ENABLED=false로DRY-RUN유지. 기존직접화재송신플래그로는
자동활성화되지않습니다. 활성화에는 SAFETY_SHARED_SEND_ENABLED=true,
SAFETY_SHARED_ALLOW_TEST=true, SAFETY_SHARED_ALERT_URL,FIRE_ALERT_TOKEN 필요.
SAFETY_SHARED_SEND_ROLE=gate(기본)/parking/both로역할제한. production입력전송은
새경로에서지원하지않고LiveConfig시험모드만사용합니다. 외부HTTP는기존정확주소예외
SAFETY_TEST_AWS_HTTP=1/SAFETY_CAMERA_SEND_MODE=test조건을그대로사용합니다.
상태API는TEST_HTTP_ENABLED/송신role만표시하며토큰·주소는노출하지않습니다.
공유알림스레드는기존delivery_cycle/ACK/체크포인트/중복코드를재사용합니다.
통신오류는종류만출력하고2초재시도대기,감지는계속유지합니다. 종료직후최종전송이
실패하면작업실패로남겨미전송을성공으로숨기지않습니다. 중단된송신의별도자동복구워커는없음.
추가/수정Python7개: shared_delivery_config.py,shared_alert_loop.py,shared_runtime.py,
shared_runtime_worker.py,test_shared_delivery_config.py,test_shared_alert_loop.py,test_shared_runtime.py.
관련43개검사통과후역할/토큰노출검사추가. 전체회귀진행중. 실제카메라·AWS송신없음.
사용자별도승인전실행금지. 준비실행기 final_two_window_aws_lifecycle_20261028은
A만시험전송/두창/60초관찰/B전송없음/주차전송없음입니다.

## 2026-10-28 A/B 두 창 통합 표시 실제 확인 완료

two_window_preview_20261028/result.json success=true,서버자동준비/90초관찰/자동종료.
사용자가‘두 창에서 함께 보였어’라고주차정보·FIRE/SMOKE박스·표본경과시간표시를확인했습니다.
화재별도창은preview_requested=false/preview_frames0으로비생성. 실제장치는A1/B0두대만소유.
A수신143/추론122/SMOKE2·FIRE2, B수신140/추론112/SMOKE1.
양쪽STOP_REQUESTED/error_type=null/직접카메라개방0,공유결과역할/카메라/현재run_id일치.
로컬알림미리보기A8/B2,실제AWS/DB전송없음. 주차·화재4작업alive=false/종료0.
두창은최근분석결과의비동기표시이며표본시간2초초과박스숨김. 모델오탐해결주장없음.
직전전체회귀화재291개/21.006초·Vision1027개/57.309초통과,그후손상JSON안정성
검사1개추가를포함한표시모듈5개/0.257초통과. 합산하거나최종전체292검사로추정하지않음.
이후소스수정없이실제카메라검증만수행했습니다. 발표기본화면은이두창모드이며
기존네창실행기는개별진단용입니다. 별도실행기의AWS전송성공과서버통합DRY-RUN을구분.
남은범위는자동통합수명주기의AWS전송연결(현재DRY-RUN전용),연기오탐,
배포Compose/Jenkins외부구성확인,프런트위험알림표시(타담당)입니다.

## 2026-10-28 새 배경 시험 결과 및 두 창 통합 표시 구현

gate_background_20261028_121547/live_background_test: 기존모델A1/DSHOW/70초,
TIME_LIMIT/오류없음/프레임2059/추론137/평균28.86ms/읽기실패0.
SMOKE사건1은 휴대전화영상 연기영역 일치(증거직접확인),FIRE3은혼합영상안의작은박스.
배경만으로확정된사건은없지만3.063초SMOKE0.3233/61.469초0.4293의단발전체배경
후보가남았습니다. 배경변경으로모델오탐해결이라고보고하지않습니다. AWS/DB없음.

SAFETY_SHARED_AUTOSTART 경로의 화재전용미리보기는꺼두고주차A/B창에최근분석박스를
표시하도록연결했습니다. 원본/추론/사건판정수정없음. 역할/카메라/run_id/해상도검증,
표본시각2초초과/미래/다른실행/손상/파일잠금이면박스숨김,대기/만료상태표시.
최근분석박스의비동기덧그림으로현재영상과완전동일프레임이라고표현하지않으며
표본경과시간을표시합니다. 직접화재단독CLI의show옵션은유지합니다.
관련60개검사통과(3.811초), 실제두창통합화면은미확인. 카메라추가실행없음.

## 2026-10-28 서버 공유 화재 자동 수명주기 실제 검증 성공

사용자 준비 승인 후 별도8002서버에서 자동주차A/B→현재run_id 공유화재A/B를 기동하고
40초 관찰 뒤 서버종료로 화재→주차 정상정리했습니다. result.success=true.
A53프레임/B54프레임,양쪽STOP_REQUESTED/error_type=null/물리카메라개방0.
화재2개·주차2개 전부alive=false/exit_code0, runtime둘다STOPPED.
AWS/DB전송없음. A정상배경SMOKE사건2건/B0건으로 기존오탐은미해결임도재확인.
근거 results/safety/shared_runtime_lifecycle_20261028/result.json.
기능코드회귀:화재287개/19.636초,Vision1027개/57.816초통과.
이전‘서버단일기동 공유화재수명주기미완료’기록은이번DRY-RUN범위에서해결됐습니다.
공유자동수명주기의실제AWS송신은연결하지않았고기본DRY-RUN입니다.
앞서별도실행기의실시간AWS전송성공과새서버수명주기DRY-RUN성공을구분합니다.
현재시험카메라·서버는모두종료상태이며사용자승인없이자동재시작하지않습니다.

## 2026-10-28 서버 수명주기 공유 화재 DRY-RUN 연결 구현

SAFETY_SHARED_AUTOSTART=true를 명시한 경우에만 주차 준비·현재run_id/역할/카메라ID·
최신프레임을 확인하고 공유 화재A/B 별도프로세스를 시작합니다. 기본false.
SAFETY_CAMERA_AUTOSTART=false 명시필수,활성주차/frame_export_dir필수,직접장치중복우회없음.
상태GET /vision/safety/shared-runtime,delivery=DRY_RUN_NO_HTTP. 키나송신설정이있어도
이 새경로는 실제전송하지 않습니다. 실제전송운영연결은 별도후속이며 기존승인시험과구분.
서버종료시 화재stop_event→사건기록정리/알림미리보기정리→주차종료 순서.
주차준비210초상한/준비식별불일치/작업자종료는FAILED. 자동재시작·신원복원없음.
변경Python6개: safety/shared_runtime.py,shared_runtime_worker.py,live_fire_smoke.py,
parking/parking_runtime.py,tests/safety/test_shared_runtime.py,test_shared_runtime_worker.py.
실제spawn을사용한 모의작업시작/정상종료검사 포함. 실제카메라미실행.
시험설정 results/safety/shared_runtime_lifecycle_20261028/check_lifecycle.py 준비.
별도8002서버로 주차/화재자동준비후40초관찰·자동종료,전송없음,양성정확도시험아님.
새기능실카메라검증전까지운영자동기동완료라고기록하지않습니다.

## 2026-10-28 배포 정적 점검 — 자동 통합 기동 미완료

확인한 현재 소스:
- ai_vision/Dockerfile은 ai_vision.app:app(vision전용)을8000/worker1로 실행합니다.
  ai_vision.app에는 주차 runtime 설치가 있으나 화재 자동감시 router는 없습니다.
- 통합 main:app은 문의/추천/Vision/주차runtime/화재router를 포함합니다.
- camera_monitor_router의 자동화재는 SAFETY_CAMERA_INDEX 한대 직접개방 방식이며
  공유role/run_dir로 A/B화재 소비자를 자동기동하는 코드가 아닙니다.
- 주차config는 이 직접화재장치와 A/B중복을 검증·차단합니다. 충돌검사를 우회하지 않습니다.
- Linux운영에서는 화재자동시작 기본false, 주차도 명시활성설정 필요.
- tracked/hidden 파일검색에서 Compose/Jenkins 정의를 찾지 못했으므로 실제팀배포와
  저장소Vision용Dockerfile을 동일하다고 주장할 수 없습니다.
- Docker빌드에서 models/results는 제외되므로 모델·기준사진·좌표·공유폴더/결과경로를
  외부마운트 또는 별도배포로 제공해야 합니다. UID10001 쓰기권한도 확인해야 합니다.

결론: 실제입출차/주차AWS와 공유화재AWS흐름은 검증됐지만 서버단일기동으로
주차A/B+공유화재A/B가 자동연결되는 운영수명주기는 미완료입니다.
오늘발표용은 검증된별도실행순서를 사용하며 자동운영완료라고 설명하지 않습니다.
다음우리코드핵심은 주차runtime 준비/현재run_id에 맞춘 공유화재소비자 시작과
정상종료/재시작 연결입니다. 배포팀은 수집PC와AWS위치·공유볼륨·모델배치를확정해야합니다.
원격AWS는현장USB를직접볼수없습니다. 현재주차입력은정수카메라번호만지원하므로
RTSP직접수집까지구현돼있다고설명하지않습니다. 오늘정적점검만수행/배포·카메라변경없음.

기준일: 2026-10-28. 발표 전 검증 기준이며 모든 운영 품질의 완성 선언이 아닙니다.
이전 상세 기록은 results/safety/final_document_snapshot_20261028/에 보존했습니다.

## 1. 현재 결론

- 기존 fire_smoke.pt를 유지합니다. 후보 모델·이중 모델은 운영 적용하지 않습니다.
- 주차 A/B 공유 입력 → 기존 YOLO → 사건 → 증거 → 실행 중 AWS 전송 → DB 사건·알림
  저장과 동일 전이 중복 방지를 실제 확인했습니다.
- SMOKE의 회색 벽·손·꺼진 화면 오탐 및 일부 약한 연기 미탐은 미해결입니다.
- 관리자 웹 위험알림 카드는 미연동입니다. 조회 API·DB는 구현됐으나 프런트는 담당자 전달.
- 오늘 추가 학습·후보 탐색은 중단하고 검증한 구성을 고정합니다.

## 2. 실제 구현 기능

웹캠/영상/주차 공유 프레임 입력, FIRE·SMOKE 클래스별 신뢰도 필터, 영역별 연속 감지,
SUSPECTED·ONGOING·CLEARED·REOPENED 상태, 증거 JPG·후보 JSONL·사건 이력,
미리보기·입력 대기/Q 처리, 사전 모델 준비, 카메라 재시도, 제한된 사건 직전 버퍼,
DRY-RUN 알림 미리보기, 선택적 HTTP 전송·응답 검증·재시도·체크포인트·중복 방지.

## 3. 주요 코드 역할과 호출 관계

| 파일 | 역할 |
|---|---|
| live_fire_smoke.py | LiveConfig 검증, detect_frame 추론·박스 추출, run_live 입력/사건/화면/저장 |
| fire_smoke_detector.py | 기본 모델 경로·이미지 분석 관련 기존 코드 |
| fire_event_state.py | 영역 연결, 연속 근거, 사건 상태 전이와 이력 |
| shared_frame_source.py | 공유 프레임을 캡처 형태로 공급, 시각 만료·중복·입력 중단 처리 |
| preroll_buffer.py | 사건 직전 원본 표본의 제한 버퍼 |
| fire_alert_live.py | 감지 프로세스 실행 중 상태 전이 감시, 알림 미리보기/선택 송신 |
| fire_alert_sender.py | payload 정규화·전이 해시·전송 정책·ACK 검증·재시도·송신 상태 |
| parking/frame_exchange.py | 주차에서 확보한 최신 BGR 프레임의 프로세스 간 전달 |
| class_specific_* / run_class_specific_* | 운영 미적용 이중 모델 진단 |
| model_review* / run_model_review.py | 고정 자료 비교·해시 검증 |
| region_review* / run_region_review.py | 수동 영역의 위치 일치와 오탐 영역 비교 |
| raw_review_frames.py / shared_review_probe.py | 시험 원본 제한 저장·감시 읽기 잠금 제한 재시도 |

주차 runtime의 A/B 작업자만 물리 카메라를 엽니다. frame_exchange가 실행별 gate.frame/
parking.frame을 발행하고 화재 SharedFrameCapture가 신원·순번·최신 시각을 확인합니다.
run_live → detect_frame → FireEventStateManager.update → 후보/증거/이력 저장.
fire_alert_live는 이력을 읽어 fire_alert_sender의 payload/정책/송신/ACK 처리를 호출합니다.
Boot 수신부 → AI_DETECTION_EVENT → SAFETY_INCIDENT → NOTIFICATION으로 반영됩니다.
알림은 SAFETY_INCIDENT_ID 기준으로 연결되므로 이벤트ID 직접 조인0건을 알림없음으로
해석하면 안 됩니다.

## 4. 판정과 중복 방지

기본 사건창5회 중3회, 해제3회 미탐지, 영역IoU0.15, cooldown30초를 사용합니다.
실제 시험은 FIRE/SMOKE 신뢰도0.30·입력640·분석간격0.5초입니다.
반복 감지는 순간 오탐을 줄이지만 고정 배경의 지속 오탐을 의미적으로 교정하지 못합니다.
smoke_confirm_conf 선택값은 기본None이며0.55 일괄 적용은 약한 연기 미탐으로 보류했습니다.
송신 transition_id는 세션/사건/영역/상태/프레임/시각으로 만든 SHA256입니다.
성공ACK 확인 후 체크포인트에 기록하며 같은 전이는 서버에서도 중복 방지합니다.
CLEARED는 감지 해제 전이이며 관리자 업무의 사건 해결 처리와 같은 의미가 아닙니다.

## 5. 실제 최종 시험 근거

### 주차

results/parking_demo/aws_20261028/e2e_manual_0e153185/http_e2e_result.json:
입차 → Z02 WRONG_SPACE·DB미연결 → Z01 MATCHED → 출차, 동일 이용ID32,
success=true/완료조건 전부true/LINK_VERSION2. 시험행19개정리·별도조회잔여0.
주차는 한 대 신원전달 모드의 시험이며 다중차량Re-ID를 검증한 것이 아닙니다.

### 화재 기존 모델 DRY-RUN

results/safety/final_baseline_dryrun_20261028:
A 수신209/추론171, SMOKE1·FIRE1; B 수신214/추론167, SMOKE1·FIRE1.
실시간 알림미리보기 각4건. 증거4장 직접 확인, SMOKE 위치는 영상연기와 일치.
불꽃전용 영상은 사용자가 제시 전에 종료돼 이번 신규 시험에서 미실행입니다.
FIRE는 혼합영상 안의 작은 영역이며 모든 박스의 정밀 위치검증을 주장하지 않습니다.

### 화재 실행 중 AWS 전송

results/safety/final_shared_aws_live_20261028:
사용자 승인 A만60초/is_test=true. A수신106/추론87/SUSPECTED7건/전이17건ACK.
전이는 실제 화재17건이라는 뜻이 아니며 반복·해제·재발생·오탐이 포함될 수 있습니다.
B 전송없음. 양쪽TIME_LIMIT/오류없음/직접카메라개방0, 주차STOPPED·작업자종료0.
실제 DB 이벤트27~43 총17개, 연결사건7~11 총5개·관리자알림합계9개 확인.
동일전이 재전송HTTP200/DUPLICATE/이벤트27/사건7/추가알림0/isTest=true 확인.
시험기록은 승인 범위대로 DB에 보존했습니다. 구조·기존업무기록 변경없음.
DB 근거 results/deployment_audit_20261028/schema_apply/fire_live_db_audit.json,
fire_live_incident_audit.json. 중복 근거 duplicate_verification.json.

## 6. 회귀 검사

최신 공식 Vision1027개/57.205초통과: final_vision_regression.log.
최신 화재277개/20.309초통과: final_safety_regression.log.
두 로그는 results/deployment_audit_20261028/에 있습니다. 검사 수를 합산하지 않습니다.
이후 수행한 것은 결과조회·시험실행설정·문서 정리이며 운영소스 변경은 없습니다.
과거 실제서버 호스트잠금과 검사 충돌은 서버 종료 후 별도 재검사로 통과했습니다.

## 7. 오탐 분석과 모델 개선 보류 이유

기존 모델은 회색 배경·정상차량 오탐과 약한연기 미탐이 있습니다.
후보 mfranzon은 고정진단16항목에서 개선된 듯 보였지만 실제 웹캠에서 손0.66,
꺼진 휴대전화0.59 오탐과 실제연기 미탐이 확인됐습니다.
동일원본3장의 수동영역평가: 기존 양성2/2·명시음성0, 후보양성1/2·명시음성2.
자료는 작고 실패분석에 재사용했으므로 일반정확도·독립성능 수치가 아닙니다.
기준상향0.35부터 약한연기사건이 사라지고0.60에서도 손부근사건이 남아 채택하지 않음.
같은 장면 반복검사·도구추가를 인식품질 개선으로 표현하지 않습니다.

## 8. 실제 시연 준비와 검증된 명령

프로젝트 D:\finalProjectB\back\apcms_ai, 가상환경 .venv.
A입출차1번/B주차면0번, USB 재연결 시 번호 재확인. 현재4칸도면 기준/좌표 유지.
동일장치를 사용하는 다른 프로세스는 먼저 종료합니다. 기존시험모드·카메라준비 확인 필요.
주차 AWS 수동시험은 아래 명령으로 실제검증됐습니다. 시험차량/예약/임시구획을
생성·정리하므로 승인된 시험용 범위를 그대로 유지해야 합니다.

```powershell
& 'D:\finalProjectB\back\apcms_ai\ai_vision\run_parking_demo.ps1' `
  -ProfileDir 'D:\finalProjectB\back\apcms_ai\ai_vision\results\parking_demo\aws_20261028' `
  -CameraBackend dshow -HideGuidance
```

공유 프레임이 이미 실행 중인 경우 기존 화재 DRY-RUN 명령은 아래와 같습니다.
현재 실행의 shared_frames/run_id를 입력해야 하며 과거 종료된 폴더를 재사용하지 않습니다.
카메라준비승인 전 자동실행하지 마세요. 두번째 터미널은 role=parking/id=PARKING_B.

```powershell
Set-Location 'D:\finalProjectB\back\apcms_ai'
$run = Read-Host '현재 실행 중인 공유 run_id 폴더 전체 경로'
$role = 'gate'
$id = 'GATE_A'
$out = Join-Path 'ai_vision\results\safety' ('demo_' + $role + '_' + [guid]::NewGuid().ToString('N'))
& .\.venv\Scripts\python.exe -m ai_vision.safety.fire_alert_live --output $out -- `
  --shared-run-dir $run --shared-role $role --shared-camera-id $id `
  --show --fire-conf 0.30 --smoke-conf 0.30 --save-evidence --save-candidates --max-seconds 120
```

혼합영상을 A→B 순서로 보여주고 필요시 화재창Q 종료. 별도 주차 실행도 정상 종료합니다.
기존 최종시험 run_compare.py는 결과폴더 고정의 일회성 실행기이므로 그대로 재실행해
기록을 덮어쓰지 않습니다. 재시험은 신규 결과폴더를 준비해야 합니다.

## 9. AWS 조회와 프런트 전달

배포주소 http://52.79.133.132:3000/admin-api.
GET /api/admin/safety-notifications?limit=30: 관리자JWT로 본인알림조회.
GET /api/admin/safety-incidents: 기존사건조회. 상세조회경로는 코드계약 참고.
배포대시보드 RiskAlertPanel은 placeholder임을 첨부화면과 로컬소스로 확인했습니다.
authFetch로 기존API연결·시험표시·시각·분류·내용·로딩/오류/빈목록 구분은 프런트담당에 전달.
화면 성공으로 보고하지 않으며 프런트소스는 수정하지 않았습니다.

## 10. 자료·학습 준비 상태

원본336장/대표12장검토/정상9·연기존재3, 연기3장의 대략적 박스 기록.
FIRE전체라벨미완료, 같은촬영/같은원본영상이므로 독립학습·평가로 분리하지 않았습니다.
D-Fire 공식연결 Kaggle자료3049605157바이트 다운로드완료, SHA256:
65d81b602991261b47ddc71281e99108362a30336a448e1f8d21352c825c6d83.
직접 압축라벨검사: 이미지21527/라벨21527/빈라벨9838/형식검사거부행26.
클래스0smoke/1fire, train14122/val3099/test4306. 원본을 임의수정하지 않았습니다.
전체이미지해독·실제해시중복·원본세션분할 검증은 미완료. 오늘 학습하지 않습니다.
자료근거 results/safety/dataset_acquisition_20261028/archive_audit.json.

## 11. 발표·면접 설명 핵심

직접 구현한 부분은 YOLO 자체가 아니라 영상 입력·주차프레임 공유·번호판 신원연결,
연속 관찰과 영역별 사건관리, 증거·감사기록, 비동기 이벤트 송신·ACK검증·중복방지,
Boot/Oracle 연동 및 실제 시험도구입니다. 공개학습가중치 활용을 자체모델학습으로
표현하지 않습니다. 오탐 한계와 시험범위를 공개하고 재학습은 후속개선으로 제시합니다.

## 12. Git·보안·남은 작업

커밋/스테이징/푸시 없이 현재 변경을 유지합니다. PR범위는 실제git status/diff로 재확인.
results·가중치·원본영상·압축데이터·.env/토큰을 무분별하게 포함하지 않습니다.
승인받은 시험HTTP 예외는 정확한AWS수신주소+시험모드에만 적용되며 운영용일반우회아님.
실제전송은 매회사용자범위승인 필요. 인증정보는 출력하지 않습니다.
남은항목: 프런트알림연동(타담당), SMOKE인식품질, 장시간자원/끊김·재시작,
최종Compose/Jenkins공유경로·장치권한·모델배치검증, 독립평가자료와학습환경.
현장USB카메라는AWS에서직접접근되지않으므로수집위치·네트워크입력구성을팀과확정해야합니다.
시스템은화재보조감지이며실제소방설비나사람확인을대체하지않습니다.

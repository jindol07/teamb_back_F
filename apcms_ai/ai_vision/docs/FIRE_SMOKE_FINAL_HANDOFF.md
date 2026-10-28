# APCMS FIRE/SMOKE 개발·검증 인수인계

기준일: 2026-10-27. 이 문서는 최신 코드와 검증 근거를 모은 인수인계이며 **모든 운영 검증 완료 선언이 아닙니다.** 미완료 항목을 아래에 명시합니다. 과거 다른 채팅은 코드 수정을 종료했고 이후 화재 개발·검증은 이 채팅이 담당합니다.

## 1. 완성 상태

| 영역 | 상태 | 근거·한계 |
|---|---|---|
| 웹캠/MP4 YOLO FIRE·SMOKE 분석 | 구현·시험 | 실제 양성 휴대전화 영상, 기존 파일 비교. 실물 화재 성능 검증 아님 |
| 주차 A/B 공유 입력·미리보기 | 실제 확인 | A/B 각각 양성 확인, 별도 프로세스, 장치 직접 열기0 |
| 로컬 사건·증거·알림 미리보기 | 실제 확인 | SUSPECTED/CLEARED/REOPENED, JPG/JSON 저장 |
| 공유 사건→AWS→DB 알림 | 승인 범위 확인 | 종료 후 B SUSPECTED2건 송신, STORED→DUPLICATE, DB 사건5·6/알림9·10. 실행 중 자동 AWS 연결은 미검증 |
| 정상 배경 SMOKE 오탐 | 미해결, 개선 후보 분석 | 이번 회색 배경 로그에서 smoke_conf0.55면 사건0. 기본값 변경 안 함 |
| 굴뚝 연기 미탐 | 확인된 제한 | 기존 영상8표본은 0.30에서도 미검출. 전체 영상 평가/재학습 필요 |
| 장시간 운영·CPU/메모리 | 미검증 | 유한 시험 결과를 무기한 운영으로 확대하지 않음 |
| 최종 Compose/Jenkins 배포 | 팀 통합 필요 | 현장 USB 영상은 AWS에서 직접 접근되지 않음 |

## 2. 구현 기능

YOLO 클래스별 탐지·임계값, 영역별 연속 관찰, 중복 영역 연결, 의심·유지·해제·재발·세션종료 이력, 선택 증거/후보/영상/사전 프레임 버퍼, 독립 카메라 재연결, 공유 입력 만료·신원검사·중복 제거, A/B 미리보기·Q 종료, HTTP 송신·재시도·ACK 검증·전이 체크포인트, Spring Boot 사건/알림 저장·중복 방지·관리자 조회/처리 경로가 존재합니다. 별도 리커버리 워커는 사용자 결정으로 제외했습니다.

## 3. 파일 구조

| 파일(ai_vision/safety 기준) | 역할 |
|---|---|
| fire_smoke_detector.py | 이미지 탐지와 화재 모델 경로 |
| live_fire_smoke.py | LiveConfig·detect_frame·run_live·CLI, 영상 수집/분석/증거/GUI |
| fire_event_state.py | FireEventStateManager, 영역 추적과 상태 전이 |
| shared_frame_source.py | SharedFrameCapture, 카메라 없는 공유 파일 캡처 어댑터 |
| fire_alert_live.py | 감지 자식 프로세스와 실시간 전이 감시, DRY-RUN/승인 송신 |
| fire_alert_sender.py | JSON 정규화, 전이 ID, URL/시험정책, 재시도·ACK·체크포인트 |
| camera_monitor_router.py | 통합 FastAPI의 독립 화재 카메라 시작/종료·상태 조회 |
| preroll_buffer.py | 사건 직전 표본의 제한 버퍼와 증거 저장 |
| fire_smoke_batch.py | 라벨 manifest 기반 이미지 비교 |
| apply_shared_fire_input.py | 과거 부분 패치 보조 도구. 현재 코드에 재적용하지 않음 |

공유 송신 모듈은 ai_vision/parking/frame_exchange.py이며 이번 화재 인수 작업에서 주차 운영 소스는 수정하지 않았습니다. tests/safety에 기능별 단위 검사가 있습니다. tests/recognition/test_frame_exchange.py는 양측 실제 파일 계약을 검사합니다.

## 4. 주요 호출 관계

- LiveConfig: CLI 인수→설정 검증. 공유 camera_id/role로 만든 출처 이름도 Boot 문자·길이 규약 검사.
- SharedFrameCapture.read: read_latest→run_id/role/camera_id/sequence 검증→새 프레임 또는 입력 중단. 대기 중 on_wait로 GUI 이벤트 처리. VideoCapture 생성 금지.
- detect_frame: ndarray BGR→YOLO.predict→정상 좌표/점수 검증→FIRE/SMOKE 탐지·추론시간. 후보 기록은 별도 낮은 기준부터 보존.
- FireEventStateManager.update: 시각·프레임번호·탐지목록→영역 연계/시간창→전이 목록.
- run_live: 입력→샘플링→탐지→상태→증거·이력·미리보기→summary. 입력 중단을 CLEARED로 위장하지 않음.
- fire_alert_live.delivery_cycle: 이력 JSON→정규화→DRY-RUN preview 또는 send_pending.
- post_payload: HTTP POST+Bearer+X-Idempotency-Key→상태/ID/isTest/알림수 ACK 검사. 성공 후에만 체크포인트.

## 5. 전체 동작 흐름

현장 주차 A/B의 단일 카메라 소유→원본 BGR 최신파일(카메라별 전달상한2FPS)→화재 프로세스별 SharedFrameCapture→YOLO FIRE/SMOKE→영역별 사건 상태→로컬 이력/증거→Python 송신→AWS 관리자 수신 API→AI_DETECTION_EVENT→조건에 따른 SAFETY_INCIDENT/NOTIFICATION→관리자 JWT 조회·처리.

공유 경로는 <frame_export_dir>/<현재 run_id>/gate.frame 및 parking.frame. 단조 시계가 공유되는 동일 호스트/로컬 볼륨만 지원합니다. 원격 스트리밍 규약이 아닙니다. 상세 바이너리 규격은 FRAME_EXCHANGE_INTERFACE.md를 참고합니다.

## 6. 판정·중복 알고리즘

기본 conf0.20, 시험에서 fire_conf0.30/smoke_conf0.30, interval0.5초, window5/min_hits3, clear_after3, cooldown30초, region_iou0.15, heartbeat10초, max_regions16입니다. 값은 CLI에서 변경 가능하며 2FPS 상한은 실제 최소 입력률 보장이 아닙니다. 상태 판정은 시각과 표본 수의 영향을 받습니다.

동일 종류 박스의 IoU·포함률·중심거리·크기비와 완만한 기준박스 갱신으로 영역 연결을 수행합니다. 사건은 SUSPECTED→ONGOING, 관찰 미검출 때 CLEARED, 조건에 따라 REOPENED를 기록합니다. EOF/입력 손실은 SESSION_ENDED 성격이며 관리자 RESOLVED가 아닙니다.

전이 ID는 시작시각·사건/영역·상태·프레임 등으로 SHA-256 생성합니다. 로컬 체크포인트는 성공 전이만 보관하며 서버는 SOURCE_EVENT_HASH 유일 인덱스로 중복을 막습니다. SOURCE_GROUP_HASH는 출처·위험유형·위치그리드·시험여부로 미해결 사건을 그룹화합니다. 현재 AWS에는 이 그룹 컬럼 대상 인덱스가 없어 동시/대량 처리 성능 검증이 필요합니다.

## 7. 주요 오류와 해결

1. 이전 run의 주차 종료→공유 수신0→imshow 미호출: 최신 run 확인, 초기 대기화면·Q 처리 추가.
2. 매 표본 사이 대기화면이 분석 화면을 덮음: 최근 표본은 유지하고 max_age 초과 때만 대기 표시.
3. A/B 창 구분 불명확: role/camera_id별 제목, preview_frames 등 진단값 추가.
4. Windows 읽기/원자 교체 PermissionError: 이전 주차 작업에서 최대0.2초 제한 재시도. 비원자 덮어쓰기 금지.
5. 공유 source.name의 콜론으로 AWS400: 화재 출처만 parking.PARKING_B 형식으로 수정. Boot 변경 없음. 기존 이력은 원본 보존, 시험 전송용 별도 정규화 자료 생성.
6. CPU부하 중 계약 검사 표본이 만료: 식별자 검사의 유효기간만 분리. 실제 만료 검사 유지.
7. 실제 주차 서버 실행 중 전체검사 잠금 충돌: 사용자 승인으로 카메라 해제·해당 서버 종료 후 재검사.

## 8. 시험 결과와 근거

- 화재 전담 기존 검사213개/27.190초 통과: results/safety/fire_takeover_regression.log.
- 공유 출처 수정 후 화재+프레임 계약226개/48.757초 통과: fire_takeover_final_checks.log. 중복 검사 수를 합산하지 않음.
- 이전 전체1016개 중 환경 충돌 오류1: final_shared_official_regression.log. 사용자 승인으로 주차를 종료한 뒤 **공식1016개/67.494초 전부 통과**: fire_takeover_official_verified.log.
- A 혼합 휴대전화: final_shared_phone_20261027/gate, 수신97/추론72/표시97, SMOKE 의심1·FIRE 의심2, 알림 전이6. B는 수신96/추론92/사건0.
- A 불꽃: final_shared_fire_20261027/gate, 수신73/추론55, FIRE 의심1·전이2. B 수신68/추론61/사건0.
- B 혼합→불꽃: takeover_b_positive_20261027/parking, 수신146/추론141/표시145, SMOKE1·FIRE2 사건, 알림전이5. A 수신155/추론135/사건0. 양쪽 TIME_LIMIT, error_type=null, 장치 개방·재연결0.
- AWS: shared_aws_verification_20261027/normalized_result.json. SMOKE 이벤트10/사건5/알림1, FIRE 이벤트11/사건6/알림1. 동일ID 재전송 DUPLICATE·추가알림0. SQLGate 조회: 사건5·6 DETECTION_COUNT1, IS_TEST=Y, 알림9·10 각1건. 시험행은 보존했고 삭제하지 않음.

위 경로는 모두 ai_vision/results/safety 하위입니다. 검출 신뢰도는 정확도/확률 보장이 아닙니다. 표본 검출률은 사건 recall이나 전체 장면 정답률이 아닙니다.

## 9. 오탐·미탐 분석

사용자 정정: 연기 영상에 실제 작은 불꽃이 포함돼 FIRE/SMOKE 혼합 양성입니다. FIRE 전체를 오탐으로 분류한 이전 해석은 폐기합니다. 증거에서 연기 옆 작은 FIRE 영역도 관찰했으나 모든 표본의 위치 정합성을 수작업 라벨로 확정한 것은 아닙니다.

회색 빈 배경 A265표본 중 SMOKE>=0.30인 표본151개, 점수최대0.7291. 기존 상태기 재생에서 0.30은 의심2/재발12, 0.50도 의심1, **0.55는 의심0**. 혼합 양성은 smoke0.55에서도 SMOKE의심1/FIRE의심2 유지. 이는 한 배경/한 혼합 영상의 저장 로그 비교이며 운영 일반화 근거가 아닙니다.

기존 이미지6장: 정상3장 후보0, 연기2장 최고0.7009/0.8244, 불꽃0.3448. FIRE 임계값까지 함께 올리면 약한 양성을 잃을 수 있어 유지합니다.

영상 균등8표본씩: 숲연기 SMOKE0.30/0.55 모두8/8, 굴뚝연기는 두 기준 모두0/8(기존 모델 미탐), 정상주차0/8, 불꽃 FIRE0.30은7/8. smoke0.55는 **책상 시연용 검토 후보**이며 기본·자동감시 설정에 아직 적용하지 않았습니다.

분석 근거: false_positive_review_20261027/candidate_comparison.json, state_replay.json, still_image_comparison.json, video_sample_comparison.json. 정상 배경을 숨기는 ROI 예외나 검증되지 않은 정적 영상 제거는 추가하지 않았습니다. 확정 개선에는 다양한 연기·정상 라벨 영상과 보류 검증 세트가 필요합니다.

## 10. 시연 준비·PowerShell

카메라 두 대, 기존 도면, FIRE/SMOKE 시험 영상 휴대전화, .venv, 모델·OCR·좌표·빈기준 필요. 실제 불 사용 없음. 준비 확인 후 주차 소유 프로세스만 장치를 엽니다. 독립 화재 자동감시와 동시에 실행하지 않습니다.

주차 공유 설정과 실행은 주차 담당 경로를 사용하며 결과의 현재 run_id를 확인합니다. 자동으로 과거 폴더 중 최신을 추측하지 않습니다. 현재 문서 작성 시에는 사용자 승인으로 주차 시험을 종료했으므로 과거 run 폴더는 모두 새 실행용 경로가 아닙니다.

각 터미널 A/B에서 아래 전체 명령을 사용합니다. 첫 터미널은 role=gate/ID=GATE_A, 두 번째는 role=parking/ID=PARKING_B로 입력합니다. 실제 runtime의 논리 ID가 바뀌면 맞춰야 합니다.

```powershell
Set-Location 'D:\finalProjectB\back\apcms_ai'
$run = Read-Host '현재 실행 중인 shared_frames 아래 run_id 폴더 전체 경로'
$role = Read-Host 'gate 또는 parking'
$id = Read-Host '현재 gate_id 또는 parking_id'
if ($role -notin @('gate','parking')) { throw 'role 오류' }
& .\.venv\Scripts\python.exe -c 'import sys; from pathlib import Path; from ai_vision.parking.frame_exchange import read_latest; p=Path(sys.argv[1])/(sys.argv[2]+".frame"); v=read_latest(p); ok=v is not None and v[0]["camera_id"]==sys.argv[3]; print("FRESH_ID_MATCH:",ok); sys.exit(0 if ok else 1)' $run $role $id
if ($LASTEXITCODE -ne 0) { throw '공유 입력 갱신·현재 run_id·논리 ID를 확인하세요.' }
$out = '.\ai_vision\results\safety\manual_' + $role + '_' + [guid]::NewGuid().ToString('N')
& .\.venv\Scripts\python.exe -m ai_vision.safety.fire_alert_live --output $out -- --shared-run-dir $run --shared-role $role --shared-camera-id $id --show --fire-conf 0.30 --smoke-conf 0.30 --save-evidence --save-candidates --max-seconds 180
```

이 명령은 검증했던0.30 기준의 DRY-RUN입니다. 0.55는 추가 검증 전 임의 기본화하지 않습니다. 대기 화면은 입력 없음, 검출 화면은 실제 분석 박스를 표시합니다. Q는 해당 화재 프로세스만 종료하며 주차를 종료하지 않습니다. 종료 후 summary.json·events.json·incident_history.json·fire_alert_live_preview.json을 확인합니다. 증거 이벤트는 JPG에 박스를 포함합니다.

## 11. AWS 확인·승인

실제 목적지는 기존 팀 시험 예외의 http://52.79.133.132:3000/admin-api/api/parking/ai/fire-alerts 입니다. HTTP 예외는 SAFETY_TEST_AWS_HTTP=1, SAFETY_CAMERA_SEND_MODE=test, 정확한 목적지, is_test=true의 조합만 허용합니다. 주소를 실제 배포 주소로 단정하지 말고 변경 시 재확인합니다. API 키는 .env FIRE_ALERT_TOKEN에 보관하며 채팅/명령/로그에 출력하지 않습니다.

관리자 조회: GET /admin-api/api/admin/safety-notifications?limit=30, 관리자 Bearer JWT 필요. FireSafetyAdminInteractionController의 사건 상세/본인 알림 처리도 존재하나 이번 인수의 실제 인증 API 재검증은 미완료입니다. DB 직접 조회와 API ACK로 확인한 결과를 관리자 화면에서 확인했다고 표현하지 않습니다. 향후 send 옵션은 실행별 사용자 승인이 필요하며 이번 승인은 위 두 시험사건에 한합니다.

## 12. Git·충돌 주의

현재 feature/ai-vision-parking-runtime의 upstream은 gone입니다. 기존 주차 변경과 화재 담당의 공유 입력 변경이 함께 미커밋 상태입니다. reset/checkout/stash/스테이징/커밋/푸시/PR을 수행하지 않았습니다.

이번 화재 인수의 운영 변경: safety/live_fire_smoke.py(출처형식·사전검증), 앞선 공유 미리보기 변경은 shared_frame_source.py와 tests/safety/test_live_fire_smoke.py·test_shared_frame_source.py. tests/recognition/test_frame_exchange.py는 양쪽 계약 확인 및 기대 출처 변경. 기존 주차 작업의 frame_exchange/runtime 변경과 구분해야 합니다. live_fire_smoke.py는 다른 담당의 미커밋 공유 입력까지 포함하므로 전체 diff를 이번 단독 작성으로 주장하지 않습니다.

미추적 패치도구/apply_shared_fire_input.py·new_files·중복 패치·README_적용및시연.md는 팀원 제공 원본이므로 임의 삭제/중복 적용하지 않습니다. 모델·영상·.env·results는 PR에 무분별하게 포함하지 않습니다. Git 올리기 전 최신 develop 충돌 점검과 파일 범위 확정이 필요합니다.

## 13. 발표·면접용 핵심

단일 카메라 수집과 분리된 AI 소비자를 파일 기반 최신 표본 계약으로 연결해 장치 충돌을 막았습니다. 클래스 탐지와 사건 상태기를 분리하고, 관찰 해제와 관리자 업무 해결을 구분했습니다. 전이 식별자·로컬 성공 체크포인트·서버 유일키로 재시도 시 중복 사건/알림을 막으며, 2xx만이 아니라 ACK 의미를 확인합니다. GUI 무표시 문제를 수신0과 렌더링 미진입으로 분리해 원인을 확인했고, 정상/양성 로그 비교로 오탐 보완의 손실을 함께 평가했습니다. 기존 라이브러리 사용과 직접 작성한 통합/검증 로직을 구분해 설명합니다.

## 14. 보안·운영 한계와 다음 우선순위

실제 소방 설비나 현장 확인을 대체하지 않습니다. confidence는 확정 확률이 아닙니다. 현장 영상·번호판·키는 접근 통제하고 결과 보존 정책을 정해야 합니다. 로컬 HTTP 시험 예외를 일반 외부 전송 우회로 확장하지 않습니다. 무기한 실행·장시간 부하·재시작 신원 복원·최종 CI/CD는 미검증입니다.

다음 순서: (1) 전체검사 단독1016개 통과 확정 (2) smoke0.55 후보를 정상/다양한 연기/혼합 사례에서 검증하고 승인된 시연 설정만 조정 (3) 추가 승인 후 새 공유 입력의 실행 중 AWS 자동 전송 검증 (4) 인증된 관리자 API·실제 화면 조회 (5) 장시간 자원·중단/재시작 시험과 최종 시연. 어느 하나도 수행하지 않고 완료로 바꾸지 않습니다.

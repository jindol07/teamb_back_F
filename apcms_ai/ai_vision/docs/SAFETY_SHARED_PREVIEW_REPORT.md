# 화재·연기 공유 프레임 미리보기 통합 시험 보고서

작성일: 2026-10-27 / 범위: Windows 로컬 A/B 공유 입력, 실제 화재 모델, DRY-RUN. AWS 전송·DB 변경 없음.

## 결론

공유 입력 미리보기·실제 분석 박스·A/B 동시 실행·로컬 알림 미리보기 경로는 확인했습니다. A 카메라에 보여준 휴대전화 연기 영상에서 SMOKE, 불꽃 영상에서 FIRE 의심 사건이 생성됐습니다. 빈 배경 SMOKE 오탐이 남아 있어 오탐까지 해결된 운영 완료 상태는 아닙니다.

## 창이 안 보였던 원인

기존 경로 d118d21d593546a18747a9b4838eafa8의 주차 runtime은 FAILED/CHILD_EXITED였고 두 작업이 종료돼 공유 파일이 갱신되지 않았습니다. 기존 실패 5회(shared_smoke_demo_20261027_161510/161600/161722/162128/162253)는 모두 SHARED_INPUT_UNAVAILABLE·수신0·추론0입니다. 기존 imshow는 유효한 첫 프레임을 받은 뒤에만 호출됐으므로 show 옵션이 있어도 창이 생성되지 않았습니다. OpenCV4.10.0은 WIN32UI 지원으로 확인했습니다. 이전 주차 작업이 종료된 근본 원인은 이번 화재 수정 범위에서 해결한 것이 아닙니다.

## 수정한 파일

- ai_vision/safety/live_fire_smoke.py: 공유 입력 0장에서도 대기 화면 표시, 대기 중 GUI 이벤트/Q 처리, A/B 논리 ID가 다른 창 제목, 실제 표시 횟수 진단 필드 추가. 새 표본 사이에는 마지막 분석 화면 유지, shared_max_age 초과 시에만 대기 표시.
- ai_vision/safety/shared_frame_source.py: 선택 on_wait 콜백으로 입력 대기 중 GUI 이벤트 처리·사용자 취소 전달. 카메라 직접 접근/재연결 없음.
- ai_vision/tests/safety/test_live_fire_smoke.py: 대기 창·Q·실제 분석 박스 전달·프레임 사이 화면 유지 검사.
- ai_vision/tests/safety/test_shared_frame_source.py: 대기 콜백·중복 입력 중 GUI 처리 검사.
- ai_vision/tests/recognition/test_frame_exchange.py: 기존 식별자 검사가 CPU 부하로 표본 만료 검사가 되지 않도록 해당 검사만 reader의 유효기간30초 사용. 별도 실제 만료 검사는 유지. 주차 인식·점유 기능 소스 변경 없음.

수정 직전 화재 소스 원본은 results/safety/preview_fix_backup/20261027_163120에 보존했습니다. 다른 담당의 기존 공유 입력 구현 위에 필요한 부분만 수정했고 패치 ZIP을 재적용하지 않았습니다.

## 실제 시험 결과

새 공유 run_id: 79defd4cf505424fb83e64588dcdeb4a
공유 폴더: D:\finalProjectB\back\apcms_ai\ai_vision\results\parking_runtime\calibrated_20261027_105910\shared_frames\79defd4cf505424fb83e64588dcdeb4a
A: gate.frame / GATE_A / 640×480. B: parking.frame / PARKING_B / 1280×1024.

| 실행 | A 수신/추론/표시 | B 수신/추론/표시 | 종료 | 확인 |
|---|---|---|---|---|
| final_shared_preview_20261027 | 305/265/304 | 281/271/280 | 양쪽 TIME_LIMIT | 최초 창 생성 확인. A의 빈 배경 SMOKE 오탐2건, 알림 미리보기28개. 표본 사이 대기 화면 삽입 현상은 이후 수정 |
| final_shared_phone_20261027 | 97/72/97 | 96/92/96 | 양쪽 USER_INTERRUPTED(Q) | 수정 후 휴대전화 연기 SMOKE 박스 직접 확인(실시간0.89, 사건 증거0.83). A 의심3건은 SMOKE1·FIRE2로 혼합 양성 영상의 동시 감지 포함(사용자 확인, 개별 FIRE 위치 정합성은 추가 검토). 미리보기6개 |
| final_shared_fire_20261027 | 73/55/73 | 68/61/68 | 양쪽 USER_INTERRUPTED(Q) | 휴대전화 불꽃 FIRE 박스0.68 증거 확인. A FIRE 의심1건·해제1건, 미리보기2개 |

모든 실행에서 camera_open_attempts=0, camera_reconnect_attempts=0, error_type=null입니다. 화재 프로세스가 물리 카메라를 중복으로 열지 않았습니다. B는 도면 관찰이며 FIRE/SMOKE 사건0건입니다. B에 별도 양성 영상을 보여준 시험은 하지 않았습니다. 모든 명령에서 send 옵션을 생략했고 실제 송신 상태 파일은 생성되지 않았습니다. 화재는 기존 로컬 알림 미리보기만 생성했습니다.

원본 근거는 results/safety/<위 실행명>/<gate 또는 parking>/summary.json, incident_history.json, detection_candidates.jsonl, fire_alert_live_preview.json, annotated.mp4와 event_*.jpg입니다. 알림 개수는 상태 전이 건수이며 별도 화재 사건 수가 아닙니다. annotated.mp4의 고정 인코딩 FPS는 관찰 실제 FPS와 다르므로 영상 길이를 관찰 시간으로 해석하지 않습니다.

## 회귀 검사

입력 대기/취소/화재 기존 실행/알림/공유 계약 검사71개, 18.613초 통과. 로그 results/safety/shared_preview_final_checks_verified.log. 이전 부하 중 고정3초 표본의 만료 때문에 식별자 검사1건이 실패한 로그도 보존하고, 해당 검사의 목적을 분리한 뒤 재검사했습니다. 임계값·상태 판정·모델 가중치는 변경하지 않았습니다.

추가 Vision 공식 묶음1016개/101.200초에서는 실패0·오류1입니다. test_real_spawn_lifecycle_and_duplicate_host_lock이 실행 중인 실제 주차 서버의 호스트 잠금(47631)과 충돌해 새 시험 runtime을 시작하지 못했습니다. 나머지1015개는 통과했으나 전체 성공으로 보고하지 않습니다. 주차 서버를 유지해야 하므로 이 단독 실행 검사는 종료 후 재검증할 항목으로 남깁니다. 로그 results/safety/final_shared_official_regression.log. 이전 공식1016개 통과는 실제 주차 서버 실행 전 결과이며 이번 결과와 구분합니다.

## 남은 문제와 검증 경계

1. 빈 회색 배경의 SMOKE 오탐. 연기 영상은 실제 작은 불꽃이 포함된 혼합 양성이므로 FIRE를 오탐으로 단정하지 않습니다. 임계값을 임의 변경하지 않았으며 별도 정상/화재/연기 검증 세트로 조정해야 합니다.
2. B 카메라에서 양성 FIRE/SMOKE 실제 시연은 미검증. 두 소비자 동시 관찰과 B 원본 표시만 확인했습니다.
3. 장시간 주차 송신 종료 시 소비자 입력이 사라집니다. 현재 run_id·runtime RUNNING·파일 갱신 확인이 필수입니다. 이번 작업에서 주차 장애 복구 기능은 변경하지 않았습니다.
4. AWS 실제 전송, 실물 화재/연기 성능, 장시간 운영, Docker Compose/Jenkins 최종 배포 검증은 이번 시험에 포함하지 않았습니다.

## 직접 실행하는 PowerShell 명령

현재 주차 공유 실행이 유지될 때만 아래 run 경로가 유효합니다. 다음 주차 실행은 새 run_id로 바뀌므로 현재 경로를 다시 확인하세요. 아래 명령은 카메라를 직접 열거나 주차 서버를 시작하지 않습니다.

터미널 A:

```powershell
Set-Location 'D:\finalProjectB\back\apcms_ai'
$run = 'D:\finalProjectB\back\apcms_ai\ai_vision\results\parking_runtime\calibrated_20261027_105910\shared_frames\79defd4cf505424fb83e64588dcdeb4a'
& .\.venv\Scripts\python.exe -c 'import sys; from pathlib import Path; from ai_vision.parking.frame_exchange import read_latest; ok=all(read_latest(Path(sys.argv[1])/(r+".frame")) is not None for r in ("gate","parking")); print("FRESH_FRAMES:",ok); sys.exit(0 if ok else 1)' $run
if ($LASTEXITCODE -ne 0) { throw '최신 공유 프레임이 없습니다. 현재 주차 실행과 run_id를 확인하세요.' }
$out = '.\ai_vision\results\safety\manual_gate_' + [guid]::NewGuid().ToString('N')
& .\.venv\Scripts\python.exe -m ai_vision.safety.fire_alert_live --output $out -- --shared-run-dir $run --shared-role gate --shared-camera-id GATE_A --show --fire-conf 0.30 --smoke-conf 0.30 --save-evidence --save-candidates --max-seconds 180
```

터미널 B(터미널 A와 동일한 현재 run 경로 사용):

```powershell
Set-Location 'D:\finalProjectB\back\apcms_ai'
$run = 'D:\finalProjectB\back\apcms_ai\ai_vision\results\parking_runtime\calibrated_20261027_105910\shared_frames\79defd4cf505424fb83e64588dcdeb4a'
$out = '.\ai_vision\results\safety\manual_parking_' + [guid]::NewGuid().ToString('N')
& .\.venv\Scripts\python.exe -m ai_vision.safety.fire_alert_live --output $out -- --shared-run-dir $run --shared-role parking --shared-camera-id PARKING_B --show --fire-conf 0.30 --smoke-conf 0.30 --save-evidence --save-candidates --max-seconds 180
```

각 화재 창 Q는 해당 화재 감지기만 종료합니다. 주차 창은 유지합니다. 종료 후 summary.json의 preview_frames·수신/추론 횟수·error_type과 로컬 알림 미리보기를 확인하세요. 독립 화재 카메라 자동감시를 동시에 실행하거나 send 옵션을 추가하지 않습니다. 창이 대기 상태면 입력 갱신과 run_id부터 확인합니다.

## 종료 시 상태

화재 A/B 시험 프로세스는 모두 Q로 종료됐습니다. 주차 전용 서버20872(이번 직접 실행), 포트8002와 공유 run79defd4cf505424fb83e64588dcdeb4a는 RUNNING/두 파일 FRESH로 확인해 유지했습니다. 다음 촬영 전 현재 상태를 다시 확인해야 하며 단순 문서의 경로를 현재 실행으로 가정하지 않습니다. 스테이징·커밋·푸시 없음.

## 인수 후 최신 결과 (2026-10-27)

이 문서 이후 화재 전체 개발을 이 채팅이 인수했습니다. 최신 종합 기록은 FIRE_SMOKE_FINAL_HANDOFF.md입니다. 사용자 확인으로 연기 영상은 혼합 양성이며 FIRE 전체를 오탐으로 분류하지 않습니다. B 양성 시험(SMOKE0.83/FIRE0.76) 완료, 공유 사건의 source.name 콜론이 Boot 규약과 불일치해 점으로 수정한 후 승인된2건 AWS전송/중복/DB알림 확인 완료. 주차는 사용자 승인으로 Q종료 후 카메라두작업exit0·dead 확인, 해당시험서버20872만 정리했습니다. Q로작업종료하면 runtime기록은 CHILD_EXITED/FAILED로 남는 기존 동작이며 화재 오류로 분류하지 않습니다. 단독 공식1016개/67.494초 모두통과로 이전잠금환경오류 재검증완료. 현재 카메라/공유서버 실행없음. 옛run폴더 재사용금지.

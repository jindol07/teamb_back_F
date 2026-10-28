# APCMS FIRE/SMOKE 최종 검증 인수인계

## 2026-10-28 자유 주차 실제 AWS 결과 및 종료 오류 수정

- 실행: `results/deployed_integration/f9c98c287eaa44ab919de2163d9bf4c3`.
- 예약 28 / 이용 39. A02→A04→A03→A01 실제 위치 연결 4회와 이전 칸 해제 4회 응답 검증. A01은 MATCHED, 나머지는 WRONG_SPACE.
- AWS 읽기 전용 재조회: 이용 39 출차 완료·연결 NULL·LINK_VERSION=9, 예약 28 CANCELLED. 화재 시험 전이 151~154 네 건 저장, 관련 사건 6·13과 관리자 알림 존재(알림 총수는 이번 신규 생성 수를 의미하지 않음).
- 카메라 PID와 공유 run_id는 주차부터 화재까지 유지. 화재 A/B 작업자는 종료 코드 0.
- 전체 성공 아님: B 주차 작업자 종료 코드 1 / DELIVERY_STOPPED. 화재 단계에서 송신을 중단한 점유 이벤트가 큐에 남아 close에서 실패로 처리됨. 부모 성공 판정이 이를 놓쳤음.
- 수정: 송신 중단 이후 점유 이벤트는 큐에 넣지 않고 PARKING_PHASE_COMPLETE로 기록. 정상 의도 취소는 검토 대상에서 제외. 런타임과 최종 결과는 작업자 종료 코드·개별 결과까지 검사.
- 원본 결과는 result.before_shutdown_validation.json에 보존하고 result.json은 FAILED로 정정. DB 시험 기록 삭제·추가 변경 없음.
- 수정 후 관련 검사 65개 통과, 전체 Vision 검사 1086개 / 56.963초 통과. 근거: results/verification_tmp/shutdown_validation_vision.log.
- 수정된 종료 경로의 실제 카메라 재시험은 미실행. 따라서 정상 종료까지 최종 완료로 표시하지 않음. 실행 명령은 기존 run_deployed_free_parking.ps1 유지.


## 최신 상태 — 2026-10-28 PR121 주차 계약 반영

AI와 세 통합 시험을 최신 실제 위치 연결 정책으로 수정했습니다.
배포 해제 API 활성 응답(400 검증 단계 도달)을 확인했고 사용자가 설정 추가를 알렸습니다.
최신 정책의 실제 카메라/AWS 업무 경로는 이용39로 확인했습니다. 종료 오류가 발견되어 수정 후 실제 종료 재확인이 남았습니다.
기존 ‘A01만 연결하고 출차까지 유지’ 및 ‘다른 자리/무예약은 위치 미연결’ 설명은 현재 정책이 아닙니다.
Boot Java·매퍼·DB 구조를 수정하지 않았습니다. 기존 해제 API 실행 옵션만 필요합니다.
화재 모델과 화재 전송 코드는 이번 주차 계약 변경에서 수정하지 않았습니다.

## 1. 현재 결론

- 주차는 최신 PR121 정책을 따릅니다. 실제 위치 연결과 예약 판정을 분리합니다.
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
| shared_runtime.py / shared_runtime_worker.py | 서버 수명주기에서 A/B 화재 작업자 시작·종료 |
| shared_delivery_config.py / shared_alert_loop.py | 승인된 역할만 시험 송신·전송 상태 관리 |
| preview_overlay.py | 신원·시각이 맞는 최신 감지 결과를 주차 두 창에 표시 |
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
서버 통합 모드는 shared_alert_loop가 이력을 읽어 fire_alert_sender의 payload/정책/송신/ACK 처리를 호출합니다.
독립 실행 모드는 fire_alert_live를 사용합니다.
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

## 5. 실제 시험 근거와 현재 한계

주차의 과거 임시 구획 시험과 실제 구획 이용34/예약22는 당시 구 계약에서 성공했습니다.
최신 PR121 이후 이용38/예약26은 A02 WRONG_SPACE+PROCESSED로 실제 위치가 연결됐으나,
구 AI 계약과 충돌해 중단됐습니다. 해당 이용은 소유 확인 후 출차 정리하고 예약 취소,
구획 상태 복원을 확인했습니다. 이를 최신 정책 통합 성공으로 소개하지 않습니다.
새 AI는 저장된 사건130의 응답 형태를 재구성한 오프라인 재현에서 APPLIED+WRONG_SPACE로 처리합니다.
원본 HTTP 응답을 캡처한 자료는 아니며 실제 재전송은 하지 않았습니다.
최신 정책의 카메라→AWS 전체 경로는 배포 해제 활성화 후 재시험해야 합니다.

화재의 기존 실제 A/B 통합 시험은 results/safety/aws_both_retained_20261028/result.json.
A 전이14건·B6건 ACK와 AWS 이벤트62~81 총20행 IS_TEST=Y를 대조했습니다.
연결 사건과 관리자 알림 존재 확인, 네 작업자 종료0, 공유 화재 물리 카메라 개방0회.
이 기록은 보존되어 있습니다. 전이20건은 실제 화재20건이나 인식 정확도를 뜻하지 않습니다.
과거 동일 전이 재전송은 DUPLICATE·추가 알림0으로 검증했습니다.

## 6. 회귀 검사

최신 전체 Vision1,083개(55.036초) 통과: observed_position_policy_complete_vision.log.
추가 전용 검사와 세 실행기의 CheckOnly·Java컴파일도 통과했습니다.
추가 근거: 실제 로컬 HTTP로 오주차 연결→해제→예약 자리 연결, 무예약 연결→해제→다음 위치,
입차 신원 전달과 버전 보호 해제의 모의 카메라 결합을 검증했습니다.
구형 실제 모델 실험 test_fire_smoke.py는 회귀 수집 대상이 아닙니다.
카메라·AWS 실제 이벤트 전송 검증과 단위/로컬 HTTP 검증을 구분합니다.

## 7. 오탐 분석과 모델 개선 보류 이유

기존 모델은 회색 배경·정상차량 오탐과 약한연기 미탐이 있습니다.
후보 mfranzon은 고정진단16항목에서 개선된 듯 보였지만 실제 웹캠에서 손0.66,
꺼진 휴대전화0.59 오탐과 실제연기 미탐이 확인됐습니다.
동일원본3장의 수동영역평가: 기존 양성2/2·명시음성0, 후보양성1/2·명시음성2.
자료는 작고 실패분석에 재사용했으므로 일반정확도·독립성능 수치가 아닙니다.
기준상향0.35부터 약한연기사건이 사라지고0.60에서도 손부근사건이 남아 채택하지 않음.
같은 장면 반복검사·도구추가를 인식품질 개선으로 표현하지 않습니다.

## 8. 실제 시연 준비와 명령

A입출차1번/B주차면0번, 기존4칸종이의 기준사진·좌표 유지. 실제 매핑은 지하3층 A01~A04,
서버 코드3F-A01~A04/DB ID46~49입니다. 세 시험 모두 네 칸 점유를 전송합니다.
카메라는 이 PC에서 수집하며 주차·화재 이벤트를 배포 API로 전송합니다.
다른 카메라 사용 창을 종료하고 두 화면을 빈 상태로 준비해야 합니다.

필수 배포 설정: 관리자 Boot 실행 인자 --parking.ai.space-release-enabled=true 및 재시작.
이 기능은 이전 구획 연결만 해제하며 입차는 유지합니다. 실제 출차·기록 삭제와 다릅니다.
자동 실행 전 잘못된 형식 요청으로 기능 활성 여부를 확인합니다. 503/인증·연결 문제면
예약·카메라 시작 전 BLOCKED로 보류합니다. 이 형식 검사 요청은 DB를 갱신할 수 없습니다.
설정 확인만 할 때:
```powershell
Set-Location 'D:\finalProjectB\back\apcms_ai'
& '.\.venv\Scripts\python.exe' -m ai_vision.parking.demo_tools.release_capability
```

예약 A01·고정 순서(A02→A01):
```powershell
& 'D:\finalProjectB\back\apcms_ai\ai_vision\run_deployed_integration.ps1'
```
예약 없이 동일 이동:
```powershell
& 'D:\finalProjectB\back\apcms_ai\ai_vision\run_deployed_no_reservation.ps1'
```
예약 A01·네 칸 자유 순서:
```powershell
& 'D:\finalProjectB\back\apcms_ai\ai_vision\run_deployed_free_parking.ps1'
```
세 명령은 --check-only가 아닌 실제 실행에서 시험 차량/예약/이용/이력·알림을 AWS에 반영합니다.
SPACE 없이 자동 준비 후 창 제목 PHASE를 따릅니다. 고정 순서는 입차→A02→A01→출차,
자유 순서는 입차→네 칸 자유 관찰→원할 때 출차입니다. 칸마다 손을 치우고 정차 확정을 기다립니다.
이동 시 이전 칸의 EMPTY·점유 전송 완료·연결 버전을 확인해 해제한 뒤 새 위치에 연결합니다.
같은 입차 이용 ID를 유지하며 오주차는 WRONG_SPACE, 무예약은 NO_VALID_RESERVATION,
예약 자리 일치는 MATCHED로 표시합니다. 위치 연결 성공을 정상 예약 주차와 혼동하지 않습니다.
A01을 방문했어도 그 연결을 고정하지 않습니다. 다른 칸으로 이동하면 해제·재연결합니다.
출차 후 두 카메라/창을 계속 유지하고 주차 송신만 멈춘 다음 FIRE_A→FIRE_B→DONE입니다.
각 불꽃 단계는 새 FIRE SUSPECTED 전송 ACK가 있어야 진행하며 단계별120초 제한입니다.

Ctrl+C는 시험 취소입니다. 소유 파일·검증 입차 근거가 맞는 시험 이용/예약/점유만 정리합니다.
다른 업무 기록·관리자 변경은 자동 정리하지 않습니다. 정리 실패 시 다음 시작에서 복구하며
소유 불명 충돌은 이용ID를 안내하고 보류합니다. 시험 이력 자체는 별도 삭제 요청 전까지 보존합니다.
기본 설정은 results/parking_runtime/demo_current_20261028/runtime.local.json.
results와 모델·인증키는 Git 제외이므로 다른 PC의 운영 준비에는 별도 파일 배치가 필요합니다.

## 9. AWS 조회와 프런트 전달

배포주소 http://52.79.133.132:3000/admin-api.
GET /api/admin/safety-notifications?limit=30: 관리자JWT로 본인알림조회.
GET /api/admin/safety-incidents: 기존사건조회. 상세조회경로는 코드계약 참고.
이전 확인 당시 배포대시보드 RiskAlertPanel은 placeholder였습니다. 현재 웹 표시 자체는 재검증하지 않았습니다.
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

# 연기 오탐 개선 후보 — 2026-10-27

> 후속 영상 검증에서 0.55 확정 조건이 약한 연기 사건을 차단했습니다.
> 일반 운영 적용은 보류하며 기본 None을 유지합니다. 추가 637회 실제 추론 결과와
> 해상도 비교는 SMOKE_VIDEO_VALIDATION.md를 우선 참고하세요.

## 적용 범위

`live_fire_smoke --smoke-confirm-conf 0.55`는 새 SMOKE 사건과 재발생을 확정하는
관찰 횟수에만 적용합니다. FIRE와 기존 SMOKE 탐지 기준은 변경하지 않습니다.
기본값 None이므로 기존 실행은 그대로입니다. 카메라 실행·AWS 전송은 하지 않았습니다.

탐지 기준 이상이지만 확정 기준 미만인 SMOKE도 화면·후보 기록·영역 추적에 남습니다.
새 사건은 최근 관찰 창 안에서 확정 기준 이상의 관찰이 min_hits번 필요합니다.
진행 중 사건은 약한 관찰이 이어져도 유지되며, 기존 clear_after 연속 미탐지 조건으로
종료합니다. 재발생에는 다시 강한 연속 근거가 필요합니다. 약한 오탐이 이미 시작된
사건을 오래 유지할 가능성도 있으므로 장시간 음성 영상 검증이 필요합니다.

## 저장 자료 재생 결과

실제 FireEventStateManager에 기존 후보 로그를 입력한 결과입니다. YOLO 재추론이나
새로운 촬영 검증이 아니며 동일 자료를 이용한 후보 선정·재평가입니다.

| 자료 | 기존 신규/재발생 | 후보 신규/재발생 |
|---|---|---|
| A 회색 배경 | SMOKE 2/12 | SMOKE 0/0 |
| A 혼합 영상 | SMOKE 1/0, FIRE 2/0 | 동일 |
| A 불꽃 영상 | FIRE 1/0 | 동일 |
| B 시험 중 A 배경 | 0 | 0 |
| B 양성 영상 | SMOKE 1/0, FIRE 2/0 | 동일 |

양성 자료의 유지·해제 전이 수도 동일했습니다. 최초 발생 시각은 달라질 수 있습니다.
근거: results/safety/false_positive_review_20261027/confirmation_gate_replay.json.
기존 굴뚝 연기 영상 8개 표본 미탐지는 해결하지 못했습니다. 일반적인 정확도나
미탐률을 이 자료만으로 계산할 수 없습니다. 따라서 운영 기본값을 올리지 않습니다.

## 재현 방법

apcms_ai 폴더에서 실행합니다. 아래는 저장 로그만 읽습니다.

```powershell
.\.venv\Scripts\python.exe -m ai_vision.safety.replay_fire_candidates `
  ai_vision/results/safety/final_shared_preview_20261027/gate/detection_candidates.jsonl `
  ai_vision/results/safety/takeover_b_positive_20261027/parking/detection_candidates.jsonl `
  --smoke-confirm-conf 0.55 `
  --output ai_vision/results/safety/false_positive_review_20261027/recheck.json
```

직접 live_fire_smoke를 실행할 때만 새 옵션을 지정합니다. 기존 런처·자동 감시의
설정으로 자동 전파하지 않았습니다. 실제 카메라 시험은 준비 확인 후 진행합니다.
다음은 독립된 정상/약한 연기 자료에서 오탐·발생 지연·미탐을 비교하는 작업입니다.

## 검사와 발생 지연

화재 관련216개/12.897초, 기존 Vision 공식1016개/54.078초 통과했습니다. 검사 집합은 중복을 포함하므로 합산하지 않습니다. A 혼합 영상 SMOKE 최초 발생은6.094초→6.766초(0.672초 지연), B 양성 SMOKE는4.531초로 동일했습니다. FIRE 발생 시각도 해당 저장 자료에서는 동일합니다. 로그는 results/safety/smoke_confirmation_regression_verified.log 및 smoke_confirmation_vision_checks.log입니다.


### 2026-10-27 실제 배경640/1280 비교 완료

준비승인후 A1/B0 공유입력 각각60초,4분석TIME_LIMIT/exit0. A회색배경640신규2/재발생5,1280신규1/유지5로오탐재현.1280최고SMOKE0.8741. B두설정후보·사건0. 화재직접장치0, 주차STOPPED/A·Bexit0, CLOSED후fresh없음. 새확정0.55재생도1280오탐1유지,약한양성손실과함께일반적용불가.1280B평균추론430.5ms(64075.55ms), 입력만료미관찰. 런타임을제어기에서직접사용했으며FastAPI서버는시작하지않음. AWS/DB전송없음. 다음은모델평가자료·학습출처확인, 운영기본값유지. 상세SMOKE_BACKGROUND_COMPARISON.md/결과results/safety/background_compare_20261027.

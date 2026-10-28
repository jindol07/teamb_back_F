# FIRE/SMOKE 모델 진단 비교 — 2026-10-27

## 2026-10-28 대표 양성 영역·다음 자료 확보 기준

dataset_review/positive_region_labels.json에 직접 원본을 확대 확인한 양성3장의
대략적 SMOKE 박스·원본 SHA·해상도·작은 FIRE 존재를 기록했습니다. FIRE 개별 박스는
미완료이므로 training_eligible=false 유지. 좌표 범위 및 원본 해시 확인 완료.
source_relations.json에는 같은 혼합 영상의 재생 촬영 관계를 기록해 원본 영상과
A/B를 분할해 독립 평가로 사용하는 오류를 막았습니다. readiness.json은 학습준비false.

D-Fire 공식 저장소(2026-10-28 재확인):
https://github.com/gaia-solutions-on-demand/DFireDataset
화재만1164/연기만5867/혼합4658/정상9838 이미지, YOLO 영역 라벨과 분할 자료 제공.
제3자 출처 이미지의 사용조건은 원제공자 조건도 확인해야 한다고 명시됩니다.
데이터 파일은 아직 다운로드하지 않았으며 실제 클래스 번호·압축 크기·분할 중복·
이미지 손상은 수령 후 확인해야 합니다. 기존 모델이 D-Fire 기반이므로 제공 시험셋도
기존 모델 학습 중복 여부가 확정되기 전 APCMS 독립 평가로 주장하지 않습니다.
원본 자료 확보 및 전체 FIRE/SMOKE 라벨 준비가 다음 단계이며 현재336장만으로
재학습을 시작하지 않습니다. 카메라·AWS·운영 패키지 변경 없음.

## 2026-10-28 확보 원본 목록·대표 검토·분할 정책 정리

results/safety/class_specific_raw_review_retry_20261028/dataset_review/에
inventory.json(원본336장 경로/해시/해상도/역할/검토상태), review_queue.csv,
summary.json을 생성했습니다. 대표 접촉표 representative_contact.png를 직접 확인해
12장 분류: 정상벽/빈도면/꺼진휴대전화·손9장, 연기존재3장. 미검토324장은 정답 추정 없음.
연기3장은 작은불꽃 유무·전체박스 미완료로 표시해 완성 탐지 라벨로 내보내지 않습니다.
모든336장을 같은 source_group/development_diagnostic에 배정했고 training_eligible=false,
holdout_eligible=false. 기존 혼합 원본 영상과 같은 장면을 재생한 자료이므로 추후 그
영상까지 같은 원본 묶음으로 관리해야 합니다. A/B를 독립 분할로 처리하지 않습니다.
336경로·해시 생성/총수·촬영그룹1개·학습/독립평가 미배정 검증 완료.
새 Python 운영파일·카메라·AWS·패키지·모델 변경 없음. 학습 실행 없음.
아직 부족한 항목: 다양한 양성/정상 원본·전체 탐지 라벨·독립 촬영 평가자료·학습 실행 환경.
이번 정리는 자료 준비 진척이며 모델 성능 개선이나 학습셋 완성으로 보고하지 않습니다.

## 2026-10-28 모델 개선 계획 확정 — 반복 실험 중단 기준

현재 운영: 기존 FIRE/SMOKE 모델 유지. mfranzon 후보 및 이중 모델 승격 보류.
클래스 이름 해석은 정상이며 판정 신뢰도 상향만으로 손/벽 오탐과 약한연기 미탐을
동시에 해결하지 못했습니다. 평가도구 추가를 인식 성능 개선으로 보고하지 않습니다.

### 확인한 준비 상태
- 원본336장(A163/B173)은 동일 촬영 세션의 인접 프레임입니다. 독립336사례 아님.
- 수동 연기/오탐 영역 라벨은3장뿐입니다. 이 목록은 진단자료이며 학습셋 아님.
- 기존 진단16항목은 실패분석에 반복 사용했으므로 최종 독립 평가셋이 아닙니다.
- 원본 학습 data.yaml/학습 이미지·정답 세트는 이 프로젝트에서 찾지 못했습니다.
- 현재 .venv torch.cuda.is_available=False,torch.version.cuda=None.
  이는 현재 설치환경 상태이며 PC의 물리 GPU 부재를 뜻하지 않습니다.

### 확정할 개발 목표와 단계
1. 목표를 실제 주차장 카메라 FIRE/SMOKE 보조 감지로 유지합니다. 휴대전화 영상은
   시연용 별도 입력 조건입니다. 휴대전화 성능을 현장 성능으로 일반화하지 않습니다.
2. 추가 촬영 전에 확보 자료에서 시간/장면별 대표 프레임을 골라 정상 벽·손·꺼진화면,
   실제 연기·불꽃·혼합 사례를 라벨링합니다. 반사/모호한 장면은 불확실로 분리합니다.
   연속프레임을 무작위로 학습/검증에 섞지 않습니다. A/B도 같은 영상·같은 세션이면
   같은 source_group으로 취급합니다. 원본과 라벨 버전/해시를 보존합니다.
3. 현재 실패분석 자료를 개발용 진단셋으로 묶고, 학습에 사용한 뒤 동일 자료 성능을
   개선 검증으로 주장하지 않습니다. 최종 보류 평가는 다른 영상/촬영 세션이 필요합니다.
4. 라벨 없는 정상 이미지는 연기 없음이 확인된 경우에만 음성으로 사용합니다.
   손·벽 음성만으로 추가학습하지 않고 일반 FIRE/SMOKE 양성과 정상 배경을 함께 유지합니다.
   공개 원본 데이터는 사용조건·라벨·분할을 확인한 후 별도 동의된 환경에서 확보합니다.
5. 학습은 운영 .venv/서버와 분리합니다. 아직 GPU 실행 환경·자료·예산은 정해지지
   않았으며 CPU로 장시간 학습을 임의 시작하거나 AWS 인스턴스를 켜지 않습니다.
6. 먼저 기존 YOLOv8n을 기준으로 현장 음성 포함 추가학습 가능성을 평가합니다.
   새 후보를 무작정 바꾸거나 이중 모델을 기본화하는 것은 중단합니다.
7. 채택은 검증셋의 실제 연기 위치·약한 연기 사건·FIRE 보존·정상 구간 오탐 사건과
   탐지 지연/자원 사용을 함께 비교한 뒤 결정합니다. 정확도 목표 수치는 자료 구성과
   사용 목적을 정한 뒤 고정하며 이번에 근거 없는 수치를 만들지 않습니다.
8. 학습 개선이 검증된 다음에만 실제 A/B 시험1회, 이후 승인된 AWS 실시간 연동을 합니다.

지금 바로 할 다음 작업은 확보 자료 라벨·세션 분할 정리입니다. 새 모델 다운로드,
학습, 패키지 설치, 카메라 개방, AWS/DB 변경은 이번에 수행하지 않았습니다.

## 2026-10-28 원본의 수동 연기 영역 평가 도구 추가

Python5개: safety/region_review.py,region_review_manifest.py,run_region_review.py,
tests/safety/test_region_review.py,test_region_review_manifest.py.
실제 연기 사각형과 명시적 오탐 영역을 구분하고 IoU0.30 이상 위치 일치를 검사합니다.
한 탐지는 한 정답만 충족하며 오탐 영역에 탐지 면적50% 이상이 겹치면 별도 기록합니다.
검토된 원본3장(꺼진화면/A실제연기/B손+실제연기), 양성영역2개와 음성영역2개 고정.
기존모델: 양성2개 일치/누락0/명시음성탐지0.
후보모델: 양성1개 일치/누락1/명시음성탐지2.
원본 SHA256 검증과 덮어쓰기 방지, RUNNING→COMPLETED 기록. 관련4개 검사 통과.
평가 경계는 눈으로 정한 대략적 사각형이며 독립 정확도/전체 사건 성능으로 일반화하지 않습니다.
기존 모델의 회색 벽 오탐은 이3장에 포함되지 않아 해결됐다는 근거로 사용할 수 없습니다.
후보/이중 모델 운영 승격 보류 유지. 운영 코드·모델·카메라·AWS 변경 없음.
근거 results/safety/class_specific_raw_review_retry_20261028/region_manifest.json,
regions_baseline/review.json,regions_candidate/review.json. 다음 개선 모델은 이 오탐
진단 자료와 기존 약한연기/혼합불꽃 자료를 함께 통과하는지 비교해야 합니다.

## 2026-10-28 원본 재수집 성공 및 동일 원본 모델 비교

class_specific_raw_review_retry_20261028: 양쪽 TIME_LIMIT/error_type=null/종료0,
주차 STOPPED·자식2개 종료0, 카메라 직접 개방0·HTTP0. 원본 A163/B173장 보존.
사건 A SMOKE2/FIRE2, B SMOKE1. 증거 직접 확인: A 꺼진 휴대전화 화면 SMOKE0.5877
오탐, A 실제 연기 SMOKE0.3384 위치 일치, B 손 SMOKE0.6603 오탐.
후보 로그 frame_index를 원본 분석 순번과 맞춰 사건5장 원본에 두 모델을 실제 재추론.
꺼진 화면: 기존탐지없음/후보SMOKE0.5877. B: 기존은 영상 속 연기0.8301,
후보는 손0.6603. A 혼합 양성2장은 기존SMOKE0.7983/0.8571인데 후보SMOKE없음.
따라서 후보는 현장 손·검은 화면 오탐뿐 아니라 화면 속 연기 미탐도 확인됐습니다.
고정 자료16항목의 클래스 존재 성공만으로 후보 우수성을 결론내리지 않습니다.
후보 및 이중 모델 운영 승격은 계속 보류하며 기존 기본 모델을 유지합니다.
증거5장 비교는 단일 프레임 추론이며 사건 재현율이나 일반 정확도가 아닙니다.
기존 모델의 회색 배경 오탐도 남아 있어 기존 모델이 완성됐다는 뜻은 아닙니다.
다음은 확보 원본에서 정상/양성 위치 라벨을 고정하고 모델 후보 또는 학습 개선을 비교하는
작업이며, 동일 시연을 반복하거나 임계값만 높이는 방식은 우선하지 않습니다.
근거 해당 결과 폴더 raw_model_comparison.json,640/*/raw_review/,events.json.

## 2026-10-28 실제 양성 시험에서 SMOKE 오탐 재확인 — 운영 승격 보류

사용자 요청으로 class_specific_positive_20261028의 SUSPECTED 증거7장을 직접 열어
확인했습니다. A SMOKE4/FIRE1, B SMOKE1/FIRE1이며 SMOKE5건 중4건의 박스가
실제 연기 밖에 있습니다. A event0001(0.3794)·0005(0.3195)는 회색 벽,
A event0002(0.4524)·B event0001(0.5232)는 휴대전화 밖 손입니다.
A event0004(0.3332)는 휴대전화 영상의 연기 영역과 일치합니다. FIRE2건은 불꽃이
포함된 영상 안에 있으므로 일괄 오탐으로 분류하지 않았으며 작은 박스 위치의 정확한
불꽃 정합성은 영상 시퀀스 추가 검토로 남깁니다. 사건 증거 기준 분류이며 전체 프레임
오탐률/독립 정확도로 계산하지 않습니다.
직전 정상 배경60초 사건0은 해당 시간대 결과일 뿐 오탐 해결의 근거가 되지 않습니다.
이중 모델 운영 승격 보류. 임계값을 일괄 올리거나 손/벽 영역을 고정 제외하지 않습니다.
실제 양성 감지 품질을 검증하기 전에 최종 완료로 표시하지 않습니다.
양쪽 TIME_LIMIT/error_type=null/camera_open_attempts0/종료0, 주차 STOPPED 및
작업자 모두 종료0. AWS/DB 전송 없음. 근거 results/safety/class_specific_positive_20261028/
evidence_review.json,640/gate 및640/parking의 event_*.jpg와 summary.json.

## 2026-10-28 실제 A/B 이중 모델 정상 배경 시험

사용자 준비 승인 후 주차 공유 프레임을 새 실행으로 생성하고 두 화재 프로세스에서
ClassSpecificModel(FIRE 기존/SMOKE 후보)을 실제 분석했습니다. 관찰 상한60초.
A: 수신100/추론96/표시99/사건0/평균추론196.39ms.
B: 수신91/추론82/표시90/사건0/평균추론274.20ms.
양쪽 TIME_LIMIT/error_type=null/물리 camera_open_attempts0/종료코드0.
공유 파일 관찰 최대 나이1초, 전체 프로세스 표본 RSS 최대3141.2MiB.
이는 합산 프로세스 메모리이며 화재 모델 단독 메모리가 아닙니다. 측정 시 CPU·카메라
부하가 포함돼 저장 영상 추론 시간과 직접 동일시하지 않습니다.
주차 runtime STOPPED/자식2개 모두 종료0, 입출차 HTTP 비활성·요청0. AWS/DB 전송 없음.
기존 정상 회색 배경의 SMOKE 오탐은 이번60초에서 재현되지 않았습니다. 장시간·다른
조명까지 해결된 것으로 표시하지 않습니다. 실제 이중 모델 양성 카메라 시험은 아직 남았습니다.
새 공유 전용 DRY-RUN 실행기 safety/run_class_specific_shared.py는 카메라 직접 입력·
실제 전송 옵션을 제공하지 않습니다. 관련 구성/라벨 검사6개 통과.
근거 results/safety/class_specific_background_20261028/result.json,
640/gate/summary.json,640/parking/summary.json,640/measurement.json,parking_shutdown.json.

## 2026-10-28 클래스별 실제 이중 추론 완료

기존 FIRE+후보 SMOKE를 ClassSpecificModel로 같은 프레임에서 직접 추론했습니다.
모델 names로 클래스 번호를 찾아 각 모델의 담당 클래스만 선택하며 기존 detect_frame/
사건 관리기를 재사용합니다. 운영 기본 모델·라이브 CLI·주차·Boot·DB 설정은 유지했습니다.
고정 진단16항목(사진9/영상7) 실제 전체 실행 COMPLETED/종료0, 예상 클래스의
누락·추가0. 회색 배경/정상 차량 사진 SMOKE 오탐 없음, 약한 연기2영상 SMOKE 사건,
혼합 영상 FIRE+SMOKE, 별도 불꽃 FIRE 확인. 이는 클래스 존재 진단이며 정답 박스가
없는 독립 정확도나 실시간 카메라 오탐 해결률로 표현하지 않습니다.
영상별 평균 이중 추론64.77~74.61ms. A/B 동시 실행·전체 프로세스 자원/지속 성능은
측정하지 않았습니다. 후보 dill은 기존 candidate_deps에서만 사용, 운영 venv/requirements
변경 없음. 모델 파일 자동 다운로드/설치 차단. 결과 두 모델 SHA256 별도 기록.
화재 회귀264개/23.138초 통과 후 메타데이터 검사1개 추가, 해당 비교 모듈8개/0.273초 통과.
검사 수를 합산하지 않습니다. 다음 우선순위는 실제 A/B 정상 배경과 양성 영상 비교이며
준비 확인 전 카메라를 열지 않습니다. AWS 전송 없음. 운영 승격은 실시간 검증 후 판단합니다.
근거 results/safety/class_specific_actual_20261028/review.json 및 validation_summary.json,
results/deployment_audit_20261028/class_specific_actual.log와 class_specific_safety_regression.log.
추가: safety/class_specific_model.py, safety/run_class_specific_review.py,
tests/safety/test_class_specific_model.py, test_class_specific_review.py.
수정: safety/model_review.py, tests/safety/test_model_review.py.

## 결론

운영 모델은 유지합니다. 후보는 회색 배경·차량 사진 오탐과 약한 연기 미탐을 개선했으나
혼합 영상의 작은 FIRE 사건을 놓쳤습니다. 후보 단독 교체를 적용하지 않았습니다.
다음 후보는 FIRE 기존 모델/SMOKE 새 모델을 선택하는 방식이지만 아직 실제 이중 추론
경로를 구현·실행하지 않았습니다. 저장 결과 재생 성공을 실제 구현 성공으로 해석하지 않습니다.

## 고정 자료와 비교 조건

- results/safety/model_comparison_20261027/review_manifest.json: 이미지9개·영상7개,총16항목.
- SHA256으로 자료 변경·중복을 검사하고 원본 영상/촬영 세션을 source_group으로 기록합니다.
- 기존 실패 사례를 포함한 진단 목록이며 무작위 독립 평가셋·학습 라벨이 아닙니다.
- FIRE/SMOKE 신뢰도0.30, 입력640, 영상 전체 길이0.5초 간격, 같은 사건 관리기 사용.
- 영상당 신규 SUSPECTED 사건의 클래스 존재를 비교합니다. 정지 사진은 탐지 클래스를
  비교합니다. 정답 박스·사건 시작시각 라벨이 없어 일반 정확도/IoU 재현율을 산출하지 않습니다.
- 혼합 영상은 실제 불꽃이 포함돼 있어 예상 클래스를 FIRE·SMOKE 모두로 지정했습니다.
- 굴뚝 영상은 시각적 연기 형상 진단 자료이며 실제 화재 여부 정답으로 사용하지 않습니다.
- 자료가 원래 모델 학습 자료에 포함됐는지 확인되지 않았으므로 독립 시험 성능으로 주장하지 않습니다.

## 모델

| 구분 | 공개 출처 | SHA256 |
|---|---|---|
| 기존 | https://huggingface.co/rabahdev/fire-smoke-yolov8n | b91633799ceb052c814b4f8b77a37efc9a40f002d528df97d74463585fa4f28f |
| 후보 | https://huggingface.co/mfranzon/fire-smoke-yolov8 | ac0a10257b2bc1f20c9d957f8adeeb61dd6140322fc19d0b4a116cb491776d16 |

후보 모델 카드에는 D-Fire와 가정 내 화재·연기 자료로 학습했다고 기재돼 있습니다.
학습 설명이 없는 후보들은 우선 제외했습니다. 공개 모델의 성능 주장을 현장 성능으로 사용하지 않습니다.
후보 다운로드 시 고정 revision의 LFS 크기·SHA256과 대조했습니다. 출처·revision은
candidate_source.json에 기록했습니다. 기존 모델의 클래스0=SMOKE/1=FIRE와 후보의
0=FIRE/1=SMOKE는 다르므로 숫자를 고정하지 않고 모델 names로 해석했습니다.

## 진단 결과

| 자료 | 기존 | 후보 |
|---|---|---|
| 기존 FIRE·SMOKE 이미지3개 | 예상 클래스 탐지 | 예상 클래스 탐지 |
| 기존 정상 이미지3개 | 추가 클래스 없음 | 추가 클래스 없음 |
| A 회색 배경 원본 사진 | SMOKE 오탐 | 탐지 없음 |
| B 빈 주차면 원본 사진 | 탐지 없음 | 탐지 없음 |
| 정상 차량 전면 원본 사진 | SMOKE 오탐 | 탐지 없음 |
| 약한 연기 영상2개 | SMOKE 사건 없음 | 각각 SMOKE 사건 있음 |
| 불꽃·연기 혼합 영상 | FIRE·SMOKE 사건 | SMOKE 사건, FIRE 사건 없음 |
| 정상 주차장 영상 | 사건 없음 | 사건 없음 |
| 산림 연기 영상 | SMOKE 사건 | SMOKE 사건 |
| 굴뚝 영상 | SMOKE 사건 없음 | SMOKE 사건 있음 |
| 불꽃 영상 | FIRE 사건 | FIRE 사건 |

정지 배경 사진에서 후보가 오탐하지 않았다는 결과는 연속 카메라의 오탐 해결을 보장하지 않습니다.
특히 이전640/1280 실제 카메라 배경 시험은 기존 모델로 수행했으며 후보로 반복하지 않았습니다.

## 클래스별 기록 조합 재생

영상7개의 두 모델 후보 로그에서 프레임 번호·원본 시각·길이가 일치하는지 확인했습니다.
기존 로그의 FIRE와 후보 로그의 SMOKE만 선택해 같은 FireEventStateManager로 재생했습니다.
정지 이미지도 동일한 클래스 선택을 적용했으며16항목에서 예상 클래스 누락·추가가 없었습니다.

이 결과는 OFFLINE_CLASS_SPECIFIC_REPLAY입니다. 동시 모델 추론 지연·메모리·미리보기·
실제 카메라·실시간 AWS 전송 검증은 포함하지 않습니다. 합산 사건 수나 무작위 정확도로
모델이 완성됐다고 판단하지 않습니다.

## 추가한 Python 파일5개

- safety/model_review_manifest.py: 진단 목록·클래스·미디어·해시·중복 검증.
- safety/model_review.py: 기존 추론/사건 관리로 이미지·전체 영상 평가 및 결과 저장.
- safety/run_model_review.py: 로컬 모델을 명시한 CLI. 자동 모델 다운로드·의존성 설치 차단.
- tests/safety/test_model_review_manifest.py: 자료 변경·중복·잘못된 정답 형식 검사.
- tests/safety/test_model_review.py: 미탐/예상 외 클래스 분리, 결과 덮어쓰기 방지,
  미완료 영상을 성공으로 표시하지 않는 검사.

모델 비교 중단 시 review.json은 RUNNING 상태로 남고 모든 항목 완료 시에만 COMPLETED가 됩니다.
기존 모델 최초 실행은 해당 완료 메타데이터 보강 전 로딩된 코드였으므로 종료코드0·16항목·
각 영상 VIDEO_END를 별도로 확인했습니다. 후보 실행은 COMPLETED·16항목을 확인했습니다.

## 의존성과 검사

후보는 dill이 없어 최초 로딩에 실패했습니다. 자동 설치는 오프라인으로 실패했으며,
dill0.4.0을 결과 폴더 candidate_deps에만 설치해 후보 프로세스 PYTHONPATH로 분리했습니다.
운영 .venv에 dill이 설치되지 않았음을 재확인했습니다. requirements는 수정하지 않았습니다.

자료·모델 비교 관련 검사와 기존 사건 처리 검사59개 통과, 이후 화재 회귀228개/11.653초
통과했습니다(중복 포함, 합산 금지). 로그 model_comparison_20261027/regression.log 및
full_fire_regression.log. 기존 Vision1016개는 이전 결과이며 이번에 다시 실행하지 않았습니다.
git diff --check 통과. 카메라·AWS·업무DB·스테이징·커밋·푸시 변경 없음.

## 재실행

기존 파일을 덮어쓰지 않도록 새 출력 폴더를 지정합니다. 모델과 자료는 로컬 파일만 읽습니다.

```powershell
Set-Location 'D:\finalProjectB\back\apcms_ai'
$reviewRoot = 'D:\finalProjectB\back\apcms_ai\ai_vision\results\safety\model_comparison_20261027'
$reviewStamp = Get-Date -Format 'yyyyMMdd_HHmmss'
& .\.venv\Scripts\python.exe -m ai_vision.safety.run_model_review `
  --manifest "$reviewRoot\review_manifest.json" `
  --model 'D:\finalProjectB\back\apcms_ai\ai_vision\models\fire_smoke.pt' `
  --output "$reviewRoot\baseline_$reviewStamp"

$reviewOldPythonPath = $env:PYTHONPATH
try {
  $env:PYTHONPATH = "$reviewRoot\candidate_deps"
  & .\.venv\Scripts\python.exe -m ai_vision.safety.run_model_review `
    --manifest "$reviewRoot\review_manifest.json" `
    --model "$reviewRoot\candidates\mfranzon_fire_smoke_yolov8.pt" `
    --output "$reviewRoot\candidate_$reviewStamp"
} finally {
  $env:PYTHONPATH = $reviewOldPythonPath
}
```

근거: 같은 결과 폴더의 comparison.json, baseline/review.json, candidate/review.json,
각 영상 후보JSONL·사건JSON·summary, class_specific_replay_summary.json,
class_specific_replay 아래 정렬된 후보와 재생 결과. 가중치·시험 원본·결과는 무분별하게 Git에 포함하지 않습니다.

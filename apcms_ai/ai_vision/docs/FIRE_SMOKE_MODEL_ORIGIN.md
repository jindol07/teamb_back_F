# FIRE/SMOKE 모델 출처 확인 — 2026-10-27

## 확인 결과

로컬 ai_vision/models/fire_smoke.pt는 공개 저장소 rabahdev/fire-smoke-yolov8n의 best.pt와
파일 SHA256·크기가 완전히 일치합니다. 원격 가중치를 실행·교체하지 않고 공개 API의
LFS SHA256과 로컬 해시를 대조했습니다. 공개 검색50개 저장소를 확인했습니다.

- 원배포 설명: https://huggingface.co/rabahdev/fire-smoke-yolov8n
- 해시 확인: https://huggingface.co/rabahdev/fire-smoke-yolov8n/blob/main/best.pt
- 고정 revision: 13017fe8af477c25f5298d168e2dfede4b000753
- SHA256: b91633799ceb052c814b4f8b77a37efc9a40f002d528df97d74463585fa4f28f
- 크기: 6229802bytes
- nobita111222/fire-smoke-yolov8n/best.pt도 같은 해시이며 모델 사용 예시는 rabahdev를 가리킵니다.
- 다운로드 폴더의 fire_smoke.pt도 같은 해시입니다. Windows 다운로드 출처 정보는 남지 않아
  사용자가 실제 어느 사이트에서 받은 것인지는 확정하지 않습니다.

## 모델 정보와 직접 확인한 기록

| 항목 | 확인 결과 |
|---|---|
| 구조 | YOLOv8n, COCO 사전학습 모델 기반 D-Fire 추가 학습(공개 모델 설명) |
| 클래스 | 0=smoke,1=fire(파일 내부·공개 설명 일치) |
| 설정 | 640 입력,50epochs,batch16(파일 내부·공개 설명 일치) |
| 학습 기록 | 파일 내부 train_results에50개 epoch 기록, 마지막50 |
| 원본 데이터 경로 | 제작자 PC의 data.yaml 경로만 기록. 이 프로젝트에 학습 데이터·라벨·data.yaml 없음 |
| 라이선스 표기 | 파일 내부·모델 카드 AGPL-3.0 |

모델 카드의 시험셋4306장 성능은 Precision0.766/Recall0.688/mAP50 0.754입니다.
체크포인트에 저장된 별도 수치 Precision0.77529/Recall0.69452와 구분해야 하며,
어느 쪽도 현재 APCMS 카메라의 정확도나 연기 사건 검출률이 아닙니다.

## 오탐 분석에 미치는 의미

클래스 번호를 뒤집어 읽는 오류는 현재 names와 처리 코드 기준으로 확인되지 않았습니다.
실제 빈 회색 배경을 높은 SMOKE 점수로 출력하므로 후속 상태 관리만의 문제로 볼 수 없습니다.

D-Fire 공개 자료에는 정상 이미지도 포함됩니다. 따라서 '정상 사진이 전혀 없는 데이터셋으로
학습했다'고 단정하면 안 됩니다. 이 가중치 학습 분할의 실제 구성과 현재 책상 배경의 포함
여부는 원본 라벨·목록 없이는 확인할 수 없습니다.

데이터셋 원문: https://github.com/gaia-solutions-on-demand/DFireDataset

## 다음 작업

1. 회색 배경·차량 전면의 음성 자료와 약한 연기·불꽃·혼합 양성 자료를 평가 목록으로 고정합니다.
2. 같은 영상의 인접 프레임이 학습과 평가로 나뉘지 않도록 원본 영상/촬영 세션별로 분리합니다.
3. 현재 모델을 기준선으로 보존하고, 출처가 확인된 대안 모델 또는 현장 자료를 포함한 추가 학습을
   별도 결과 폴더에서 비교합니다. 후보 평가 없이 기존 가중치를 교체하지 않습니다.
4. 학습에 사용한 자료로 오탐 해결을 선언하지 않고 별도 촬영 자료에서 재확인합니다.

이번에는 모델 다운로드·추가 학습·카메라·AWS·DB·Git 변경을 수행하지 않았습니다.

## 재현 근거

results/safety/model_origin_review_20261027/checkpoint_metadata.json,
public_search.json,public_weight_matches.json,find_public_origin.py.
기계 판독용 고정 출처: docs/FIRE_SMOKE_MODEL_PROVENANCE.json.

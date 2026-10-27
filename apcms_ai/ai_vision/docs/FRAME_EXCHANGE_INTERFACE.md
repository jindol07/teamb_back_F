# 주차 A/B → 화재·연기 감지 프레임 전달 인터페이스

버전: 1 / 작성일: 2026-10-27

## 1. 목적과 담당 범위

주차 A(입출차)·B(주차면)가 확보한 원본 영상을 별도 화재 감지 프로세스에 제공합니다. 화재 소비자는 카메라를 다시 열지 않습니다.

주차 송신·읽기 함수와 다른 담당이 추가한 화재 SharedFrameCapture 입력 모드가 로컬에 있습니다. 실제 송신기→수신기→화재 상태 누적의 모의 프레임 검증은 통과했습니다. 실카메라·실제 화재 모델·실제 알림 전송 통합 검증은 아직입니다. 이 채팅에서는 화재 소스를 수정하지 않았습니다.

지원 범위는 **동일 호스트의 별도 프로세스**, 또는 **동일 호스트의 로컬 공유 볼륨을 사용하는 컨테이너**입니다. 원격 호스트·네트워크 파일시스템·AWS에서 현장 USB 직접 접근은 지원하지 않습니다. 단조 시계가 공유되는 환경이어야 합니다.

## 2. 활성화 설정

일반 주차 runtime의 기존 JSON에 다음 항목을 추가합니다. 아래는 추가 필드 예시이며 완전한 runtime 설정 파일이 아닙니다.

```json
{
  "frame_export_dir": "shared_frames",
  "frame_export_fps": 2
}
```

| 항목 | 규칙 |
|---|---|
| frame_export_dir | 선택. 생략하면 전달 비활성. 상대 경로는 runtime JSON의 부모 폴더 기준으로 해석 |
| frame_export_fps | 경로 지정 시 선택, 기본 2. 유한한 숫자이며 0 초과 10 이하. bool 불가 |
| PARKING_RUNTIME_ENABLED | 기존 주차 runtime 활성화 설정. true 필요 |
| PARKING_RUNTIME_CONFIG | 기존 runtime JSON 경로 |

FPS만 지정하고 전달 경로를 생략하면 설정 오류입니다. 전달 경로가 기존 일반 파일이면 시작 전 설정 오류로 차단합니다. 전달 설정은 Boot 전송 활성화와 독립적입니다. 일반 runtime에 연결되어 있으며 기존 수동 시연·전용 ServerTrial에는 활성화하지 않았습니다.

## 3. 위치와 카메라 식별

```text
<frame_export_dir>/<run_id>/gate.frame
<frame_export_dir>/<run_id>/parking.frame
```

| role | 의미 | camera_id 출처 |
|---|---|---|
| gate | A 입출차 | runtime JSON의 gate_id |
| parking | B 주차면 | runtime JSON의 parking_id |

camera_id와 run_id는 공백이 아닌 문자열이며 각각 최대 128자입니다. FRAME의 sequence는 1 이상 정수, CLOSED는 0 이상 정수이고 bool은 허용하지 않습니다. published_at_utc는 UTC 오프셋을 가진 ISO 시각이어야 합니다.

camera_id는 논리 식별자입니다. USB 번호 0/1과 구분합니다. run_id는 주차 실행 결과 폴더 이름과 같습니다. 매 실행 바뀌므로 소비자에 현재 실행 폴더를 전달해야 합니다. **현재 실행 자동 탐색·구독 등록 API는 없습니다.** 과거 폴더를 임의 선택하지 않습니다. 실행 폴더 안의 파일은 카메라별 송신자 하나만 씁니다.

## 4. 파일 형식

파일은 임시 파일에 쓴 뒤 os.replace로 교체합니다. Windows에서 소비자의 읽기와 겹친 PermissionError는 0.01초 간격 최대 20회 추가 재시도(총 대기 약0.2초) 후 실패를 기록하며 비원자 덮어쓰기로 바꾸지 않습니다. 소비자는 한 번 연 파일에서 헤더와 픽셀을 함께 읽어야 합니다.

| 순서 | 길이 | 내용 |
|---|---|---|
| 1 | 8바이트 | ASCII APCMSF1 + LF (hex 41 50 43 4D 53 46 31 0A) |
| 2 | 4바이트 | JSON 길이, unsigned uint32, big-endian |
| 3 | 위 길이 | UTF-8 JSON 메타데이터 |
| 4 | FRAME일 때 H×W×3 바이트 | 원본 픽셀, uint8, BGR, C 순서 |

읽기 함수의 파일 상한은 64MiB, JSON 헤더 상한은 4096바이트입니다. FRAME 픽셀 바이트 수는 shape의 곱과 정확히 같아야 합니다. JPEG 압축·크기 변경·주차 안내 문구를 넣지 않습니다.

FRAME 메타데이터 예시(숫자·식별자는 설명용):

```json
{
  "version": 1,
  "role": "gate",
  "camera_id": "A_GATE",
  "run_id": "example-run-id",
  "sequence": 1,
  "captured_monotonic": 12345.67,
  "published_at_utc": "2026-10-27T04:00:00+00:00",
  "shape": [720, 1280, 3],
  "dtype": "uint8",
  "color": "BGR",
  "status": "FRAME"
}
```

- sequence: 카메라 촬영 순번이 아니라 전달 표본 순번입니다. 중간 표본은 덮어써질 수 있으므로 연속 수신을 요구하지 않습니다.
- captured_monotonic: 촬영 시각, 초 단위 단조 시계입니다. UTC 시각이나 영상 파일 재생 시각이 아닙니다.
- published_at_utc: 파일 작성 UTC 시각. 입력 신선도는 captured_monotonic으로 판정합니다.
- shape: 실행 중 해상도가 바뀔 수 있으므로 매 표본 확인합니다.

## 5. FPS와 지연

기본 전달 상한은 카메라별 2FPS입니다. 주차 분석 루프가 확보한 프레임을 표본으로 전달하므로 실제 전달률은 추론·카메라 속도에 제한됩니다. 카메라 전체 FPS나 일정 간격 수신을 보장하지 않습니다.

카메라마다 대기열은 최신 1장입니다. 느린 디스크 쓰기·소비자 때문에 무제한 적재하지 않으며 중간 표본은 건너뜁니다. 디스크 쓰기는 별도 스레드에서 수행하지만 원본 복사 비용은 주차 실행에 추가됩니다. 화재 담당은 이 입력률에 맞춰 감지 조건·확정 시간을 검토해야 합니다.

## 6. 소비자 읽기 API

구현 모듈: ai_vision.parking.frame_exchange

```python
read_latest(path, max_age=3)
```

| 결과 | 의미 / 소비자 처리 |
|---|---|
| (metadata, frame) | 유효한 FRAME. frame은 독립 복사된 numpy.ndarray, uint8 BGR |
| None | 파일 없음, CLOSED, 입력 만료, 또는 미래 단조 시각. 새 감지 표본으로 사용 금지 |
| ValueError | 손상·규격·시각 오류 또는 유효하지 않은 max_age. 입력 오류로 처리 |
| OSError | 접근·읽기 오류. 별도 기록하고 다음 폴링에서 재시도 가능 |

max_age는 유한한 양수 초이며 기본 3초입니다. 현재 함수는 None의 세부 원인을 분리해 반환하지 않습니다. 소비자는 마지막 유효 입력 시각을 별도로 관리해 미연결·입력 중단 상태를 표시해야 합니다. 같은 프레임의 반복 반환은 정상이며 `(run_id, role, sequence)`로 중복을 제거합니다.

## 7. 소비자 사용 예시

아래 코드는 카메라 하나의 읽기·중복 제거 골격입니다. 화재 감지 호출은 담당자가 기존 파이프라인에 연결합니다. A/B는 각각 실행하거나 번갈아 폴링하며 상태를 분리합니다.

```python
import time
from pathlib import Path
from ai_vision.parking.frame_exchange import read_latest


def consume_frames(run_dir, role, stop_event, handle_frame, handle_unavailable):
    if role not in ("gate", "parking"):
        raise ValueError("잘못된 role")
    path = Path(run_dir) / f"{role}.frame"
    last_token = None
    while not stop_event.is_set():
        try:
            sample = read_latest(path, max_age=3)
        except (ValueError, OSError) as error:
            handle_unavailable(role, type(error).__name__)
            sample = None
        if sample is not None:
            metadata, bgr_frame = sample
            token = (metadata["run_id"], metadata["role"], metadata["sequence"])
            if token != last_token:
                # 성공한 처리만 중복 토큰으로 기록합니다.
                handle_frame(metadata, bgr_frame)
                last_token = token
        else:
            # 실제 구현에서는 같은 상태 알림의 반복을 제한합니다.
            handle_unavailable(role, "NO_FRESH_FRAME")
        stop_event.wait(0.1)
```

## 8. 연결·재시작·종료

1. 운영자가 현재 run_id 폴더를 소비자에 제공합니다. 파일 생성 전에는 None입니다.
2. 첫 유효 표본부터 처리하고 role/camera_id가 예상 설정과 일치하는지 소비자가 확인합니다.
3. 새 run_id로 연결 시 이전 실행의 중복 토큰·시간 기준을 초기화합니다. 화재 이벤트의 유지/종료 정책은 화재 담당이 정합니다.
4. 정상 송신 종료 시 같은 파일에 CLOSED 메타데이터를 쓰고 픽셀은 넣지 않습니다. CLOSED는 version/role/camera_id/run_id/sequence/published_at_utc/status를 포함합니다.
5. 송신 스레드 종료 대기는 최대 2초입니다. 강제 종료·디스크 오류·종료 대기 초과에서는 CLOSED가 없을 수 있으므로 입력 만료 판단이 필수입니다.
6. 수신 종료는 소비자 자신의 stop_event로 처리합니다. 소비자는 송신 파일을 삭제하거나 주차 프로세스를 종료하지 않습니다.

전달 파일은 자동 삭제되지 않습니다. 실행 폴더 정리는 소비자 종료 후 운영 보존 정책에 따라 수행합니다. 키·토큰은 프레임 파일에 넣지 않습니다. 차량 영상이 포함되므로 공유 폴더 접근을 제한합니다.

## 9. 화재 담당 구현 항목

- 카메라를 직접 열지 않는 외부 프레임 입력 모드 추가. 공유 모드에서는 VideoCapture와 장치 재연결 금지.
- 위 읽기 함수로 A/B 입력 수신, 논리 카메라 검증, 중복 제거, 만료/오류/새 실행 처리.
- 카메라별 독립 감지 상태·시간 기준·이벤트·증거 경로 구성.
- 기존 화재의 상태 누적·증거 저장·알림 전송 흐름 재사용. 단일 프레임 detect_frame 호출만으로 전체 연동 완료 처리 금지.
- 입력 중단 시 마지막 이미지를 새 프레임처럼 재사용하지 않고 입력 장애를 표시.
- 현재 통합 앱의 카메라 중복 차단은 유지되어 있습니다. 공유 모드가 구현·검증된 후 설정/차단 규칙을 담당자와 함께 조정해야 합니다. 기존 독립 카메라 화재 모드를 동시에 켜지 않습니다.

## 10. 검증 범위

모의 영상으로 원본 복사, 별도 프로세스 읽기, A/B 분리, 입력 만료·종료, 설정값·손상 파일, worker 전달 연결·예외 종료를 검사했습니다. 실제 화재 소비자 연동·실제 카메라 동시 실행·장시간 성능·컨테이너 공유 볼륨 검증은 아직입니다.

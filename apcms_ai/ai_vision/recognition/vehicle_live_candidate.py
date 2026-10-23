# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_live_candidate.py
"""실시간 차량 통과 기록을 검증하고 백엔드 전달 후보로 변환하는 모듈.

처리 단계: 실시간 출처 확인 → 통과 기록 검사 → 번호판 확정 여부 확인
→ 차량 탐지 점수 확인 → 입출차 방향 결정 → 전송 *후보* 반환.
이 함수 자체는 HTTP 요청을 보내지 않습니다.
"""

# 1. 외부 모듈 불러오기
# 1-1. uuid는 요청마다 고유 이벤트 식별자를 만드는 표준 라이브러리입니다.
import uuid
# 1-2. 번호판을 탐지했던 프레임의 신뢰도 점수를 구하는 기존 함수입니다.
from ai_vision.recognition.preview_vehicle_events import detection_confidence
# 1-3. 저장/실시간 통과 자료의 필드와 자료형을 검증합니다.
from ai_vision.recognition.result_validation import public_passage
# 1-4. 서버 요청 규격과 카메라 번호 및 감지 시각을 검증합니다.
from ai_vision.recognition.vehicle_contract import validate_camera_id, validate_vehicle_payload, parse_detected_at


# 2. 실시간 통과 기록을 전송 가능한 형태의 후보로 만드는 함수
# 2-1. passage: 추적 ID, 화면 방향, OCR 표본 등이 들어 있는 통과 기록
# 2-2. camera_id: 서버가 구분할 카메라 식별자
# 2-3. down_direction: 화면에서 아래로 이동할 때의 실제 의미('ENTRY' 또는 'EXIT')
# 2-4. detected_at: 타임존을 포함한 통과 시각; event_id는 선택적인 이벤트 UUID
# 2-5. 반환값은 status, 차단 이유, payload를 담은 딕셔너리입니다.
def create_live_candidate(passage, camera_id, down_direction, detected_at, event_id=None):
    # 3. 출처와 입력값 검증
    # 3-1. 오프라인 영상을 LIVE 이벤트인 것처럼 전송하는 사고를 차단합니다.
    if not isinstance(passage, dict) or passage.get("record_type") != "LIVE_TRACKED_PASSAGE":
        raise ValueError("실시간 통과 자료만 변환할 수 있습니다.")
    # 3-2. 검증기에서 사용하는 기존 형식으로 표시만 바꾼 새 사본을 전달합니다.
    # 원본 passage 딕셔너리의 record_type은 변경되지 않습니다.
    checked = public_passage({**passage, "record_type": "LOCAL_TRACKED_PASSAGE"})
    validate_camera_id(camera_id)
    # 3-3. DOWN 방향의 실제 의미를 설치 현장에서 확인하도록 강제합니다.
    if not isinstance(down_direction, str) or down_direction not in {"ENTRY", "EXIT"}:
        raise ValueError("카메라 DOWN 방향의 실제 입출차 구분이 필요합니다.")
    # 3-4. 시각을 임의로 추정하지 않고 호출자가 받은 값을 검증합니다.
    parse_detected_at(detected_at)

    # 4. 전송 후보 자격을 판단합니다.
    reasons = []
    # 4-1. 서로 다른 프레임에서 번호판이 충분히 일치하여 CONFIRMED여야 합니다.
    if checked["plate_status"] != "CONFIRMED":
        reasons.append("NO_CONFIRMED_KOREAN_PLATE")
    # 4-2. 번호판이 확정된 경우에만 탐지 신뢰도를 조회합니다.
    confidence = detection_confidence(passage) if not reasons else None
    if not reasons and confidence is None:
        reasons.append("MISSING_DETECTION_CONFIDENCE")

    # 5. 조건을 만족할 때만 Spring Boot 요청 형식의 payload를 만듭니다.
    payload = None
    if not reasons:
        # 5-1. 실제 DOWN이 ENTRY라면 화면 UP은 EXIT이고, 반대도 마찬가지입니다.
        direction = down_direction if checked["screen_direction"] == "DOWN" else {"ENTRY": "EXIT", "EXIT": "ENTRY"}[down_direction]
        # 5-2. 이벤트 ID는 새로 만들거나 외부에서 전달한 값을 사용합니다.
        # 5-3. validate_vehicle_payload가 요청의 필수 항목/형식을 마지막으로 확인합니다.
        payload = validate_vehicle_payload({"event_id": str(uuid.uuid4()) if event_id is None else event_id,
                    "event_type": "VEHICLE_PASSAGE", "detected_at": detected_at, "camera_id": camera_id,
                    "direction": direction, "plate_number": checked["plate_number"], "confidence": confidence})

    # 6. 전송 '후보'만 반환합니다. 실제 HTTP 호출이나 DB 저장은 여기서 하지 않습니다.
    # 6-1. reasons가 있으면 BLOCKED, 없으면 CANDIDATE_ONLY입니다.
    # 6-2. confidence는 OCR의 실제 정답 확률이 아니라 번호판 탐지 점수입니다.
    return {"origin": "LIVE", "track_id": checked["track_id"], "status": "BLOCKED" if reasons else "CANDIDATE_ONLY",
            "reasons": reasons, "payload": payload, "http_enabled": False,
            "confidence_basis": "MIN_MATCHING_PLATE_DETECTION_CONFIDENCE_NOT_OCR_ACCURACY"}


def create_space_match_candidate(match, current_matches, camera_id, detected_at):
    """현재 점유·추적과 일치하는 실시간 연결만 Boot 요청 후보로 만듭니다."""
    from ai_vision.parking.parking_event_sender import convert_space_code
    from ai_vision.recognition.vehicle_contract import validate_space_match_payload
    if not isinstance(match, dict) or match.get('kind') != 'LIVE_SPACE_MATCH':
        raise ValueError('실시간 구획 관찰만 변환할 수 있습니다.')
    track = match.get('track_id')
    if type(track) is not int or track < 0:
        raise ValueError('추적 ID를 확인하세요.')
    signature = {key: match.get(key) for key in ('track_id', 'space_id', 'plate_number')}
    if signature not in current_matches:
        return {'origin': 'LIVE', 'track_id': track, 'status': 'BLOCKED',
                'reasons': ['MATCH_WITHDRAWN'], 'payload': None}
    payload = validate_space_match_payload({
        'event_id': str(uuid.uuid4()), 'event_type': 'VEHICLE_SPACE_MATCH',
        'camera_id': camera_id, 'detected_at': detected_at,
        'plate_number': match.get('plate_number'),
        'confidence': match.get('plate_detection_confidence'),
        'space_code': convert_space_code(match.get('space_id')), 'method': 'TRACKING'})
    identity = match.get('identity_basis') == 'SINGLE_VEHICLE_ENTRY_HANDOFF'
    expected_usage = match.get('parking_usage_id') if identity else None
    if identity and (type(expected_usage) is not int or expected_usage < 1):
        raise ValueError('입차 신원 전달의 이용 ID를 확인하세요.')
    return {'origin': 'LIVE', 'track_id': track, 'status': 'CANDIDATE_ONLY',
            'reasons': [], 'payload': payload, 'http_enabled': False,
            **({'expected_parking_usage_id': expected_usage} if identity else {}),
            'confidence_basis': ('ENTRY_PLATE_AND_PARKING_TARGET_DETECTION_NOT_OCR_ACCURACY' if identity
                                 else 'MIN_MATCHING_PLATE_DETECTION_CONFIDENCE_NOT_OCR_ACCURACY')}

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_live_candidate.py

"""실시간 통과 자료를 전송 판단용 후보로 바꿉니다. 시각·방향을 추측하지 않습니다."""

import uuid
from ai_vision.recognition.preview_vehicle_events import detection_confidence
from ai_vision.recognition.result_validation import public_passage
from ai_vision.recognition.vehicle_contract import validate_camera_id, validate_vehicle_payload, parse_detected_at


def create_live_candidate(passage, camera_id, down_direction, detected_at, event_id=None):
    # 1. 과거 영상의 LOCAL_TRACKED_PASSAGE를 실시간 입출차로 잘못 재생하지 않습니다.
    if not isinstance(passage, dict) or passage.get("record_type") != "LIVE_TRACKED_PASSAGE":
        raise ValueError("실시간 통과 자료만 변환할 수 있습니다.")
    checked = public_passage({**passage, "record_type": "LOCAL_TRACKED_PASSAGE"})
    validate_camera_id(camera_id)
    if not isinstance(down_direction, str) or down_direction not in {"ENTRY", "EXIT"}:
        raise ValueError("카메라 DOWN 방향의 실제 입출차 구분이 필요합니다.")
    parse_detected_at(detected_at)
    reasons = []
    if checked["plate_status"] != "CONFIRMED":
        reasons.append("NO_CONFIRMED_KOREAN_PLATE")
    confidence = detection_confidence(passage) if not reasons else None
    if not reasons and confidence is None:
        reasons.append("MISSING_DETECTION_CONFIDENCE")
    payload = None
    if not reasons:
        direction = down_direction if checked["screen_direction"] == "DOWN" else {"ENTRY": "EXIT", "EXIT": "ENTRY"}[down_direction]
        # 2. detected_at은 호출자가 통과 순간에 확보한 타임존 포함 시각입니다.
        payload = validate_vehicle_payload({"event_id": str(uuid.uuid4()) if event_id is None else event_id,
                    "event_type": "VEHICLE_PASSAGE", "detected_at": detected_at, "camera_id": camera_id,
                    "direction": direction, "plate_number": checked["plate_number"], "confidence": confidence})
    return {"origin": "LIVE", "track_id": checked["track_id"], "status": "BLOCKED" if reasons else "CANDIDATE_ONLY",
            "reasons": reasons, "payload": payload, "http_enabled": False,
            "confidence_basis": "MIN_MATCHING_PLATE_DETECTION_CONFIDENCE_NOT_OCR_ACCURACY"}

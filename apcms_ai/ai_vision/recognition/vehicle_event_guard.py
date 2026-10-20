# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_event_guard.py

"""UUID DB 저장 없이 AI 프로세스 안에서 반복 차량 이벤트 후보를 억제합니다."""

import math
import re
import threading
from datetime import timezone

from ai_vision.recognition.vehicle_contract import validate_camera_id, validate_vehicle_payload, parse_detected_at


class VehicleEventGuard:
    def __init__(self, cooldown_seconds=5, max_entries=10000):
        if (isinstance(cooldown_seconds, bool) or not isinstance(cooldown_seconds, (int, float)) or
                not 0 < cooldown_seconds <= 300 or not math.isfinite(cooldown_seconds) or
                type(max_entries) is not int or max_entries < 1):
            raise ValueError("중복 억제 시간과 최대 보관 건수를 확인해 주세요.")
        self.cooldown_seconds = cooldown_seconds
        self.max_entries = max_entries
        self._tracks = {}
        self._recent = {}
        self._ids = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(session_id, track_id, camera_id):
        if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", session_id):
            raise ValueError("실행 식별자 형식이 유효하지 않습니다.")
        if type(track_id) is not int or track_id < 0:
            raise ValueError("차량 ID는 0 이상의 정수여야 합니다.")
        return validate_camera_id(camera_id), session_id, track_id

    @staticmethod
    def _decision(record, decision=None):
        state = record["decision"] if decision is None else decision
        return {"decision": state, "event_id": record["event_id"], "receipt_state": record["receipt_state"],
                "payload": dict(record["payload"]) if state == "NEW_CANDIDATE" else None,
                "http_enabled": False, "sendable": False, "automatic_retry_allowed": False}

    def consider(self, session_id, track_id, payload, now=None):
        # 같은 프로세스의 여러 스레드가 동시에 후보를 요청해도 한 건만 만듭니다.
        with self._lock:
            return self._consider(session_id, track_id, payload, now)

    def _consider(self, session_id, track_id, payload, now):
        event = validate_vehicle_payload(payload, now)
        key = self._key(session_id, track_id, event["camera_id"])
        at = parse_detected_at(event["detected_at"]).astimezone(timezone.utc)
        # 1. 다시 만든 UUID·신뢰도로 별도 통과를 만들지 않고 최초 이벤트를 유지합니다.
        signature = (event["plate_number"], event["direction"], at)
        old = self._tracks.get(key)
        if old is not None:
            decision = "SUPPRESSED_SAME_TRACK" if old["signature"] == signature else "HELD_TRACK_CONFLICT"
            return self._decision(old, decision)
        if len(self._tracks) >= self.max_entries:
            # 오래된 기록을 지워 중복을 다시 허용하지 않고 신규 입력을 보류합니다.
            return {"decision": "HELD_CAPACITY", "event_id": None, "receipt_state": None, "payload": None,
                    "http_enabled": False, "sendable": False, "automatic_retry_allowed": False}
        recent_key = (event["camera_id"], event["plate_number"], event["direction"])
        recent = self._recent.get(recent_key)
        decision, anchor = "NEW_CANDIDATE", event["event_id"]
        if recent is not None:
            elapsed = (at - recent["at"]).total_seconds()
            if elapsed < 0:
                decision, anchor = "HELD_OUT_OF_ORDER", recent["event_id"]
            elif elapsed < self.cooldown_seconds:
                decision, anchor = "SUPPRESSED_RECENT_PLATE", recent["event_id"]
        if decision == "NEW_CANDIDATE" and event["event_id"] in self._ids:
            decision = "HELD_EVENT_ID_REUSE"
        record = {"signature": signature, "decision": decision, "event_id": anchor,
                  "receipt_state": "AWAITING_RESULT" if decision == "NEW_CANDIDATE" else "NOT_CREATED",
                  "payload": dict(event) if decision == "NEW_CANDIDATE" else None, "result": None}
        self._tracks[key] = record
        if decision == "NEW_CANDIDATE":
            self._recent[recent_key] = {"at": at, "event_id": anchor}
            self._ids[event["event_id"]] = key
        return self._decision(record)

    def record_result(self, session_id, track_id, camera_id, result):
        with self._lock:
            return self._record_result(session_id, track_id, camera_id, result)

    def _record_result(self, session_id, track_id, camera_id, result):
        record = self._tracks.get(self._key(session_id, track_id, camera_id))
        if record is None or record["decision"] != "NEW_CANDIDATE":
            raise ValueError("생성된 후보의 응답만 기록할 수 있습니다.")
        verified_states = {"APPLIED", "UNCHANGED", "HELD"}
        other_states = {"REJECTED", "AUTH_REQUIRED", "DELIVERY_UNKNOWN"}
        if (not isinstance(result, dict) or result.get("event_id") != record["event_id"] or
                result.get("event_type") != "VEHICLE_PASSAGE" or result.get("automatic_retry_allowed") is not False or
                not isinstance(result.get("state"), str) or result["state"] not in verified_states | other_states or
                result.get("receipt_verified") is not (result.get("state") in verified_states)):
            raise ValueError("원본 이벤트와 일치하는 검증 결과가 필요합니다.")
        # 2. 처리 불명 결과를 성공으로 자동 변경하거나 재전송 대기 상태로 돌리지 않습니다.
        saved = {key: result[key] for key in ("event_id", "event_type", "state", "receipt_verified", "automatic_retry_allowed")}
        if record["result"] is not None and record["result"] != saved:
            raise ValueError("기록된 응답을 다른 상태로 덮어쓸 수 없습니다.")
        record["result"] = saved
        record["receipt_state"] = result["state"]
        return self._decision(record, "RESULT_RECORDED")

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_event_guard.py
"""UUID DB 저장 없이 AI 프로세스 안에서 반복 차량 이벤트 후보를 억제합니다."""

# 1. 모듈과 공통 검증 함수
# 1-1. math는 유한한 숫자 검사, re는 세션 이름 형식 검사에 사용합니다.
import math
import re
# 1-2. threading.RLock은 같은 프로세스 내 여러 스레드의 동시 후보 생성을 막습니다.
import threading
from datetime import timezone
# 1-3. 백엔드 요청값·카메라 ID·감지 시각 형식을 다른 모듈과 동일하게 검사합니다.
from ai_vision.recognition.vehicle_contract import validate_camera_id, validate_vehicle_payload, parse_detected_at

# 2. 차량 이벤트 중복 억제 관리자
class VehicleEventGuard:
    # 2-1. 동일 번호판의 반복 방지 시간과 메모리 보관 상한을 설정합니다.
    # 함수 설명: __init__() — 중복 억제 기간·보관 용량·스레드 락을 초기화합니다.
    def __init__(self, cooldown_seconds=5, max_entries=10000):
        # 2-2. bool은 숫자의 하위 타입으로 취급될 수 있어 명시적으로 제외합니다.
        if (isinstance(cooldown_seconds, bool) or not isinstance(cooldown_seconds, (int, float)) or
                not 0 < cooldown_seconds <= 300 or not math.isfinite(cooldown_seconds) or
                type(max_entries) is not int or max_entries < 1):
            raise ValueError("중복 억제 시간과 최대 보관 건수를 확인해 주세요.")
        self.cooldown_seconds = cooldown_seconds
        self.max_entries = max_entries
        # 2-3. 차량 ID별 최초 처리·동일 번호판 최근 이벤트·UUID 사용 여부를 분리해 보관합니다.
        self._tracks = {}
        self._recent = {}
        self._ids = {}
        self._lock = threading.RLock()

    # 3. 차량을 구분할 복합 키 생성
    @staticmethod
    # 함수 설명: _key() — 카메라, 세션, 차량 ID를 하나의 고유 추적 키로 묶습니다.
    def _key(session_id, track_id, camera_id):
        # 3-1. 세션 ID는 영문·숫자로 시작하는 최대 96자 안전한 식별자여야 합니다.
        if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", session_id):
            raise ValueError("실행 식별자 형식이 유효하지 않습니다.")
        if type(track_id) is not int or track_id < 0:
            raise ValueError("차량 ID는 0 이상의 정수여야 합니다.")
        # 3-2. 추적 번호가 같아도 카메라나 실행 세션이 다르면 다른 차량 기록입니다.
        return validate_camera_id(camera_id), session_id, track_id

    # 4. 외부 호출자에게 반환할 판정 형태 통일
    @staticmethod
    # 함수 설명: _decision() — 외부로 노출할 제한된 판정 기록을 새 딕셔너리로 생성합니다.
    def _decision(record, decision=None):
        state = record["decision"] if decision is None else decision
        # 4-1. 신규 후보만 payload를 제공하고, 억제·보류된 이벤트는 전송하지 못하게 합니다.
        return {"decision": state, "event_id": record["event_id"], "receipt_state": record["receipt_state"],
                "payload": dict(record["payload"]) if state == "NEW_CANDIDATE" else None,
                "http_enabled": False, "sendable": False, "automatic_retry_allowed": False}

    # 5. 후보 검사 진입점
    # 함수 설명: consider() — 동시에 같은 후보가 들어와도 한 번만 판단하도록 잠금 처리합니다.
    def consider(self, session_id, track_id, payload, now=None):
        # 5-1. 하나의 프로세스 안에서 동시에 같은 후보가 만들어지지 않도록 잠급니다.
        with self._lock:
            return self._consider(session_id, track_id, payload, now)

    # 6. 후보 생성·중복 억제 판정
    # 함수 설명: _consider() — 동일 트랙·동일 번호판 재등장·오래된 이벤트를 구분합니다.
    def _consider(self, session_id, track_id, payload, now):
        # 6-1. 이벤트 필드를 검증하고 서로 다른 타임존 표현을 UTC로 통일합니다.
        event = validate_vehicle_payload(payload, now)
        key = self._key(session_id, track_id, event["camera_id"])
        at = parse_detected_at(event["detected_at"]).astimezone(timezone.utc)
        # 6-2. UUID나 탐지 점수가 다시 만들어져도 번호판·방향·시각이 같으면 같은 이벤트입니다.
        signature = (event["plate_number"], event["direction"], at)
        old = self._tracks.get(key)
        if old is not None:
            decision = "SUPPRESSED_SAME_TRACK" if old["signature"] == signature else "HELD_TRACK_CONFLICT"
            return self._decision(old, decision)
        # 6-3. 보관 상한에 도달해도 기존 기록을 삭제하지 않고 새로운 후보를 보류합니다.
        if len(self._tracks) >= self.max_entries:
            return {"decision": "HELD_CAPACITY", "event_id": None, "receipt_state": None, "payload": None,
                    "http_enabled": False, "sendable": False, "automatic_retry_allowed": False}
        # 6-4. 추적 ID가 바뀌어도 동일 카메라·번호판·방향의 최근 이벤트를 확인합니다.
        recent_key = (event["camera_id"], event["plate_number"], event["direction"])
        recent = self._recent.get(recent_key)
        decision, anchor = "NEW_CANDIDATE", event["event_id"]
        if recent is not None:
            elapsed = (at - recent["at"]).total_seconds()
            if elapsed < 0:
                decision, anchor = "HELD_OUT_OF_ORDER", recent["event_id"]
            elif elapsed < self.cooldown_seconds:
                decision, anchor = "SUPPRESSED_RECENT_PLATE", recent["event_id"]
        # 6-5. 과거에 사용한 UUID를 새 통과 이벤트로 재사용할 수 없습니다.
        if decision == "NEW_CANDIDATE" and event["event_id"] in self._ids:
            decision = "HELD_EVENT_ID_REUSE"
        # 6-6. 신규 후보일 때만 전송 대기 상태와 요청 본문을 저장합니다.
        record = {"signature": signature, "decision": decision, "event_id": anchor,
                  "receipt_state": "AWAITING_RESULT" if decision == "NEW_CANDIDATE" else "NOT_CREATED",
                  "payload": dict(event) if decision == "NEW_CANDIDATE" else None, "result": None}
        self._tracks[key] = record
        if decision == "NEW_CANDIDATE":
            self._recent[recent_key] = {"at": at, "event_id": anchor}
            self._ids[event["event_id"]] = key
        return self._decision(record)

    # 7. 서버 응답 기록 진입점
    # 함수 설명: record_result() — 서버 응답을 스레드 안전하게 기존 이벤트에 연결합니다.
    def record_result(self, session_id, track_id, camera_id, result):
        # 7-1. 후보 판단과 동일한 잠금으로 응답 상태의 경쟁 변경을 방지합니다.
        with self._lock:
            return self._record_result(session_id, track_id, camera_id, result)

    # 8. 응답 검증 및 최종 상태 보존
    # 함수 설명: _record_result() — 원본 이벤트 식별자와 응답 상태의 정합성을 검사하고 기록합니다.
    def _record_result(self, session_id, track_id, camera_id, result):
        record = self._tracks.get(self._key(session_id, track_id, camera_id))
        if record is None or record["decision"] != "NEW_CANDIDATE":
            raise ValueError("생성된 후보의 응답만 기록할 수 있습니다.")
        # 8-1. 응답 상태별로 서버가 식별정보를 확인한 상태인지 검사합니다.
        verified_states = {"APPLIED", "UNCHANGED", "HELD"}
        other_states = {"REJECTED", "AUTH_REQUIRED", "DELIVERY_UNKNOWN"}
        if (not isinstance(result, dict) or result.get("event_id") != record["event_id"] or
                result.get("event_type") != "VEHICLE_PASSAGE" or result.get("automatic_retry_allowed") is not False or
                not isinstance(result.get("state"), str) or result["state"] not in verified_states | other_states or
                result.get("receipt_verified") is not (result.get("state") in verified_states)):
            raise ValueError("원본 이벤트와 일치하는 검증 결과가 필요합니다.")
        # 8-2. 필요한 필드만 복사하며, 이미 기록한 결과를 다른 상태로 변경하지 못하게 합니다.
        saved = {key: result[key] for key in ("event_id", "event_type", "state", "receipt_verified", "automatic_retry_allowed")}
        if record["result"] is not None and record["result"] != saved:
            raise ValueError("기록된 응답을 다른 상태로 덮어쓸 수 없습니다.")
        # 8-3. 타임아웃 등 DELIVERY_UNKNOWN도 무조건 재전송하지 않고 상태를 보관합니다.
        record["result"] = saved
        record["receipt_state"] = result["state"]
        return self._decision(record, "RESULT_RECORDED")

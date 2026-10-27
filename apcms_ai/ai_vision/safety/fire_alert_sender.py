"""저장된 화재·연기 사건 이력을 검증하여 알림 요청을 생성/전송합니다.

기존 live_fire_smoke.py와 독립적으로 실행합니다. 기본 동작은 dry-run이며
명시적인 --send와 --url 없이는 어떠한 HTTP 요청도 발생하지 않습니다.

서버 API 규격이 확정되기 전의 임시 계약(v1)입니다. 실제 Spring Boot
Controller의 경로/DTO가 확정되면 본 파일만 수정하여 맞추면 됩니다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = "1.0"
ACTIONABLE_STATUSES = frozenset({"SUSPECTED", "REOPENED", "CLEARED"})
ALL_STATUSES = ACTIONABLE_STATUSES | {"ONGOING", "SESSION_ENDED"}
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_TRANSITIONS = 10000


# 1. 저장된 결과 파일 검증

def _reject_invalid_number(value):
    raise ValueError(f"유효하지 않은 JSON 숫자: {value}")


def _reject_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"JSON 중복 키: {key}")
        obj[key] = value
    return obj


def _read_json_object(path: Path) -> dict:
    """1-1. 파일 크기 및 JSON 타입을 확인합니다."""
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError(f"JSON 크기가 허용 한도를 초과했습니다: {path.name}")
    result = json.loads(
        raw.decode("utf-8-sig"), parse_constant=_reject_invalid_number,
        object_pairs_hook=_reject_duplicate_keys,
    )
    if not isinstance(result, dict):
        raise ValueError(f"JSON의 최상위 값은 객체여야 합니다: {path.name}")
    return result


def _required_string(obj: dict, field: str) -> str:
    value = obj.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(f"{field}에는 비어 있지 않은 문자열(최대 256자)이 필요합니다.")
    return value


def _required_number(obj: dict, field: str, minimum: float, maximum: float) -> float:
    value = obj.get(field)
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{field} 값이 올바르지 않습니다.")
    return float(value)


def _required_integer(obj: dict, field: str, minimum: int = 0) -> int:
    value = obj.get(field)
    if type(value) is not int or value < minimum:
        raise ValueError(f"{field}에는 {minimum} 이상의 정수가 필요합니다.")
    return value


def _iso_utc(text: str) -> str:
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("UTC 기록 시각 형식이 올바르지 않습니다.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("UTC 기록 시각에는 UTC 시간대가 필요합니다.")
    return parsed.isoformat()


def _normalize_transition(transition: dict, summary: dict) -> dict:
    """1-2. 임의 데이터 대신 검증된 사건 정보만 요청 DTO로 옮깁니다."""
    if not isinstance(transition, dict):
        raise ValueError("사건 전이 항목은 객체여야 합니다.")
    incident_id = _required_string(transition, "event_id")
    region_id = _required_string(transition, "region_id")
    hazard = _required_string(transition, "type")
    status = _required_string(transition, "status")
    if hazard not in {"FIRE", "SMOKE"} or status not in ALL_STATUSES:
        raise ValueError("지원하지 않는 화재/연기 유형 또는 사건 상태입니다.")
    source_seconds = _required_number(transition, "source_seconds", 0, 86400 * 365)
    confidence = _required_number(transition, "confidence", 0, 1)
    frame = _required_integer(transition, "frame_index")
    bbox = transition.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4 or any(type(x) is not int or x < 0 for x in bbox):
        raise ValueError("bbox는 4개 비음수 정수 배열이어야 합니다.")
    if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
        raise ValueError("bbox 시작 좌표가 종료 좌표보다 작아야 합니다.")
    hits = _required_integer(transition, "hits_in_window")
    observed_at = _iso_utc(_required_string(transition, "logged_at_utc"))
    source_type = _required_string(summary, "source")
    if source_type not in ("CAMERA", "VIDEO"):
        raise ValueError("알 수 없는 입력 종류입니다.")
    source_name = _required_string(summary, "source_name")
    started = _iso_utc(_required_string(summary, "started_at_utc"))
    # 미확인/오래된 메타데이터를 운영으로 오인하지 않도록 record_type을 엄격하게 판별합니다.
    record_type = summary.get("record_type")
    if record_type == "FIRE_SMOKE_LIVE_TEST":
        is_test = True
    elif record_type == "FIRE_SMOKE_LIVE_PRODUCTION" and source_type == "CAMERA":
        is_test = False
    else:
        raise ValueError("허용되지 않은 record_type/source 조합입니다. 운영은 CAMERA만 허용합니다.")

    # 같은 사건의 재발생과 해제는 각각 별도 전이로 전송해야 합니다.
    identity = {
        "schema_version": SCHEMA_VERSION,
        "session_started_at_utc": started,
        "incident_id": incident_id,
        "region_id": region_id,
        "status": status,
        "frame_index": frame,
        "source_seconds": source_seconds,
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "transition_id": digest,
        "incident_id": incident_id,
        "region_id": region_id,
        "hazard_type": hazard,
        "status": status,
        "observed_at_utc": observed_at,
        "source_seconds": source_seconds,
        "frame_index": frame,
        "confidence": confidence,
        "bbox_xyxy": list(bbox),
        "hits_in_window": hits,
        "reason": transition.get("reason") if isinstance(transition.get("reason"), str) else None,
        "source": {"kind": source_type, "name": source_name},
        "session_started_at_utc": started,
        # 미확인 기록은 위에서 거부하며, 명시적 CAMERA 운영 기록만 is_test=False입니다.
        "is_test": is_test,
        "requires_human_review": True,
    }


def build_payloads(results_dir: Path, *, include_ongoing: bool = False,
                   include_session_ended: bool = False) -> list[dict]:
    """1-3. 기존 결과 폴더를 읽고 중복 없는 전송 후보를 만듭니다."""
    folder = Path(results_dir)
    summary = _read_json_object(folder / "summary.json")
    history = _read_json_object(folder / "incident_history.json")
    transitions = history.get("transitions")
    if not isinstance(transitions, list) or len(transitions) > MAX_TRANSITIONS:
        raise ValueError("사건 전이 목록이 올바르지 않거나 너무 깁니다.")

    allowed = set(ACTIONABLE_STATUSES)
    if include_ongoing:
        allowed.add("ONGOING")
    if include_session_ended:
        allowed.add("SESSION_ENDED")

    payloads = []
    seen = set()
    for transition in transitions:
        # 필터 적용 전에 전체 기록의 형식과 출처를 확인합니다.
        payload = _normalize_transition(transition, summary)
        if payload["status"] not in allowed:
            continue
        identity = payload["transition_id"]
        if identity not in seen:
            payloads.append(payload)
            seen.add(identity)
    return payloads


# 2. 외부 서버 전송 보호

# APCMS 팀 AWS 시험용 HTTP 예외. 다른 외부 HTTP/운영 이벤트에는 적용하지 않습니다.
_APCMS_AWS_TEST_HTTP_URL = "http://52.79.133.132:3000/admin-api/api/parking/ai/fire-alerts"


def _allow_explicit_apcms_aws_test_http(url: str) -> bool:
    """환경변수 명시 승인 + 시험 모드 + 정확한 목적지 URL 세 조건 모두 충족."""
    return (
        os.environ.get("SAFETY_TEST_AWS_HTTP", "").strip() == "1"
        and os.environ.get("SAFETY_CAMERA_SEND_MODE", "test").strip().lower() == "test"
        and url == _APCMS_AWS_TEST_HTTP_URL
    )


def validate_endpoint(url: str) -> str:
    """2-1. 기본 HTTPS만 허용하고 HTTP는 로컬 테스트 서버만 허용합니다."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("유효한 HTTPS API 주소가 필요합니다.")
    if parsed.fragment or any(ch.isspace() for ch in url):
        raise ValueError("API 주소에 fragment나 공백을 포함할 수 없습니다.")
    if parsed.scheme == "http" and parsed.hostname.lower() not in ("localhost", "127.0.0.1", "::1") and not _allow_explicit_apcms_aws_test_http(url):
        raise ValueError("외부 HTTP는 허용하지 않습니다. HTTPS 또는 localhost HTTP를 사용하세요.")
    try:
        _ = parsed.port
    except ValueError as error:
        raise ValueError("유효하지 않은 URL 포트입니다.") from error
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 2-2. Bearer 토큰이 다른 주소로 자동 전달되는 것을 금지합니다.
        return None


def _validate_success_ack(payload: dict, raw: bytes) -> None:
    """Spring Boot의 성공 응답을 확인한 뒤에만 전송 완료로 인정합니다.

    HTTP 2xx만으로 성공 처리하면 프록시 HTML, 빈 응답, 잘못된 ACK도
    fire_alert_sent_state.json에 기록되어 재전송이 영구적으로 누락될 수 있습니다.
    """
    try:
        ack = json.loads(
            raw.decode("utf-8"), parse_constant=_reject_invalid_number,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (ValueError, UnicodeError) as error:
        raise RuntimeError("HTTP 2xx 응답이 유효한 JSON ACK가 아닙니다.") from error
    if not isinstance(ack, dict):
        raise RuntimeError("서버 ACK는 JSON 객체여야 합니다.")
    if ack.get("transitionId") != payload["transition_id"]:
        raise RuntimeError("서버 ACK의 transitionId가 요청과 일치하지 않습니다.")
    if ack.get("outcome") not in ("STORED", "DUPLICATE"):
        raise RuntimeError("서버 ACK의 outcome이 STORED/DUPLICATE가 아닙니다.")
    event_id = ack.get("aiDetectionEventId")
    if type(event_id) is not int or event_id <= 0:
        raise RuntimeError("서버 ACK의 aiDetectionEventId가 올바르지 않습니다.")
    incident_id = ack.get("safetyIncidentId")
    if incident_id is not None and (type(incident_id) is not int or incident_id <= 0):
        raise RuntimeError("서버 ACK의 safetyIncidentId가 올바르지 않습니다.")
    count = ack.get("notificationsCreated")
    if type(count) is not int or count < 0:
        raise RuntimeError("서버 ACK의 notificationsCreated가 올바르지 않습니다.")
    if type(ack.get("isTest")) is not bool or ack["isTest"] is not payload["is_test"]:
        raise RuntimeError("서버 ACK의 isTest가 요청과 일치하지 않습니다.")
    if ack["outcome"] == "DUPLICATE" and count != 0:
        raise RuntimeError("중복 전이에 관리자 알림이 생성되었다는 응답입니다.")
    if payload["status"] == "CLEARED" and count != 0:
        raise RuntimeError("CLEARED 전이에 관리자 알림이 생성되었다는 응답입니다.")
    if payload["status"] == "CLEARED" and ack["outcome"] == "STORED" and incident_id is not None:
        raise RuntimeError("CLEARED 신규 저장이 업무 사건을 갱신했다는 응답입니다.")


def post_payload(payload: dict, url: str, *, token: str | None = None,
                 timeout: float = 5.0, max_retries: int = 2,
                 opener=None, sleep=time.sleep) -> int:
    """2-3. POST 전송. 반복 전송 시 서버는 X-Idempotency-Key를 반드시 처리해야 합니다."""
    validate_endpoint(url)
    if not (0 < timeout <= 60) or type(max_retries) is not int or not 0 <= max_retries <= 5:
        raise ValueError("timeout 또는 max_retries 범위를 확인하세요.")
    if token is not None and (not token or any(c in token for c in "\r\n")):
        raise ValueError("토큰 형식이 올바르지 않습니다.")
    handler = opener or urllib.request.build_opener(_NoRedirect())
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "X-Idempotency-Key": payload["transition_id"],
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(max_retries + 1):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with handler.open(request, timeout=timeout) as response:
                code = response.status
                raw_ack = response.read(16 * 1024 + 1)
                if 200 <= code < 300:
                    if len(raw_ack) > 16 * 1024:
                        raise RuntimeError("서버 ACK가 16KiB 제한을 초과했습니다.")
                    _validate_success_ack(payload, raw_ack)
                    return code
                if code not in RETRYABLE_STATUSES or attempt >= max_retries:
                    raise RuntimeError(f"HTTP 요청 실패: 상태 {code}")
        except urllib.error.HTTPError as error:
            code = error.code
            error.close()
            if code not in RETRYABLE_STATUSES or attempt >= max_retries:
                raise RuntimeError(f"HTTP 요청 실패: 상태 {code}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            if attempt >= max_retries:
                raise RuntimeError(f"HTTP 네트워크 오류: {type(error).__name__}") from error
        if attempt < max_retries:
            sleep(0.3 * (2 ** attempt))
    raise RuntimeError("HTTP 전송 실패")


# 2-4. 시험/운영 모드별 송신 허가 정책 (CLI/실시간 송신기 공통)
def validate_delivery_policy(payloads: list[dict], url: str, *,
                             allow_test_records: bool = False,
                             allow_production_records: bool = False) -> None:
    validate_endpoint(url)
    has_test = any(p["is_test"] is True for p in payloads)
    has_production = any(p["is_test"] is False for p in payloads)
    if has_test and has_production:
        raise ValueError("한 번의 요청에서 시험/운영 기록을 섞을 수 없습니다.")
    if has_test and not allow_test_records:
        raise ValueError("시험용 기록입니다. --allow-test-records가 필요합니다.")
    if has_production:
        if not allow_production_records:
            raise ValueError("운영 데이터 전송은 --allow-production-records가 필요합니다.")
        if allow_test_records:
            raise ValueError("운영 데이터 전송에 --allow-test-records를 함께 지정할 수 없습니다.")
        if urllib.parse.urlsplit(url).scheme != "https":
            raise ValueError("운영 데이터 전송은 HTTPS 주소만 허용합니다.")


# 3. 성공 기록과 재실행 제어

def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".fire-alert-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def send_pending(payloads: list[dict], url: str, *, state_file: Path,
                 token: str | None = None, timeout: float = 5.0,
                 max_retries: int = 2, post=post_payload) -> dict:
    """3-1. 성공한 전이 ID를 체크포인트에 저장하고 재실행 시 건너뜁니다.

    같은 state_file을 여러 프로세스가 동시에 수정하는 용도로는 사용하지 않습니다.
    """
    validate_endpoint(url)
    state_file = Path(state_file)
    if state_file.is_file():
        state = _read_json_object(state_file)
        acked = state.get("acknowledged_transition_ids")
        if not isinstance(acked, list) or not all(isinstance(x, str) and len(x) == 64 for x in acked):
            raise ValueError("기존 전송 체크포인트 파일이 올바르지 않습니다.")
        sent = set(acked)
    else:
        sent = set()
    successes, skipped = 0, 0
    for payload in payloads:
        identity = payload["transition_id"]
        if identity in sent:
            skipped += 1
            continue
        # 성공 응답을 받은 건에 대해서만 상태 저장 (실패 후 재실행 가능).
        post(payload, url, token=token, timeout=timeout, max_retries=max_retries)
        sent.add(identity)
        successes += 1
        _write_json_atomic(state_file, {"schema_version": SCHEMA_VERSION,
                                        "acknowledged_transition_ids": sorted(sent)})
    return {"total": len(payloads), "sent": successes, "already_sent": skipped}


# 4. 독립 명령행 실행

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="화재·연기 사건 API 요청 검증기 (기본값: 전송 없는 미리보기)")
    parser.add_argument("--results", type=Path, required=True, help="summary.json/incident_history.json이 있는 폴더")
    parser.add_argument("--include-ongoing", action="store_true", help="주기적 ONGOING 기록 포함")
    parser.add_argument("--include-session-ended", action="store_true", help="SESSION_ENDED 포함 (화재 진화 아님)")
    parser.add_argument("--preview-out", type=Path, help="미리보기 요청 JSON을 지정 경로에 저장")
    parser.add_argument("--send", action="store_true", help="실제 HTTP 전송(명시적 선택 필요)")
    parser.add_argument("--url", help="Spring Boot 이벤트 수신 API (확정된 URL만 사용)")
    parser.add_argument("--allow-test-records", action="store_true", help="시험용 기록을 실제 HTTP로 전송하도록 별도 허용")
    parser.add_argument("--allow-production-records", action="store_true",
                        help="운영 CAMERA 기록의 실제 전송을 별도로 승인 (HTTPS 전용)")
    parser.add_argument("--token-env", default="FIRE_ALERT_TOKEN", help="Bearer 토큰을 읽을 환경 변수명")
    parser.add_argument("--state-file", type=Path, help="중복 전송 방지 체크포인트 저장 위치")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-retries", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        payloads = build_payloads(args.results, include_ongoing=args.include_ongoing,
                                  include_session_ended=args.include_session_ended)
        kinds = {status: sum(item["status"] == status for item in payloads) for status in sorted(ALL_STATUSES)}
        print(f"[검증] 전송 후보 {len(payloads)}개 | 상태별: {kinds}")
        if args.preview_out is not None:
            _write_json_atomic(args.preview_out, {"schema_version": SCHEMA_VERSION, "alerts": payloads})
            print(f"[미리보기 저장] {args.preview_out}")
        if not args.send:
            print("[DRY-RUN] HTTP 요청 없음. --send를 명시해야 전송됩니다.")
            for item in payloads[:5]:
                print(f"  {item['hazard_type']} {item['status']} | {item['source_seconds']:.3f}s | "
                      f"incident={item['incident_id'][:8]} | transition={item['transition_id'][:12]}")
            if len(payloads) > 5:
                print(f"  ... 추가 {len(payloads) - 5}개")
            return 0
        if not args.url:
            raise ValueError("실제 전송에는 --url이 필요합니다.")
        validate_delivery_policy(payloads, args.url,
                                 allow_test_records=args.allow_test_records,
                                 allow_production_records=args.allow_production_records)
        token = os.environ.get(args.token_env) or None
        if any(p["is_test"] is False for p in payloads) and not token:
            raise ValueError("운영 전송에는 --token-env로 지정한 환경변수의 인증키가 필요합니다.")
        state_file = args.state_file or (args.results / "fire_alert_sent_state.json")
        outcome = send_pending(payloads, args.url, state_file=state_file, token=token,
                               timeout=args.timeout, max_retries=args.max_retries)
        print(f"[전송 완료] 신규 {outcome['sent']}건 | 이미 전송 {outcome['already_sent']}건")
        return 0
    except (ValueError, FileNotFoundError, OSError, RuntimeError, UnicodeError, json.JSONDecodeError) as error:
        # Bearer 토큰이나 요청 본문은 콘솔 오류에 포함하지 않습니다.
        print(f"[실패] {error.__class__.__name__}: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

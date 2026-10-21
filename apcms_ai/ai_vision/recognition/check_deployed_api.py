# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/check_deployed_api.py

"""Vision API의 상태·선택적 이미지 응답을 점검합니다. Boot 이벤트는 전송하지 않습니다."""

import argparse
import hashlib
import io
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from ai_vision.upload_policy import MAX_UPLOAD_BYTES, MAX_IMAGE_PIXELS
from ai_vision.recognition.local_io import decode_object, write_json_atomic
from ai_vision.recognition.plate_review import KOREAN_PLATE_PATTERN, REVIEW_REASON_CODES, plate_review_reasons

PLATE_TYPES = ("KOREAN_VALID", "FOREIGN_OR_OTHER", "REVIEW", "OCR_FAILED", "NOT_DETECTED", "CROP_FAILED")


def _image_payload(path):
    from PIL import Image, UnidentifiedImageError
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_UPLOAD_BYTES + 1)
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("점검 이미지는 0바이트 초과 10MB 이하로 지정합니다.")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError("이미지 픽셀 한도 초과")
            mime = Image.MIME.get(image.format)
            image.verify()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise ValueError("점검 이미지 형식을 확인해 주세요.") from error
    if not mime or not mime.startswith("image/"):
        raise ValueError("점검 이미지 형식을 확인해 주세요.")
    return raw, mime


def _diagnostics(headers):
    request_id, timing = headers.get("X-Request-ID"), headers.get("Server-Timing")
    if request_id is None and timing is None:
        return "MISSING"
    if (isinstance(request_id, str) and re.fullmatch(r"[0-9a-f]{32}", request_id) and
            _server_duration(headers) is not None):
        return "PRESENT"
    return "INVALID"


def _server_duration(headers):
    timing = headers.get("Server-Timing")
    if not isinstance(timing, str) or len(timing) > 1024:
        return None
    match = re.search(r"(?:^|,)\s*app;dur=([0-9]+(?:\.[0-9]+)?)(?:\s*,|$)", timing)
    if match is None:
        return None
    value = float(match.group(1))
    return value if math.isfinite(value) else None


def _recognition_result(body):
    count, vehicles = body.get("vehicle_count"), body.get("vehicles")
    if (type(body.get("success")) is not bool or type(count) is not int or not 0 <= count <= 10000 or
            not isinstance(vehicles, list) or len(vehicles) != count or body["success"] != bool(count)):
        raise ValueError("차량 응답 형식 오류")
    kinds = {}
    for vehicle in vehicles:
        if not isinstance(vehicle, dict) or not isinstance(vehicle.get("plate_number"), str):
            raise ValueError("차량 번호판 필드 오류")
        kind = vehicle.get("plate_type")
        if kind not in PLATE_TYPES:
            raise ValueError("차량 번호판 형식 오류")
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind == "KOREAN_VALID":
            if not KOREAN_PLATE_PATTERN.fullmatch(vehicle["plate_number"]):
                raise ValueError("유효 판정과 번호판 문자열 불일치")
        # 응답에 사유가 있다면 원문에서 계산한 사유와 일치해야 합니다.
        if "review_reasons" in vehicle and vehicle["review_reasons"] != plate_review_reasons(vehicle["plate_number"], kind):
            raise ValueError("번호판 검토 사유 불일치")
    return count, vehicles, kinds


def validate_check_inputs(base_url="http://127.0.0.1:8000", image=None, expected_plate=None,
                          expected_vehicle_count=None, require_diagnostics=False, timeout=120, *,
                          expected_ocr_text=None, expected_plate_type=None, expected_review_reason=None,
                          expected_image_sha256=None):
    # 1. 잘못된 입력은 세션 생성·네트워크 접근 전에 거부합니다.
    parsed = urlsplit(base_url)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None or
            parsed.password is not None or parsed.query or parsed.fragment or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in base_url)):
        raise ValueError("인증정보·쿼리 없는 Vision API base URL을 지정합니다.")
    parsed.port
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300 or type(require_diagnostics) is not bool:
        raise ValueError("점검 시간·진단 옵션을 확인해 주세요.")
    if expected_plate is not None and (not isinstance(expected_plate, str) or not KOREAN_PLATE_PATTERN.fullmatch(expected_plate)):
        raise ValueError("기대 번호판은 한국 번호판 형식이어야 합니다.")
    if expected_vehicle_count is not None and (type(expected_vehicle_count) is not int or not 0 <= expected_vehicle_count <= 10000):
        raise ValueError("기대 차량 수를 확인해 주세요.")
    if expected_ocr_text is not None and (not isinstance(expected_ocr_text, str) or len(expected_ocr_text) > 1024):
        raise ValueError("기대 OCR 문자열을 확인해 주세요.")
    if expected_plate_type is not None and expected_plate_type not in PLATE_TYPES:
        raise ValueError("기대 번호판 형식을 확인해 주세요.")
    if expected_review_reason is not None and expected_review_reason not in REVIEW_REASON_CODES:
        raise ValueError("기대 검토 사유를 확인해 주세요.")
    if expected_plate is not None and ((expected_ocr_text is not None and expected_ocr_text != expected_plate) or
                                      expected_plate_type not in (None, "KOREAN_VALID") or expected_review_reason is not None):
        raise ValueError("기대 번호판 조건이 서로 충돌합니다.")
    vehicle_expected = any(value is not None for value in
                           (expected_plate, expected_ocr_text, expected_plate_type, expected_review_reason))
    if (image is None and (vehicle_expected or expected_vehicle_count is not None)) or (vehicle_expected and expected_vehicle_count == 0):
        raise ValueError("기대 결과와 점검 이미지 지정이 일치하지 않습니다.")
    payload = _image_payload(image) if image is not None else None
    if expected_image_sha256 is not None:
        if (not isinstance(expected_image_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_image_sha256) is None or
                payload is None or hashlib.sha256(payload[0]).hexdigest() != expected_image_sha256):
            raise ValueError("사전 검사 후 이미지 내용이 변경되었습니다.")
    return payload


def run_check(base_url="http://127.0.0.1:8000", image=None, expected_plate=None,
              expected_vehicle_count=None, require_diagnostics=False, timeout=120, session_factory=None, *,
              expected_ocr_text=None, expected_plate_type=None, expected_review_reason=None, expected_image_sha256=None):
    payload = validate_check_inputs(base_url, image, expected_plate, expected_vehicle_count, require_diagnostics,
                                    timeout, expected_ocr_text=expected_ocr_text, expected_plate_type=expected_plate_type,
                                    expected_review_reason=expected_review_reason, expected_image_sha256=expected_image_sha256)
    vehicle_expected = any(value is not None for value in
                           (expected_plate, expected_ocr_text, expected_plate_type, expected_review_reason))
    session = (requests.Session if session_factory is None else session_factory)()
    checks = []
    try:
        session.trust_env = False
        for protocol in ("http://", "https://"):
            session.mount(protocol, HTTPAdapter(max_retries=0))
        for name in ("health", "ready", "recognize"):
            if name == "recognize" and (payload is None or any(c["status"] != "PASS" for c in checks)):
                checks.append({"name": name, "status": "NOT_RUN",
                               "reason": "NO_IMAGE" if payload is None else "PREREQUISITE_FAILED"})
                continue
            response = None
            check = {"name": name, "status": "FAIL", "http_status": None}
            try:
                options = {"timeout": (3, timeout), "allow_redirects": False, "stream": True}
                url = base_url.rstrip("/") + "/" + name
                if name == "recognize":
                    response = session.post(url, files={"file": ("sample", payload[0], payload[1])}, **options)
                else:
                    response = session.get(url, **options)
                check["http_status"] = response.status_code
                diagnostics = _diagnostics(response.headers)
                check["diagnostics"] = diagnostics
                if diagnostics == "PRESENT":
                    check.update(request_id=response.headers["X-Request-ID"], server_duration_ms=_server_duration(response.headers))
                if response.status_code != 200:
                    check["reason"] = "HTTP_STATUS"
                    continue
                raw = bytearray()
                for chunk in response.iter_content(chunk_size=8192):
                    if not isinstance(chunk, bytes) or len(raw) + len(chunk) > 1024 * 1024:
                        raise ValueError("응답 크기·형식 오류")
                    raw.extend(chunk)
                body = decode_object(bytes(raw).decode("utf-8-sig"))
                if name == "health":
                    valid = body.get("status") == "ok" and body.get("scope") == "PROCESS_ONLY"
                elif name == "ready":
                    valid = body.get("status") == "CHECKED" and body.get("scope") == "FILES_AND_STORAGE_ONLY"
                else:
                    count, vehicles, kinds = _recognition_result(body)
                    check.update(vehicle_count=count, plate_type_counts=kinds)
                    valid = expected_vehicle_count is None or count == expected_vehicle_count
                    if vehicle_expected:
                        # 3. 여러 차량의 서로 다른 필드를 합쳐서 통과시키지 않습니다.
                        matched = any(
                            (expected_plate is None or (v["plate_number"] == expected_plate and v["plate_type"] == "KOREAN_VALID")) and
                            (expected_ocr_text is None or v["plate_number"] == expected_ocr_text) and
                            (expected_plate_type is None or v["plate_type"] == expected_plate_type) and
                            (expected_review_reason is None or expected_review_reason in v.get("review_reasons", []))
                            for v in vehicles)
                        check["expected_vehicle_matched"] = matched
                        if expected_plate is not None:
                            check["expected_plate_matched"] = matched
                        valid = valid and matched
                valid = valid and diagnostics != "INVALID" and (not require_diagnostics or diagnostics == "PRESENT")
                check.update(status="PASS" if valid else "FAIL", reason="MATCHED" if valid else "RESPONSE_MISMATCH")
            except requests.Timeout:
                check["reason"] = "TIMEOUT"
            except requests.RequestException:
                check["reason"] = "CONNECTION_ERROR"
            except (OSError, ValueError, TypeError):
                check["reason"] = "INVALID_RESPONSE"
            finally:
                if response is not None:
                    try:
                        response.close()
                    except Exception:
                        check.update(status="FAIL", reason="RESPONSE_CLOSE_FAILED")
                checks.append(check)
    finally:
        try:
            session.close()
        except Exception:
            checks.append({"name": "session_cleanup", "status": "FAIL", "reason": "SESSION_CLOSE_FAILED"})
    # 2. 이미지·번호판 원문·내부 경로는 점검 보고서에 저장하지 않습니다.
    return {"record_type": "VISION_API_CHECK", "status": "PASS" if all(c["status"] != "FAIL" for c in checks) else "FAIL",
            "recognition_tested": any(c["name"] == "recognize" and c["status"] != "NOT_RUN" for c in checks),
            "checks": checks, "automatic_retry": False, "scope": "VISION_API_ONLY"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--expected-plate")
    parser.add_argument("--expected-ocr-text")
    parser.add_argument("--expected-plate-type", choices=PLATE_TYPES)
    parser.add_argument("--expected-review-reason", choices=sorted(REVIEW_REASON_CODES))
    parser.add_argument("--expected-vehicle-count", type=int)
    parser.add_argument("--require-diagnostics", action="store_true")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        # 새 폴더를 먼저 확보해 결과를 저장할 수 없는 상태에서 요청하지 않습니다.
        args.output_dir.mkdir(parents=True, exist_ok=False)
        report = run_check(args.base_url, args.image, args.expected_plate, args.expected_vehicle_count,
                           args.require_diagnostics, args.timeout, expected_ocr_text=args.expected_ocr_text,
                           expected_plate_type=args.expected_plate_type, expected_review_reason=args.expected_review_reason)
        write_json_atomic(args.output_dir / "api_check.json", report)
    except (OSError, ValueError, TypeError):
        parser.exit(2, "API 점검 입력·새 출력 폴더를 확인해 주세요.\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

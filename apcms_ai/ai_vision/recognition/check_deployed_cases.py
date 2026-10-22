# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/check_deployed_cases.py

"""로컬 JSON 사례 목록으로 배포 Vision API를 순차 점검합니다."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from ai_vision.recognition.check_deployed_api import run_check, validate_check_inputs
from ai_vision.recognition.local_io import read_json, write_json_atomic


EXPECTATIONS = frozenset({"expected_plate", "expected_vehicle_count", "expected_ocr_text",
                          "expected_plate_type", "expected_review_reason"})


def load_cases(manifest, base_url, require_diagnostics=False, timeout=120):
    # 1. 모든 사례를 먼저 검사하여 뒤쪽 입력 오류로 앞쪽 이미지만 전송되는 일을 줄입니다.
    manifest = Path(manifest).resolve()
    document = read_json(manifest, max_bytes=256 * 1024)
    cases = document.get("cases")
    if set(document) != {"cases"} or not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise ValueError("사례 목록은 cases 배열 1~100개로 지정합니다.")
    prepared, identifiers = [], set()
    for case in cases:
        if not isinstance(case, dict) or set(case) - (EXPECTATIONS | {"id", "image"}):
            raise ValueError("지원하지 않는 사례 필드입니다.")
        identifier, image = case.get("id"), case.get("image")
        if (not isinstance(identifier, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", identifier) is None or
                identifier in identifiers or not isinstance(image, str) or not image.strip()):
            raise ValueError("고유한 사례 ID와 이미지 경로를 지정합니다.")
        identifiers.add(identifier)
        options = {key: case[key] for key in EXPECTATIONS if key in case}
        if not options or any(value is None for value in options.values()):
            raise ValueError("사례마다 최소 한 개의 기대값을 지정합니다.")
        image_path = Path(image)
        options["image"] = image_path if image_path.is_absolute() else manifest.parent / image_path
        payload = validate_check_inputs(base_url, require_diagnostics=require_diagnostics, timeout=timeout, **options)
        options["expected_image_sha256"] = hashlib.sha256(payload[0]).hexdigest()
        prepared.append((identifier, options))
    return prepared


def run_cases(manifest, output_dir, base_url="http://127.0.0.1:8000", require_diagnostics=False,
              timeout=120, session_factory=None):
    cases = load_cases(manifest, base_url, require_diagnostics, timeout)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    results = []
    # 2. 순차 실행하고 매 사례 후 저장하므로 중단되더라도 완료한 결과를 확인할 수 있습니다.
    report = {"record_type": "VISION_API_CASE_CHECK", "scope": "VISION_API_ONLY", "status": "INCOMPLETE",
              "total_cases": len(cases), "completed_cases": 0, "passed_cases": 0, "failed_cases": 0,
              "automatic_retry": False, "cases": results}
    write_json_atomic(output_dir / "api_cases.json", report)
    for index, (_, options) in enumerate(cases, 1):
        try:
            result = run_check(base_url, require_diagnostics=require_diagnostics, timeout=timeout,
                               session_factory=session_factory, **options)
        except (OSError, ValueError, TypeError):
            # 사전 검사 후 이미지가 삭제되어도 예외 원문 없이 실패를 기록합니다.
            result = {"status": "FAIL", "reason": "CASE_INPUT_CHANGED", "recognition_tested": False}
        # 3. 입력 ID에도 개인정보가 있을 수 있으므로 결과에는 사례 순번만 저장합니다.
        results.append({"case_index": index, "result": result})
        report["completed_cases"] = index
        report["passed_cases"] += int(result["status"] == "PASS")
        report["failed_cases"] += int(result["status"] != "PASS")
        if index == len(cases):
            report["status"] = "FAIL" if report["failed_cases"] else "PASS"
        write_json_atomic(output_dir / "api_cases.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--require-diagnostics", action="store_true")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    try:
        report = run_cases(args.manifest, args.output_dir, args.base_url, args.require_diagnostics, args.timeout)
    except (OSError, ValueError, TypeError):
        parser.exit(2, "사례 목록·이미지·기대값·새 출력 폴더를 확인해 주세요.\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

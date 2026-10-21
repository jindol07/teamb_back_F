# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/deployment_readiness.py

"""모델 파일과 결과 볼륨을 검사합니다. 추론 준비 완료 판정은 아닙니다."""

import argparse
import json
import tempfile
from pathlib import Path

from ai_vision.paths import MODEL_DIR, RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic, read_json
from ai_vision.recognition.model_files import require_model_file
from ai_vision.recognition.ocr_configuration import local_ocr_options, OCRConfigurationError


def check_readiness(model_dir=MODEL_DIR, result_dir=RESULT_DIR):
    checks = []
    for name in ("yolo11n.pt", "license_plate_yolov8n.pt"):
        try:
            require_model_file(Path(model_dir) / name)
            state = "READABLE"
        except OSError:
            state = "UNAVAILABLE"
        checks.append({"name": name, "status": state})
    # 1. os.access 결과만 믿지 않고 실제로 작은 JSON을 쓰고 읽은 뒤 제거합니다.
    try:
        with tempfile.TemporaryDirectory(prefix=".vision-probe-", dir=result_dir) as folder:
            path = Path(folder) / "check.json"
            write_json_atomic(path, {"probe": True})
            if read_json(path) != {"probe": True}:
                raise ValueError("볼륨 검증 실패")
        storage = "WRITABLE"
    except (OSError, ValueError):
        storage = "UNAVAILABLE"
    checks.append({"name": "result_storage", "status": storage})
    try:
        options = local_ocr_options(model_dir)
        ocr = "LOCAL_FILES_CHECKED" if options else "CACHE_OR_DOWNLOAD_NOT_CHECKED"
    except OCRConfigurationError:
        ocr = "UNAVAILABLE"
    checks.append({"name": "ocr_models", "status": ocr})
    # 2. 내부 경로·예외 원문은 API 응답에 포함하지 않습니다.
    return {"status": "BLOCKED" if any(c["status"] == "UNAVAILABLE" for c in checks) else "CHECKED",
            "scope": "FILES_AND_STORAGE_ONLY", "checks": checks,
            "unverified": ["PACKAGE_IMPORT", "MODEL_INFERENCE", "GPU", "CAMERA", "BOOT_AND_DATABASE"]}


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    report = check_readiness()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())

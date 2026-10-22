# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/runtime_environment.py

"""모델을 import하지 않고 개발 환경 버전 정보를 수집·비교합니다."""

import platform
import sys
from importlib import metadata


PACKAGES = ("fastapi", "starlette", "httpx", "httpx2", "anyio", "uvicorn", "python-multipart",
            "numpy", "opencv-python", "opencv-contrib-python", "ultralytics", "lap", "torch",
            "paddlepaddle", "paddlepaddle-gpu", "paddleocr", "paddlex", "Pillow", "requests", "python-dotenv")


def collect_snapshot(version_reader=None):
    reader = metadata.version if version_reader is None else version_reader
    versions = {}
    # 1. 환경변수·경로·접속 정보 대신 설치 메타데이터만 읽습니다.
    for name in PACKAGES:
        try:
            versions[name] = reader(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return {"record_type": "VISION_RUNTIME_SNAPSHOT", "python": platform.python_version(),
            "implementation": platform.python_implementation(), "system": platform.system(),
            "machine": platform.machine(), "virtualenv": sys.prefix != sys.base_prefix, "packages": versions}


def validate_snapshot(value):
    keys = {"record_type", "python", "implementation", "system", "machine", "virtualenv", "packages"}
    if not isinstance(value, dict) or set(value) != keys or value["record_type"] != "VISION_RUNTIME_SNAPSHOT":
        raise ValueError("Vision 환경 버전 기록이 필요합니다.")
    if (type(value["virtualenv"]) is not bool or
            any(not isinstance(value[key], str) or not 1 <= len(value[key]) <= 128
                for key in ("python", "implementation", "system", "machine"))):
        raise ValueError("Python·운영체제 정보가 올바르지 않습니다.")
    packages = value["packages"]
    if (not isinstance(packages, dict) or set(packages) != set(PACKAGES) or
            any(item is not None and (not isinstance(item, str) or not 1 <= len(item) <= 128) for item in packages.values())):
        raise ValueError("패키지 버전 기록이 올바르지 않습니다.")
    return value


def compare_snapshots(expected, actual):
    validate_snapshot(expected)
    validate_snapshot(actual)
    differences = []
    for field in ("python", "implementation", "system", "machine", "virtualenv"):
        if expected[field] != actual[field]:
            differences.append({"field": field, "expected": expected[field], "actual": actual[field]})
    for name in PACKAGES:
        if expected["packages"][name] != actual["packages"][name]:
            differences.append({"field": "packages." + name, "expected": expected["packages"][name], "actual": actual["packages"][name]})
    # 2. 일치는 버전 정보의 일치이며 설치 성공·추론 호환성 판정이 아닙니다.
    return {"record_type": "VISION_RUNTIME_COMPARISON", "matches": not differences, "differences": differences}

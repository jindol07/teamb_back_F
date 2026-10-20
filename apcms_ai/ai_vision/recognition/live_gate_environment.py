# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_environment.py

"""모델을 불러오지 않고 패키지 설치 정보와 로컬 가중치 파일을 확인합니다."""

from importlib import metadata
from pathlib import Path

from ai_vision.paths import MODEL_DIR


PACKAGES = {
    "numpy": ("numpy",), "opencv": ("opencv-contrib-python", "opencv-python",
                                      "opencv-contrib-python-headless", "opencv-python-headless"),
    "ultralytics": ("ultralytics",), "torch": ("torch",), "lap": ("lap",),
    "paddleocr": ("paddleocr",), "paddle": ("paddlepaddle", "paddlepaddle-gpu"),
    "requests": ("requests",),
}


def check_environment(model_dir=MODEL_DIR, version_reader=None):
    reader = metadata.version if version_reader is None else version_reader
    checks = []
    # 1. 설치 메타데이터만 읽습니다. import 성공·버전 호환성까지 보장하지 않습니다.
    for name, alternatives in PACKAGES.items():
        installed = {}
        for distribution in alternatives:
            try:
                installed[distribution] = reader(distribution)
            except metadata.PackageNotFoundError:
                continue
        checks.append({"name": name, "status": "FOUND" if installed else "MISSING",
                       "installed": installed, "scope": "PACKAGE_METADATA_ONLY"})
    # 2. YOLO 가중치는 파일 존재와 크기만 확인하고 역직렬화·다운로드하지 않습니다.
    for name in ("yolo11n.pt", "license_plate_yolov8n.pt"):
        path = Path(model_dir) / name
        try:
            size = path.stat().st_size if path.is_file() else 0
            state = "FOUND" if size > 0 else "MISSING"
        except OSError:
            size, state = 0, "UNREADABLE"
        checks.append({"name": name, "status": state, "bytes": size, "scope": "FILE_PRESENCE_ONLY"})
    return checks

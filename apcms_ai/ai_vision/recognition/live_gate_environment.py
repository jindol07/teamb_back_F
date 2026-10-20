# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_environment.py

"""모델을 불러오지 않고 패키지 설치 정보와 로컬 가중치 파일을 확인합니다."""

# 1. 외부 패키지 설치 메타데이터 조회 도구
from importlib import metadata
# 1-1. 모델 파일의 존재·크기를 확인하는 경로 도구
from pathlib import Path

# 1-2. 프로젝트 공통 모델 폴더 경로를 불러옵니다.
from ai_vision.paths import MODEL_DIR


# 2. 점검할 의존 패키지와 대체 가능한 배포 이름
# 2-1. 예: opencv는 여러 배포판 중 하나라도 있으면 FOUND로 분류합니다.
PACKAGES = {
    "numpy": ("numpy",), "opencv": ("opencv-contrib-python", "opencv-python",
                                      "opencv-contrib-python-headless", "opencv-python-headless"),
    "ultralytics": ("ultralytics",), "torch": ("torch",), "lap": ("lap",),
    "paddleocr": ("paddleocr",), "paddle": ("paddlepaddle", "paddlepaddle-gpu"),
    "requests": ("requests",),
}


# 3. 무거운 모델을 로드하지 않고 설치 준비 상태를 점검합니다.
# 3-1. version_reader는 테스트 시 가짜 메타데이터 조회 함수를 주입할 수 있습니다.
# 함수 설명: check_environment() — 설치 메타데이터와 가중치 파일의 존재만 검사합니다. 추론이나 모델 로딩은 수행하지 않습니다.
def check_environment(model_dir=MODEL_DIR, version_reader=None):
    # 3-2. 기본은 importlib.metadata.version으로 설치 버전을 조회합니다.
    reader = metadata.version if version_reader is None else version_reader
    checks = []
    # 1. 설치 메타데이터만 읽습니다. import 성공·버전 호환성까지 보장하지 않습니다.
    # 4. 패키지별로 발견된 배포 이름과 버전을 수집합니다.
    for name, alternatives in PACKAGES.items():
        installed = {}
        # 4-1. 대체 후보를 각각 살펴보고 설치되지 않은 것만 건너뜁니다.
        for distribution in alternatives:
            try:
                installed[distribution] = reader(distribution)
            except metadata.PackageNotFoundError:
                continue
        # 4-2. 이 점검은 import·실제 추론 성공 여부를 보장하지 않습니다.
        checks.append({"name": name, "status": "FOUND" if installed else "MISSING",
                       "installed": installed, "scope": "PACKAGE_METADATA_ONLY"})
    # 2. YOLO 가중치는 파일 존재와 크기만 확인하고 역직렬화·다운로드하지 않습니다.
    # 5. 차량/번호판 가중치 파일 두 개를 확인합니다.
    for name in ("yolo11n.pt", "license_plate_yolov8n.pt"):
        path = Path(model_dir) / name
        # 5-1. 존재하고 크기가 0보다 큰지 확인하며 파일을 로드하지 않습니다.
        try:
            size = path.stat().st_size if path.is_file() else 0
            state = "FOUND" if size > 0 else "MISSING"
        except OSError:
            size, state = 0, "UNREADABLE"
        # 5-2. 모델 무결성·호환성을 증명하는 검사는 아닙니다.
        checks.append({"name": name, "status": state, "bytes": size, "scope": "FILE_PRESENCE_ONLY"})
    # 6. 패키지와 모델 파일의 검사 기록 리스트를 반환합니다.
    return checks

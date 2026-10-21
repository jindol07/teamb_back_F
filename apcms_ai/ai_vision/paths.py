# D:/finalProjectB/back/apcms_ai/ai_vision/paths.py

import os
import sys
from pathlib import Path, PureWindowsPath

# ai 프로젝트 최상위 폴더
BASE_DIR = Path(__file__).resolve().parent

# 공통 폴더
def _directory(name, default):
    # 1. Docker 볼륨 경로를 환경변수로 지정하고, 상대 경로는 실행 위치 대신 모듈 기준으로 해석합니다.
    raw = os.environ.get(name)
    if raw is None:
        return default
    if not raw.strip():
        raise ValueError(f"{name}에는 비어 있지 않은 경로가 필요합니다.")
    if any(char in raw for char in ("\x00", "\n", "\r")) or (sys.platform != "win32" and PureWindowsPath(raw).drive):
        raise ValueError(f"{name}에는 현재 운영체제에서 사용할 경로가 필요합니다.")
    path = Path(raw).expanduser()
    return (path if path.is_absolute() else BASE_DIR / path).resolve()


MODEL_DIR = _directory("VISION_MODEL_DIR", BASE_DIR / "models")
DATA_DIR = _directory("VISION_DATA_DIR", BASE_DIR / "data")
RESULT_DIR = _directory("VISION_RESULT_DIR", BASE_DIR / "results")
TEST_IMAGE_DIR = _directory("VISION_TEST_IMAGE_DIR", BASE_DIR / "test_images")

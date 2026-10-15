# 경로 모음

from pathlib import Path

# ai 프로젝트 최상위 폴더
BASE_DIR = Path(__file__).resolve().parent

# 공통 폴더
MODEL_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
RESULT_DIR = BASE_DIR / "results"
TEST_IMAGE_DIR = BASE_DIR / "test_images"
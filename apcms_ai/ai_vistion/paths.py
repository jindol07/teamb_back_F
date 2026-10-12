# 경로 모음

from pathlib import Path

# ai 프로젝트 최상위 폴더
BASE_DIR = Path(__file__).resolve().parent
print(F"BASE_DIR : {BASE_DIR}")

# 공통 폴더
MODEL_DIR = BASE_DIR / "models"
print(F"MODEL_DIR : {MODEL_DIR}")
DATA_DIR = BASE_DIR / "data"
print(F"DATA_DIR : {DATA_DIR}")
RESULT_DIR = BASE_DIR / "results"
print(F"RESULT_DIR : {RESULT_DIR}")
TEST_IMAGE_DIR = BASE_DIR / "test_images"
print(F"TEST_IMAGE_DIR : {TEST_IMAGE_DIR}")
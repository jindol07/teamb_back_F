from pathlib import Path
import sys
import easyocr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from paths import MODEL_DIR, DATA_DIR, RESULT_DIR, TEST_IMAGE_DIR

# 한국어 + 영어 문자 인식
reader = easyocr.Reader(
    ["ko", "en"], # 한국어와 영어 문자 세트 사용
    gpu=False # GPU 없이 CPU로 실행
)

image_path = str(RESULT_DIR / "plates" / "plate_1.jpg")

results = reader.readtext(image_path)

print("=== EasyOCR 결과 ===")

for bbox, text, confidence in results:
    print(
        f"인식 문자: {text}, "
        f"신뢰도: {confidence:.4f}"
    )
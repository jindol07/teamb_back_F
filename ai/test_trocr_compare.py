from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import cv2
import unicodedata
import os

# 결과 저장 폴더 생성
os.makedirs("results/trocr_compare", exist_ok=True)

# 사용할 Ko-TrOCR 모델
model_name = "ddobokki/ko-trocr"

processor = TrOCRProcessor.from_pretrained(model_name)
model = VisionEncoderDecoderModel.from_pretrained(model_name)

# 원본 번호판 이미지
image_path = "results/plates/plate_1.jpg"

# OpenCV로 이미지 읽기
image = cv2.imread(image_path)

print(f"원본 이미지 경로 : {image_path}")
print(f"원본 이미지 크기 : {image.shape}")


def run_trocr(image_path, label):
    """
    전달받은 이미지를 Ko-TrOCR에 넣고
    인식 결과 문자열을 반환하는 함수
    """

    image = Image.open(image_path).convert("RGB")

    pixel_values = processor(
        images=image,
        return_tensors="pt"
    ).pixel_values

    generated_ids = model.generate(pixel_values)

    text = processor.batch_decode(
        generated_ids,
        skip_special_tokens=True
    )[0]

    # 분리형 한글 자모를 완성형으로 정규화
    text = unicodedata.normalize("NFC", text)

    print(f"{label:<20} → {text}")

    return text


# -----------------------------------------
# 1. 원본 이미지
# -----------------------------------------

original_path = "results/trocr_compare/01_original.jpg"

cv2.imwrite(
    original_path,
    image
)


# -----------------------------------------
# 2. 4배 확대
# -----------------------------------------

upscaled = cv2.resize(
    image,
    None,
    fx=4,
    fy=4,
    interpolation=cv2.INTER_CUBIC
)

upscaled_path = "results/trocr_compare/02_upscaled.jpg"

cv2.imwrite(
    upscaled_path,
    upscaled
)


# -----------------------------------------
# 3. 4배 확대 + Grayscale
# -----------------------------------------

gray = cv2.cvtColor(
    upscaled,
    cv2.COLOR_BGR2GRAY
)

gray_path = "results/trocr_compare/03_gray.jpg"

cv2.imwrite(
    gray_path,
    gray
)


# -----------------------------------------
# 4. 4배 확대 + CLAHE
# -----------------------------------------

clahe = cv2.createCLAHE(
    clipLimit=2.0,
    tileGridSize=(8, 8)
)

clahe_image = clahe.apply(gray)

clahe_path = "results/trocr_compare/04_clahe.jpg"

cv2.imwrite(
    clahe_path,
    clahe_image
)


print("\n=== Ko-TrOCR 전처리 비교 ===")

result_original = run_trocr(
    original_path,
    "1. 원본"
)

result_upscaled = run_trocr(
    upscaled_path,
    "2. 4배 확대"
)

result_gray = run_trocr(
    gray_path,
    "3. 확대 + Gray"
)

result_clahe = run_trocr(
    clahe_path,
    "4. 확대 + CLAHE"
)

print("\n정답 : 10누1557")
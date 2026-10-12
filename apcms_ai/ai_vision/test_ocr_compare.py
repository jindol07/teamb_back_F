
from pathlib import Path
import re
import unicodedata

from PIL import Image
from paddleocr import PaddleOCR
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

# 1. 실제 정답 데이터
GROUND_TRUTH = {
    "car": "10누1557",
    "car2": "32부5178",
    "car3": "1146NMC",
    "car4": "97소3698",
    "car5": "10호8904",
}

# 2. 비교 대상 번호판 이미지
# car2의 모자이크 차량은 제외
PLATE_IMAGES = {
    "car": "results/pipeline/car/plate_2_1.jpg",
    "car2": "results/pipeline/car2/plate_2_1.jpg",
    "car3": "results/pipeline/car3/plate_1_1.jpg",
    "car4": "results/pipeline/car4/plate_1_1.jpg",
    "car5": "results/pipeline/car5/plate_1_1.jpg",
}

# 3. 결과 비교를 위한 문자열 정규화 (한글 Unicode를 정규화하고 공백을 제거하며 영문을 대문자로 통일)
def normalize_text(text):
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", "", text).upper()


# 4. PaddleOCR 모델 준비
paddle_ocr = PaddleOCR(
    lang="korean",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    enable_mkldnn=False,
)

# 5. Ko-TrOCR 모델 준비
model_name = "ddobokki/ko-trocr"

processor = TrOCRProcessor.from_pretrained(model_name)
trocr_model = VisionEncoderDecoderModel.from_pretrained(model_name)
trocr_model.eval()


# 6. 각각의 모델에 동일한 번호판 이미지를 전달하고 인식 문자열을 반환
def run_paddleocr(image_path):
    results = paddle_ocr.predict(str(image_path))

    texts = []

    for item in results:
        texts.extend(item["rec_texts"])

    return "".join(texts)


def run_trocr(image_path):
    image = Image.open(image_path).convert("RGB")

    pixel_values = processor(
        images=image,
        return_tensors="pt"
    ).pixel_values

    generated_ids = trocr_model.generate(pixel_values)

    text = processor.batch_decode(
        generated_ids,
        skip_special_tokens=True
    )[0]

    return text


# 7. 비교 실행
paddle_correct = 0
trocr_correct = 0
total = 0

print("\n=== OCR 성능 비교 ===")

for name, image_path in PLATE_IMAGES.items():
    path = Path(image_path)

    if not path.is_file():
        print(f"\n{name}: 이미지 파일 없음 - {path}")
        continue

    answer = GROUND_TRUTH[name]

    paddle_text = run_paddleocr(path)
    trocr_text = run_trocr(path)

    paddle_pass = (
        normalize_text(paddle_text) == normalize_text(answer)
    )

    trocr_pass = (
        normalize_text(trocr_text) == normalize_text(answer)
    )

    total += 1
    paddle_correct += int(paddle_pass)
    trocr_correct += int(trocr_pass)

    print(f"\n[{name}] 정답: {answer}")
    print(f"PaddleOCR: {paddle_text} / {'PASS' if paddle_pass else 'FAIL'}")
    print(f"Ko-TrOCR : {trocr_text} / {'PASS' if trocr_pass else 'FAIL'}")


# 7. 최종 정확도
print("\n=== 최종 비교 ===")

if total > 0:
    print(f"평가 이미지: {total}개")
    print(f"PaddleOCR: {paddle_correct}/{total} ({paddle_correct / total * 100:.1f}%)")
    print(f"Ko-TrOCR : {trocr_correct}/{total} ({trocr_correct / total * 100:.1f}%)")
else:
    print("평가할 이미지가 없습니다.")

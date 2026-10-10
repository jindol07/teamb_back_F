import unicodedata # 유니코드 문자 데이터베이스를 다루는 라이브러리
from PIL import Image # Image : 이미지 파일을 불러오고, 이미지 데이터를 다루는 라이브러리
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
# TrOCRProcessor : 입력 이미지를 TrOCR 모델이 읽을 수 있는 형식으로 바꿔주는 전처리 도구
# VisionEncoderDecoderModel : TrOCR 모델을 불러오는 클래스(실제 OCR 모델 본체)
# Vision Encoder -> 이미지 특징 분석
# (Text) Decoder -> 분석된 이미지 특징을 바탕으로 문자 생성

model_name = "ddobokki/ko-trocr" # 떡볶이(진짜임) 모델 : 한국어 TrOCR 모델

# 해당 모델에 맞는 전처리기와 디코딩 도구 불러오기
# 모델용 이미지 변환기 + 모델 출력 문자 복원기 준비
processor = TrOCRProcessor.from_pretrained(model_name)
# TrOCR 모델 불러오기
model = VisionEncoderDecoderModel.from_pretrained(model_name)

# 번호판 이미지 경로
image_path = "results/plates/plate_1.jpg"

image = Image.open(image_path).convert("RGB")

# 이미지를 모델에 넣을 수 있는 형태로 변환
pixel_values = processor(
    images=image,
    return_tensors="pt" # pt = PyTorch
    # PIL 이미지 -> TrOCRProcessor -> PyTorch Tensor
).pixel_values # pixel_values에는 단순 이미지 파일이 아니라 모델이 계산할 수 있도록 변환된 숫자 배열이 들어 있음

# 실제 OCR 모델 추론
generated_ids = model.generate(pixel_values)
# pixel_values -> Ko-TrOCR -> 문자 예측 -> 토큰 ID

# 모델이 만든 토큰 ID를 실제 문자열로 바꾸기 위해서 TrOCRProcessor의 batch_decode() 함수 사용
text = processor.batch_decode(
    generated_ids,
    skip_special_tokens=True # 모델 내부에서 사용하는 특수 토큰은 결과 문자열에서 제거하라는 뜻(문자열만 나오게)
)[0]

# 분리되어 있는 한글 자모를 완성형 한글로 정규화
text = unicodedata.normalize("NFC", text)

print("=== Ko-TrOCR 결과 ===")
print(f"인식 문자: {text}")
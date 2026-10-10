from paddleocr import PaddleOCR
import cv2, os

os.makedirs("results/ocr", exist_ok=True) # ocr 결과를 저장할 폴더 생성

# ocr 모델 생성
ocr = PaddleOCR(
    lang="korean", # 한국어 인식할 수 있는 OCR 모델 사용
    # 아래 세 옵션들은 불필요한 부가 기능들을 끄는 설정(일단은 테스트니까)
    use_doc_orientation_classify=False, # 이미지가 거꾸로 뒤집혔는지 등을 판단하는 기능
    use_doc_unwarping=False, # 휘거나 왜곡된 문서 이미지를 펴주는 기능
    use_textline_orientation=False, # 글자가 어느 방향으로 쓰여 있는지 판단하는 기능
    enable_mkldnn=False # 오류에 대한 우회책 (최적화 사용 X)
)

# OCR할 번호판 이미지
image_path = "results/plates/plate_1.jpg"

# 1. 이미지 읽기
image = cv2.imread(image_path)
print(f"이미지 읽기 완료 : {image_path}")
print(f"원본 크기 : {image.shape}") # (높이, 너비, 채널(BGR 컬러))
print(f"이미지 크기 : {image.shape[1]} x {image.shape[0]}")

#################################################전처리 시작#################################################

# 2. 번호판 이미지 4배 확대 - OCR 모델이 글자의 형태를 분석하기 더 좋은 크기로 만들어주기 위해서
upscaled = cv2.resize(
    image,
    None,
    fx=4,
    fy=4,
    interpolation=cv2.INTER_CUBIC # INTER_CUBIC : 작은 이미지를 확대할 때 사용할 수 있는 보간법 중 하나
)

# 3. OCR이 글자 인식할 때 색상 정보는 필요 없으므로 흑백으로 변환(색보다는 문자와 배경의 명암 차이가 더 중요한 경우가 많음)
gray = cv2.cvtColor(
    upscaled,
    cv2.COLOR_BGR2GRAY
)

# 4. 대비 강화 - 밝은 곳과 어두운 곳의 차이를 좀 더 크게 만들어서 글자 인식이 더 잘 되도록
gray = cv2.equalizeHist(gray)

# 5. 2~4의 전처리 결과 저장
processed_path = "results/ocr/plate_processed.jpg"

cv2.imwrite(
    processed_path,
    gray
)

#################################################전처리 끝#################################################

# 6. OCR 실행
result = ocr.predict(processed_path) # predict() : 이미지에서 글자를 인식하는 함수

# result : OCR 처리 과정 전체 정보를 담고 있는 리스트 
# 리스트 안에는 이미지 한 장에 대한 OCR 결과가 딕셔너리 형태로 들어 있고
# 딕셔너리 안에는 OCR에 넣은 원본 이미지 경로(input_path)(이 OCR 결과가 어떤 파일에서 나온 것인지 알려줌), 
# OCR이 실제로 읽은 문자 결과(rec_texts)(번호판 이미지에서 인식된 한 줄의 글자들), 
# 각 rec_texts에 대한 인식된 글자들의 신뢰도 점수(rec_scores) 등이 들어 있음
# rec_scores 는 OCR 모델이 자기 결과를 얼마나 확신하는지에 대한 신뢰도이기 때문에 실제 정답률과는 무관
# 그 외 것들은 PaddleOCR 공식 문서 참조

# 7. OCR 결과 확인
print("=== OCR 결과 ===")

for item in result:
    # item 하나가 이미지 한 장에 대한 OCR 결과 묶음
    texts = item["rec_texts"] # 인식된 문자들
    scores = item["rec_scores"] # 인식된 문자들의 신뢰도 점수

    for text, score in zip(texts, scores): # zip() : 두 개 이상의 리스트의 같은 위치에 있는 값을 묶어주는 Python 함수
        print(
            f"인식 문자: {text}, "
            f"신뢰도: {score:.4f}"
        )
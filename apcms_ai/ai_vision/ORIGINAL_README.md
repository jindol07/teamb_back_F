=== 통합 install ===
pip install -r requirements.txt

=== FastAPI 실행 시 ===
python -m uvicorn main:app --reload --port 8000

=====================================================================================================
[YOLO]

pip install ultralytics

ultralytics : YOLO를 Python에서 쉽게 사용할 수 있게 해주는 라이브러리

======== 내부적으로 같이 쓰이는 주요 패키지 목록 ========
ultralytics : YOLO 실행, 학습, 추론
torch : 딥러닝 모델 계산 담당
torchvision : 이미지 관련 딥러닝 기능
opencv-python : 이미지/영상 처리
numpy : 좌표, 배열, 수치 연산
Pillow : 이미지 파일 읽기/처리
matplotlib : 결과 시각화

Python 코드 -> Ultralytics -> PyTorch (ultralytics가 내부적으로 PyTorch를 사용) -> CPU 또는 GPU 연산

yolo11n.pt : 이미 학습되어 있는 YOLO 모델 파일

=====================================================================================================
[OCR]

1. PaddleOCR (이거 쓸듯)
pip install paddleocr paddlepaddle

PaddleOCR : 문자 인식 기능을 쉽게 사용하게 해주는 라이브러리, 내부적으로 PaddlePaddle을 사용함
PaddlePaddle : PaddleOCR 모델이 실제로 계산을 수행할 때 사용하는 딥러닝 엔진(프레임워크)

Python 코드 -> PaddleOCR -> PaddlePaddle (PaddleOCR이 내부적으로 PaddlePaddle을 사용) -> CPU / GPU

2. EasyOCR (안쓸듯)
pip install easyocr

EasyOCR : 설치와 구현이 간단한 ocr, 비교용(안해도됨)

3. Ko-TrOCR (비교용으로 사용할듯)
pip install transformers sentencepiece

transformers : Hugging Face에서 제공하는 라이브러리로 BERT, GPT 계열, ViT, TrOCR 같은 다양한 사전학습 AI 모델을 불러와서 사용할 수 있게 해주는 도구(여기서는 TrOCR 사용)
sentencepiece : 문자열을 AI 모델이 처리할 수 있는 토큰 단위로 나누거나 다시 합치는 데 사용하는 라이브러리

Python 코드 -> transformers -> Ko-TrOCR 모델 -> PyTorch -> CPU / GPU

=====================================================================================================

[FastAPI]

python -m pip install fastapi uvicorn python-multipart

fastapi -> Python API 서버를 만드는 프레임워크
uvicorn -> FastAPI 애플리케이션을 실제로 실행하는 서버
python-multipart ->브라우저나 Spring Boot가 이미지 파일을 multipart/form-data 방식으로 업로드할 때 필요

테스트 해본 결과
{
    "success": true,
    "message": "차량 인식 처리가 완료되었습니다.",
    "vehicle_fallback_used": false,
    "vehicle_count": 1,
    "vehicles": [
        {
            "vehicle_index": 1,
            "vehicle_type": "car",
            "vehicle_confidence": 0.6485,
            "vehicle_box": {
                "x1": 10,
                "y1": 26,
                "x2": 1411,
                "y2": 1074
            },
            "plate_detected": true,
            "plate_confidence": 0.9736,
            "plate_number": "91소6408",
            "plate_type": "KOREAN_VALID",
            "first_ocr": "91소6408O©",
            "first_type": "REVIEW",
            "retry_ocr": "91소6408",
            "retry_type": "KOREAN_VALID"
        }
    ]
}

success: 전체 AI 인식 처리 정상 수행 여부 (true일 경우 요청 정상 처리)

message: AI 인식 처리 결과 설명 메시지 (예: "차량 인식 처리가 완료되었습니다.")

vehicle_fallback_used: 기본 차량 탐지 기준 미달 시 더 낮은 신뢰도 기준으로 재탐지했는지 여부 
(false일 경우 기본 기준에서 정상 탐지)

vehicle_count: 최종 탐지된 차량 개수

vehicles: 탐지된 차량별 결과를 담는 배열 (여러 대 탐지 시 객체 다수 포함)

    vehicle_index: 탐지된 차량 순번 (1: 첫 번째 차량)

    vehicle_type: YOLO 모델이 판단한 차량 종류 (car, truck, bus, motorcycle 등)
        얘는 현재 참고용 값임. 핵심은 plate_detected, plate_number, plate_type

    vehicle_confidence: 차량 탐지 신뢰도 (예: 0.6485 → 약 64.85%)

    vehicle_box: 원본 이미지 내 차량 사각형 영역 좌표

        vehicle_box.x1: 차량 영역 좌상단 X 좌표

        vehicle_box.y1: 차량 영역 좌상단 Y 좌표

        vehicle_box.x2: 차량 영역 우하단 X 좌표

        vehicle_box.y2: 차량 영역 우하단 Y 좌표

    plate_detected: 차량 영역 내 번호판 탐지 성공 여부

    plate_confidence: 번호판 탐지 모델 신뢰도 (예: 0.9736 → 약 97.36%)

    plate_number: 최종 확정된 번호판 문자열

    plate_type: 최종 번호판 문자열 형식 판정 결과

        아래는 plate_type 종류들
        KOREAN_VALID : 정상적인 국내 번호판 형식으로 판단
        FOREIGN_OR_OTHER : 영문/숫자 조합 등 국내 번호판 형식이 아닌 형태
        REVIEW : OCR 결과가 번호판 형식에 맞지 않아 재확인이 필요한 상태
        OCR_FAILED : OCR 자체가 실패한 상태

    first_ocr: 1차 OCR 인식 문자열 (노이즈/불필요 문자 포함 가능)

    first_type: 1차 OCR 결과 형식 판정 결과

    retry_ocr: 이미지 보정 후 수행한 2차 OCR 결과 문자열

    retry_type: 2차 OCR 결과 형식 판정 결과

Q : 1차랑 2차는 뭐냐? 왜 또하냐?
A : 1차 OCR 결과가 REVIEW / OCR_FAILED일 경우 번호판 이미지를 다시 전처리(확대·그레이스케일·CLAHE 보정)한 뒤 
2차 OCR을 수행하고 더 나은 결과를 최종 번호판으로 사용
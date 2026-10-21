# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/recognition_models.py

"""이미지 인식 모델을 필요한 역할별로 처음 사용할 때 한 번 생성합니다."""

# 1. 모델 캐시 관리에 필요한 도구 가져오기
# 1-1. threading.RLock: 여러 요청이 동시에 모델을 불러올 때 중복 생성을 막습니다.
# 1-2. Path: 모델 파일 경로를 운영체제에 맞게 조립합니다.
import threading
from contextlib import contextmanager
from pathlib import Path

# 1-3. MODEL_DIR은 차량·번호판 탐지 모델 파일이 보관된 프로젝트 기준 폴더입니다.
from ai_vision.paths import MODEL_DIR
from ai_vision.recognition.model_files import require_model_file
from ai_vision.recognition.ocr_configuration import local_ocr_options


# 2. 차량 탐지, 번호판 탐지, 문자 인식(OCR) 모델의 지연 로딩 관리자
# 지연 로딩이란 프로그램 시작 시 모두 로드하지 않고 처음 요청한 모델만 생성하는 방식입니다.
class RecognitionModels:
    # 2-1. 모델 위치와 테스트용 생성 함수를 받아 내부 저장소를 초기화합니다.
    # 함수 설명: __init__() — 모델 폴더, 테스트용 생성 함수 및 동기화 락을 준비합니다.
    def __init__(self, model_dir=MODEL_DIR, yolo_factory=None, ocr_factory=None):
        self.model_dir = Path(model_dir)
        # factory가 지정되지 않으면 실제 YOLO/PaddleOCR 생성자를 나중에 import합니다.
        self._yolo_factory, self._ocr_factory = yolo_factory, ocr_factory
        # 역할별로 생성된 객체를 저장하며 RLock으로 동시 접근을 보호합니다.
        self._models, self._lock = {}, threading.RLock()
        self._inference_locks = {role: threading.RLock() for role in ("vehicle", "plate", "ocr")}

    # 3. 요청된 역할에 맞는 모델을 생성하거나 기존 객체를 재사용합니다.
    # 3-1. _get(role)의 role은 vehicle, plate, ocr 중 하나입니다(외부 공개 메서드가 선택).
    # 함수 설명: _get() — 역할별 모델을 처음 요청할 때에만 만들고 이후 캐시에서 꺼냅니다.
    def _get(self, role):
        # 동시에 첫 요청이 들어와도 같은 역할의 모델을 중복 생성하지 않습니다.
        with self._lock:
            # 이미 만들어 둔 모델이 있으면 생성 과정을 건너뜁니다.
            if role not in self._models:
                # 3-2. 문자 인식 역할(ocr)은 PaddleOCR을 생성합니다.
                if role == "ocr":
                    options = local_ocr_options(self.model_dir)
                    factory = self._ocr_factory
                    if factory is None:
                        # 실제로 OCR이 필요할 때에만 라이브러리를 import합니다.
                        from paddleocr import PaddleOCR
                        factory = PaddleOCR
                    # 한국어 인식 모델을 사용하고 문서 회전·왜곡 등의 별도 기능은 비활성화합니다.
                    language_options = options if options else {"lang": "korean"}
                    model = factory(use_doc_orientation_classify=False,
                                    use_doc_unwarping=False, use_textline_orientation=False, enable_mkldnn=False, **language_options)
                else:
                    # 3-3. 차량 탐지는 yolo11n.pt, 번호판 탐지는 license_plate_yolov8n.pt를 사용합니다.
                    filename = "yolo11n.pt" if role == "vehicle" else "license_plate_yolov8n.pt"
                    path = self.model_dir / filename
                    require_model_file(path)
                    factory = self._yolo_factory
                    if factory is None:
                        # 실제 차량/번호판 탐지가 필요할 때에만 YOLO 라이브러리를 import합니다.
                        from ultralytics import YOLO
                        factory = YOLO
                    model = factory(path)
                # 3-4. 생성에 성공했을 때만 캐시에 기록합니다.
                # 모델 파일 누락이나 초기화 오류 시 실패 객체를 저장하지 않아 재시도가 가능합니다.
                self._models[role] = model
            # 역할별로 같은 모델 객체를 반환하여 반복 로딩 비용을 줄입니다.
            return self._models[role]

    # 4. 다른 코드에서 사용하는 역할별 공개 메서드
    # 4-1. vehicle(): 차량 위치와 종류를 탐지할 YOLO 모델을 반환합니다.
    # 함수 설명: vehicle() — 차량 탐지용 YOLO 모델 객체를 반환합니다.
    def vehicle(self):
        return self._get("vehicle")

    # 4-2. plate(): 차량 이미지에서 번호판 영역을 찾을 YOLO 모델을 반환합니다.
    # 함수 설명: plate() — 번호판 탐지용 YOLO 모델 객체를 반환합니다.
    def plate(self):
        return self._get("plate")

    # 4-3. ocr(): 번호판의 문자를 읽는 PaddleOCR 모델을 반환합니다.
    # 함수 설명: ocr() — 한국어 문자 인식용 PaddleOCR 객체를 반환합니다.
    def ocr(self):
        return self._get("ocr")

    @contextmanager
    def inference_lock(self, role):
        # 5. 모델 생성과 추론 잠금을 분리하고 같은 모델의 추론만 순서대로 실행합니다.
        if role not in self._inference_locks:
            raise ValueError("지원하지 않는 인식 모델 역할입니다.")
        with self._inference_locks[role]:
            # 잠금만 요청해도 모델이 로딩되지는 않습니다.
            yield

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/recognition_models.py

"""이미지 인식 모델을 필요한 역할별로 처음 사용할 때 한 번 생성합니다."""

import threading
from pathlib import Path

from ai_vision.paths import MODEL_DIR


class RecognitionModels:
    def __init__(self, model_dir=MODEL_DIR, yolo_factory=None, ocr_factory=None):
        self.model_dir = Path(model_dir)
        self._yolo_factory, self._ocr_factory = yolo_factory, ocr_factory
        self._models, self._lock = {}, threading.RLock()

    def _get(self, role):
        # 1. 동시에 첫 요청이 들어와도 같은 역할의 모델을 중복 생성하지 않습니다.
        with self._lock:
            if role not in self._models:
                if role == "ocr":
                    factory = self._ocr_factory
                    if factory is None:
                        from paddleocr import PaddleOCR
                        factory = PaddleOCR
                    model = factory(lang="korean", use_doc_orientation_classify=False,
                                    use_doc_unwarping=False, use_textline_orientation=False, enable_mkldnn=False)
                else:
                    filename = "yolo11n.pt" if role == "vehicle" else "license_plate_yolov8n.pt"
                    path = self.model_dir / filename
                    if not path.is_file():
                        raise FileNotFoundError(f"인식 모델이 없습니다: {filename}")
                    factory = self._yolo_factory
                    if factory is None:
                        from ultralytics import YOLO
                        factory = YOLO
                    model = factory(path)
                # 2. 생성이 끝난 객체만 보관합니다. 실패한 생성 결과는 캐시하지 않습니다.
                self._models[role] = model
            return self._models[role]

    def vehicle(self):
        return self._get("vehicle")

    def plate(self):
        return self._get("plate")

    def ocr(self):
        return self._get("ocr")

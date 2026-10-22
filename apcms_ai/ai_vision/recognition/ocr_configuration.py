# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/ocr_configuration.py

"""PaddleOCR의 선택적인 로컬 추론 모델 경로를 검사합니다."""

import os
import re
from pathlib import Path
from ai_vision.paths import MODEL_DIR
from ai_vision.recognition.model_files import require_model_file


class OCRConfigurationError(ValueError):
    pass


def local_ocr_options(model_dir=MODEL_DIR):
    detection = os.environ.get("VISION_OCR_DETECTION_MODEL_DIR")
    recognition = os.environ.get("VISION_OCR_RECOGNITION_MODEL_DIR")
    if detection is None and recognition is None:
        return {}
    # 1. 한쪽만 지정해 나머지가 뜻하지 않게 다운로드되는 설정은 거부합니다.
    if not detection or not recognition or not detection.strip() or not recognition.strip():
        raise OCRConfigurationError("로컬 OCR 탐지·인식 모델 폴더를 함께 지정해 주세요.")
    options = {}
    for key, raw in (("text_detection_model_dir", detection), ("text_recognition_model_dir", recognition)):
        folder = Path(raw).expanduser()
        folder = (folder if folder.is_absolute() else Path(model_dir) / folder).resolve()
        # 2. PaddleOCR 3.x 추론용 파일을 확인합니다. 학습 체크포인트 폴더와 구분합니다.
        try:
            require_model_file(folder / "inference.yml")
            require_model_file(folder / "inference.pdiparams")
            structure = folder / "inference.json"
            require_model_file(structure if structure.is_file() else folder / "inference.pdmodel")
        except OSError as error:
            raise OCRConfigurationError("로컬 OCR 추론 모델 파일·읽기 권한을 확인해 주세요.") from error
        # 3. 경로만 넘기면 라이브러리 기본 모델 이름과 충돌하므로 모델 설정의 이름도 전달합니다.
        try:
            import yaml
            with (folder / "inference.yml").open("rb") as stream:
                content = stream.read(1024 * 1024 + 1)
            if len(content) > 1024 * 1024:
                raise ValueError("OCR 설정 파일 크기 초과")
            config = yaml.safe_load(content)
            global_options = config.get("Global") if isinstance(config, dict) else None
            name = global_options.get("model_name") if isinstance(global_options, dict) else None
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", name):
                raise ValueError("OCR 모델 이름이 없습니다.")
        except ImportError as error:
            raise OCRConfigurationError("로컬 OCR 모델 설정을 읽으려면 PyYAML이 필요합니다.") from error
        except (OSError, ValueError, RecursionError, yaml.YAMLError) as error:
            raise OCRConfigurationError("OCR inference.yml의 Global.model_name을 확인해 주세요.") from error
        options[key] = str(folder)
        options[key.replace("_dir", "_name")] = name
    return options

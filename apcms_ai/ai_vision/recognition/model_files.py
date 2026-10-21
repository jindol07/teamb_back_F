# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/model_files.py

"""모델 로딩 전에 파일 존재·읽기 가능 여부만 검사합니다."""

from pathlib import Path


def require_model_file(path):
    path = Path(path)
    # 1. 파일이 없을 때 라이브러리가 자동 다운로드로 넘어가지 않게 먼저 거부합니다.
    if not path.is_file():
        raise FileNotFoundError("인식 모델 파일이 없습니다.")
    with path.open("rb") as handle:
        if not handle.read(1):
            raise FileNotFoundError("인식 모델 파일이 비어 있습니다.")
    # 실제 모델 무결성은 로더·추론으로 별도 확인합니다.
    return path

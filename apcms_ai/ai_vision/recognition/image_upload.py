# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/image_upload.py

"""업로드 이미지의 압축 크기와 픽셀 수를 확인한 뒤 BGR 이미지로 해석합니다."""

import io

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000


class ImageUploadError(ValueError):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


def decode_uploaded_image(data):
    # 1. 압축된 파일 크기를 먼저 제한합니다. 원본 파일이나 임시 이미지는 저장하지 않습니다.
    if not isinstance(data, bytes) or not data:
        raise ImageUploadError(400, "빈 이미지 파일입니다.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageUploadError(413, "이미지 파일은 최대 10MB까지 업로드할 수 있습니다.")
    try:
        # 2. 픽셀 배열을 생성하기 전에 헤더의 가로·세로 크기를 확인합니다.
        with Image.open(io.BytesIO(data)) as header:
            width, height = header.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ImageUploadError(413, "이미지는 최대 2천만 픽셀까지 처리할 수 있습니다.")
    except ImageUploadError:
        raise
    except Image.DecompressionBombError as error:
        raise ImageUploadError(413, "이미지 해상도가 처리 한도를 넘었습니다.") from error
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as error:
        raise ImageUploadError(400, "이미지를 읽을 수 없습니다.") from error
    try:
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error as error:
        raise ImageUploadError(400, "이미지를 읽을 수 없습니다.") from error
    # 3. 실제 디코딩 결과도 재확인하고 모델에 넘깁니다.
    if image is None or image.ndim != 3 or image.shape[2] != 3 or not image.size:
        raise ImageUploadError(400, "이미지를 읽을 수 없습니다.")
    if image.shape[0] * image.shape[1] > MAX_IMAGE_PIXELS:
        raise ImageUploadError(413, "이미지는 최대 2천만 픽셀까지 처리할 수 있습니다.")
    return image


def process_uploaded_image(data, inference):
    # 디코딩된 배열이 작업 스레드 안에 머물도록 추론까지 한 작업으로 연결합니다.
    return inference(decode_uploaded_image(data))

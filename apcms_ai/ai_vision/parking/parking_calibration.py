# D:/finalProjectB/back/apcms_ai/ai_vision/parking/parking_calibration.py
"""기준 사진과 카메라 해상도를 같은 규칙으로 검사합니다."""

import io
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from ai_vision.parking.parking_validation import validate_spaces

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 16 * 1024 * 1024
MAX_MASK_BYTES = 64 * 1024 * 1024


def validate_resolution(width, height):
    if type(width) is not int or type(height) is not int or not 1 <= width <= 8192 or not 1 <= height <= 8192 or width * height > MAX_IMAGE_PIXELS:
        raise ValueError('카메라 해상도가 허용 범위를 벗어났습니다.')


def load_reference(path, config=None):
    # 1. 압축 파일의 크기와 실제 해상도를 확인한 뒤 픽셀 배열을 만듭니다.
    if config is not None:
        validate_spaces(config)
        validate_resolution(config['image_width'], config['image_height'])
        if config['image_width'] * config['image_height'] * len(config['spaces']) > MAX_MASK_BYTES:
            raise ValueError('주차면 마스크 메모리 한도를 초과했습니다.')
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_IMAGE_BYTES + 1)
    if not 0 < len(raw) <= MAX_IMAGE_BYTES:
        raise ValueError('기준 사진은 0바이트 초과 10MiB 이하여야 합니다.')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            validate_resolution(*image.size)
            if image.format not in ('JPEG', 'PNG'):
                raise ValueError('기준 사진은 JPEG 또는 PNG로 지정하세요.')
            if config is not None and image.size != (config['image_width'], config['image_height']):
                raise ValueError('기준 사진과 좌표의 해상도가 다릅니다.')
            image.verify()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise ValueError('기준 사진이 손상되었거나 지원하지 않는 형식입니다.') from error
    # EXIF 회전을 자동 적용하면 좌표가 바뀌므로 저장된 픽셀 방향을 유지합니다.
    frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if frame is None:
        raise ValueError('기준 사진을 해독할 수 없습니다.')
    return frame


def configure_resolution(capture, width, height):
    # 2. 드라이버의 성공 응답만 믿지 않고 이후 실제 프레임 크기도 검사합니다.
    validate_resolution(width, height)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)


def validate_frame_resolution(frame, width, height):
    if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.shape != (height, width, 3):
        raise ValueError(f'카메라가 요청한 {width} x {height} 해상도를 제공하지 않습니다. 지원 해상도로 다시 촬영하세요.')

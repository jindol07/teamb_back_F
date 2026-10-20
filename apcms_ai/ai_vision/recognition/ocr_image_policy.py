# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/ocr_image_policy.py

"""OCR 재시도 이미지의 확대율·변 길이·총 픽셀 수를 제한합니다."""

import math


RETRY_MAX_SCALE = 4
RETRY_MAX_SIDE = 4096
RETRY_MAX_PIXELS = 4_000_000


def retry_image_size(width, height):
    if type(width) is not int or type(height) is not int or width < 1 or height < 1:
        raise ValueError("OCR 이미지의 가로·세로 크기가 올바르지 않습니다.")
    # 1. 일반적인 작은 번호판은 기존 4배 확대를 유지합니다.
    target_width, target_height = width * RETRY_MAX_SCALE, height * RETRY_MAX_SCALE
    longest = max(target_width, target_height)
    if longest > RETRY_MAX_SIDE:
        # 정수 비율 계산으로 큰 입력도 먼저 안전한 변 길이 안으로 맞춥니다.
        target_width = max(1, target_width * RETRY_MAX_SIDE // longest)
        target_height = max(1, target_height * RETRY_MAX_SIDE // longest)
    # 2. 가로·세로 비율을 유지하되 총 픽셀 수도 제한합니다.
    if target_width * target_height > RETRY_MAX_PIXELS:
        ratio = math.sqrt(RETRY_MAX_PIXELS / (target_width * target_height))
        target_width = max(1, int(target_width * ratio))
        target_height = max(1, int(target_height * ratio))
    return target_width, target_height

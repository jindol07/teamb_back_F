# D:/finalProjectB/back/apcms_ai/ai_vision/upload_policy.py
"""서버·점검 도구가 함께 사용하는 업로드 용량 정책."""

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
# 파일 용량 외에 multipart 경계·헤더를 위한 여유를 둡니다.
MAX_MULTIPART_BYTES = MAX_UPLOAD_BYTES + 1024 * 1024

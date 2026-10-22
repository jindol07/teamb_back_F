# D:/finalProjectB/back/apcms_ai/ai_vision/deployment_config.py

"""배포 환경변수를 검사합니다. 모델·네트워크를 초기화하지 않습니다."""

import json
import os
from urllib.parse import urlsplit


def cors_origins():
    raw = os.environ.get("VISION_CORS_ORIGINS", "[]")
    # 1. 쉼표 구분 대신 JSON 목록을 사용해 주소 형식을 명확히 합니다.
    try:
        origins = json.loads(raw)
    except (ValueError, TypeError) as error:
        raise ValueError("VISION_CORS_ORIGINS에는 HTTP(S) origin의 JSON 목록이 필요합니다.") from error
    if not isinstance(origins, list) or len(origins) > 16:
        raise ValueError("CORS origin은 최대 16개의 목록으로 지정합니다.")
    normalized = []
    for origin in origins:
        if not isinstance(origin, str) or len(origin) > 2048 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in origin):
            raise ValueError("CORS origin 형식을 확인해 주세요.")
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path or
                parsed.query or parsed.fragment or parsed.username is not None or parsed.password is not None):
            raise ValueError("CORS에는 경로·인증정보 없는 HTTP(S) origin만 지정합니다.")
        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError("CORS origin 포트를 확인해 주세요.") from error
        # 브라우저가 보내는 origin처럼 호스트 대소문자·기본 포트를 정규화합니다.
        host = parsed.hostname.encode("idna").decode("ascii").lower()
        host = f"[{host}]" if ":" in host else host
        suffix = "" if port is None or (parsed.scheme, port) in (("http", 80), ("https", 443)) else f":{port}"
        normalized.append(f"{parsed.scheme}://{host}{suffix}")
    return list(dict.fromkeys(normalized))

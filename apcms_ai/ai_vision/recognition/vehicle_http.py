# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_http.py

"""기본 비활성인 단발성 차량 입출차 HTTP 클라이언트."""

import math
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter

from ai_vision.recognition.vehicle_contract import AUTH_HEADER, VEHICLE_ENDPOINT, validate_vehicle_payload
from ai_vision.recognition.vehicle_response import assess_response


class VehicleHTTPClient:
    def __init__(self, context_url=None, api_key=None, enabled=False, timeout=(3, 5), session_factory=None):
        if type(enabled) is not bool:
            raise ValueError("enabled는 명시적인 bool이어야 합니다.")
        if (not isinstance(timeout, (tuple, list)) or len(timeout) != 2 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v <= 60 or not math.isfinite(v) for v in timeout)):
            raise ValueError("연결·읽기 제한 시간은 0초 초과 60초 이하로 지정합니다.")
        if context_url is not None:
            if not isinstance(context_url, str):
                raise ValueError("관리자 서버 context URL을 확인해 주세요.")
            parsed = urlsplit(context_url)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or
                    parsed.password is not None or parsed.query or parsed.fragment or any(char.isspace() for char in context_url)):
                raise ValueError("인증정보·query·fragment 없는 HTTP(S) context URL이 필요합니다.")
            try:
                parsed.port
            except ValueError as error:
                raise ValueError("관리자 서버 포트를 확인해 주세요.") from error
        if enabled and (context_url is None or not isinstance(api_key, str) or not api_key or
                        any(not 33 <= ord(char) <= 126 for char in api_key)):
            raise ValueError("활성화에는 서버 context URL과 유효한 API 키가 필요합니다.")
        self._enabled = enabled
        self._url = context_url.rstrip("/") + VEHICLE_ENDPOINT if context_url is not None else None
        self._api_key = api_key
        self._timeout = tuple(timeout)
        self._session_factory = requests.Session if session_factory is None else session_factory

    @property
    def enabled(self):
        return self._enabled

    def send(self, payload):
        event = validate_vehicle_payload(payload)
        base = {"event_id": event["event_id"], "event_type": "VEHICLE_PASSAGE", "http_status": None,
                "automatic_retry_allowed": False, "receipt_verified": False, "request_attempted": False}
        if not self.enabled:
            # 1. 세션 생성·환경변수 로드·네트워크 접근 전에 반환합니다.
            return {**base, "state": "DISABLED", "reason_code": "HTTP_DISABLED"}
        session, response, attempted = None, None, False
        try:
            session = self._session_factory()
            session.trust_env = False
            # 2. 요청 라이브러리의 숨은 재시도·리다이렉트도 차단합니다.
            session.mount("http://", HTTPAdapter(max_retries=0))
            session.mount("https://", HTTPAdapter(max_retries=0))
            attempted = True
            response = session.post(self._url, json=event, headers={AUTH_HEADER: self._api_key},
                                    timeout=self._timeout, allow_redirects=False, stream=True)
            raw = bytearray()
            if response.status_code == 200:
                for chunk in response.iter_content(chunk_size=8192):
                    if not isinstance(chunk, bytes):
                        raise ValueError("HTTP 응답 바이트 형식 오류")
                    if len(raw) + len(chunk) > 65536:
                        raw = bytearray(b" " * 65537)
                        break
                    raw.extend(chunk)
            result = assess_response(event, response.status_code, bytes(raw))
        except requests.Timeout:
            result = assess_response(event, transport_error="TIMEOUT")
        except requests.RequestException:
            result = assess_response(event, transport_error="CONNECTION_ERROR")
        except Exception:
            # 예외·URL·키를 응답에 복사하지 않고 처리 여부 불명으로 남깁니다.
            result = {**base, "state": "DELIVERY_UNKNOWN", "reason_code": "LOCAL_HTTP_PROCESSING_FAILED"}
        finally:
            for resource in (response, session):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:
                        pass
        return {**result, "request_attempted": attempted}

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_http.py

"""기본 비활성인 단발성 차량 입출차 HTTP 클라이언트."""

# 1. URL·시간 제한과 HTTP 호출에 필요한 모듈
import math
# 1-1. urlsplit은 접속 주소의 프로토콜·호스트·인증정보 등을 분리합니다.
from urllib.parse import urlsplit

# 1-2. requests는 HTTP POST 요청과 연결/시간초과 예외를 처리합니다.
import requests
# 1-3. HTTPAdapter에서 라이브러리 수준의 자동 재시도를 끕니다.
from requests.adapters import HTTPAdapter

# 1-4. 백엔드 약속된 요청 경로와 payload 검증기를 사용합니다.
from ai_vision.recognition.vehicle_contract import (AUTH_HEADER, VEHICLE_ENDPOINT, SPACE_MATCH_ENDPOINT,
                                                   validate_vehicle_payload, validate_space_match_payload)
# 1-5. HTTP 응답을 업무 처리 상태로 변환하는 함수입니다.
from ai_vision.recognition.vehicle_response import assess_response, assess_space_match_response


# 2. 기본 비활성 상태로 생성되는 차량 입출차 HTTP 클라이언트
class VehicleHTTPClient:
    _endpoint = VEHICLE_ENDPOINT
    _validate = staticmethod(validate_vehicle_payload)
    _assess = staticmethod(assess_response)
# 2-1. 서버 주소, API 키, 사용 여부, 연결·읽기 타임아웃을 설정합니다.
    # 함수 설명: __init__() — 서버 URL·API 키·타임아웃·사용 여부를 검사하여 HTTP 클라이언트를 설정합니다.
    def __init__(self, context_url=None, api_key=None, enabled=False, timeout=(3, 5), session_factory=None):
# 2-2. bool이 아닌 활성화 값을 허용하지 않아 오작동을 방지합니다.
        if type(enabled) is not bool:
            raise ValueError("enabled는 명시적인 bool이어야 합니다.")
        if (not isinstance(timeout, (tuple, list)) or len(timeout) != 2 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v <= 60 or not math.isfinite(v) for v in timeout)):
            raise ValueError("연결·읽기 제한 시간은 0초 초과 60초 이하로 지정합니다.")
# 2-3. URL에 사용자명·비밀번호·query·fragment가 포함된 경우 거부합니다.
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
# 2-4. 활성화를 명시한 경우에만 유효한 서버 주소와 API 키를 필수로 합니다.
        if enabled and (context_url is None or not isinstance(api_key, str) or not api_key or
                        any(not 33 <= ord(char) <= 126 for char in api_key)):
            raise ValueError("활성화에는 서버 context URL과 유효한 API 키가 필요합니다.")
# 2-5. 전송 설정을 인스턴스에 저장하며 기본 상태는 비활성입니다.
        self._enabled = enabled
        self._url = context_url.rstrip("/") + self._endpoint if context_url is not None else None
        self._api_key = api_key
        self._timeout = tuple(timeout)
        self._session_factory = requests.Session if session_factory is None else session_factory

# 3. 전송 가능 여부를 읽기 전용 속성으로 제공합니다.
    @property
    # 함수 설명: enabled() — 현재 명시적으로 HTTP가 활성화되었는지 읽기 전용으로 제공합니다.
    def enabled(self):
        return self._enabled

# 4. 요청 한 건을 검증하고 필요할 때만 HTTP POST를 수행합니다.
    # 함수 설명: send() — 중복 재시도 없이 한 번 요청하고 통신 결과를 정규화하여 반환합니다.
    def send(self, payload):
# 4-1. 네트워크 접근 전에 요청 형식부터 검증합니다.
        event = self._validate(payload)
        base = {"event_id": event["event_id"], "event_type": event['event_type'], "http_status": None,
                "automatic_retry_allowed": False, "receipt_verified": False, "request_attempted": False}
        if not self.enabled:
            # 1. 세션 생성·환경변수 로드·네트워크 접근 전에 반환합니다.
            return {**base, "state": "DISABLED", "reason_code": "HTTP_DISABLED"}
# 4-2. 자원 정리와 실제 요청 시도 여부를 위해 초기 상태를 저장합니다.
        session, response, attempted = None, None, False
        try:
# 4-3. 프록시 환경 상속을 끄고 명시한 서버만 대상으로 사용합니다.
            session = self._session_factory()
            session.trust_env = False
            # 2. 요청 라이브러리의 숨은 재시도·리다이렉트도 차단합니다.
            session.mount("http://", HTTPAdapter(max_retries=0))
            session.mount("https://", HTTPAdapter(max_retries=0))
# 4-4. POST 호출을 시작한 뒤부터 요청 시도 사실을 기록합니다.
            attempted = True
            response = session.post(self._url, json=event, headers={AUTH_HEADER: self._api_key},
                                    timeout=self._timeout, allow_redirects=False, stream=True)
# 4-5. 정상 응답 본문은 최대 64KiB까지만 메모리에 수집합니다.
            raw = bytearray()
            if response.status_code == 200:
                for chunk in response.iter_content(chunk_size=8192):
                    if not isinstance(chunk, bytes):
                        raise ValueError("HTTP 응답 바이트 형식 오류")
                    if len(raw) + len(chunk) > 65536:
                        raw = bytearray(b" " * 65537)
                        break
                    raw.extend(chunk)
# 4-6. 상태 코드와 본문을 업무 결과로 분류합니다.
            result = self._assess(event, response.status_code, bytes(raw))
# 5. 네트워크 오류는 서버 처리 불명으로 기록합니다.
# 5-1. 타임아웃만으로 재전송하면 중복 입출차가 생길 수 있어 자동 재시도하지 않습니다.
        except requests.Timeout:
            result = self._assess(event, transport_error="TIMEOUT")
        except requests.RequestException:
            result = self._assess(event, transport_error="CONNECTION_ERROR")
        except Exception:
            # 예외·URL·키를 응답에 복사하지 않고 처리 여부 불명으로 남깁니다.
            result = {**base, "state": "DELIVERY_UNKNOWN", "reason_code": "LOCAL_HTTP_PROCESSING_FAILED"}
# 6. 성공·실패에 관계없이 응답·세션 자원을 닫습니다.
        finally:
            for resource in (response, session):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:
                        pass
# 7. 결과와 실제 네트워크 시도 여부를 반환합니다.
        return {**result, "request_attempted": attempted}


class SpaceMatchHTTPClient(VehicleHTTPClient):
    """기존 Boot 구획 연결 계약용 단발성 클라이언트. 기본 비활성입니다."""
    _endpoint = SPACE_MATCH_ENDPOINT
    _validate = staticmethod(validate_space_match_payload)
    _assess = staticmethod(assess_space_match_response)


from ai_vision.recognition.vehicle_contract import SPACE_RELEASE_ENDPOINT, validate_space_release_payload
from ai_vision.recognition.vehicle_response import assess_space_release_response


class SpaceReleaseHTTPClient(VehicleHTTPClient):
    """버전으로 보호된 구획 해제 전용 클라이언트. 기본 비활성입니다."""
    _endpoint = SPACE_RELEASE_ENDPOINT
    _validate = staticmethod(validate_space_release_payload)
    _assess = staticmethod(assess_space_release_response)

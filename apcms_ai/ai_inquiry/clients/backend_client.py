"""인증 토큰을 Spring Boot에 전달. 임의 user_id를 사용해 DB를 조회하지 않는다."""

import httpx
import re
from ai_inquiry.config import settings


class BackendError(Exception):
    pass


class BackendClient:
    PATH = {
        "RESERVATION": "reservation_path",
        "USAGE": "usage_path",
        "VEHICLE": "vehicle_path",
        "MILEAGE": "mileage_path",
        "FEE": "fee_path",
    }

    def __init__(self):
        self.cfg = settings()

    async def request(self, method, path, token, *, payload=None):
        if not token:
            raise PermissionError("로그인이 필요합니다.")
        try:
            async with httpx.AsyncClient(
                base_url=self.cfg["base_url"], timeout=15
            ) as c:
                r = await c.request(
                    method,
                    path.lstrip('/'),
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                )
                if r.status_code in (401, 403):
                    # 토큰·응답 원문 없이 실제 실패한 API 단계만 알려줍니다.
                    reason = ''
                    try:
                        diagnosis = r.json()
                        if isinstance(diagnosis, dict) and diagnosis.get('code') == 'CHATBOT_IDENTITY_CHECK':
                            allowed = {
                                '로그인이 필요합니다.', '인증된 사용자 객체가 Office 타입이 아닙니다.',
                                '인증된 Office에 사용자 ID가 없습니다.', '인증된 계정에 OFFICE 권한이 없습니다.',
                            }
                            if diagnosis.get('detail') in allowed:
                                reason = ' ' + diagnosis['detail']
                    except ValueError:
                        pass
                    raise PermissionError(
                        f"사용자 서버 인증 거부: HTTP {r.status_code}, {method} {r.request.url.path}.{reason} "
                        "사용자 계정 로그인 및 실행 중인 서버의 API 반영 여부를 확인해 주세요."
                    )
                r.raise_for_status()
                return r.json() if r.content else {}
        except httpx.HTTPStatusError as e:
            raise BackendError(
                f"사용자 서버 응답 오류: HTTP {e.response.status_code}, {method} {e.request.url.path}"
            ) from e
        except httpx.TimeoutException as e:
            raise BackendError(f"사용자 서버 응답 시간 초과: {method} {path}") from e
        except httpx.RequestError as e:
            raise BackendError(f"사용자 서버 연결 실패: {method} {path}. 서버 실행 상태와 주소를 확인해 주세요.") from e
        except ValueError as e:
            raise BackendError(f"사용자 서버가 올바른 JSON을 반환하지 않았습니다: {method} {path}") from e

    async def authenticate(self, token):
        data = await self.request("GET", self.cfg["auth_path"], token)
        if not isinstance(data, dict) or 'officeId' not in data:
            raise BackendError("본인 확인 응답에 officeId 키가 없습니다. GET /api/chatbot/me의 응답 형식을 확인해 주세요.")
        office = data['officeId']
        # DB ID를 JSON 숫자 또는 숫자 문자열로 반환하는 경우를 모두 지원합니다.
        if isinstance(office, str) and re.fullmatch(r'[1-9][0-9]{0,18}', office):
            office = int(office)
        if isinstance(office, bool) or not isinstance(office, int) or not 0 < office <= 9223372036854775807:
            raise BackendError("본인 확인 응답의 officeId는 양의 정수 또는 숫자 문자열이어야 합니다. ID 값과 토큰은 표시하지 않습니다.")
        return str(office)

    async def get(self, category, token):
        if category in ('MILEAGE', 'FEE'):
            raise BackendError("마일리지·청구 정보의 본인 조회 API는 아직 지원하지 않습니다.")
        if category not in self.PATH:
            raise BackendError("지원하지 않는 조회 유형")
        data = await self.request("GET", self.cfg[self.PATH[category]], token)
        if not isinstance(data, list):
            raise BackendError("본인 조회 API 응답이 목록 형식이 아닙니다.")
        return data

    async def add_conversation(self, token, payload):
        # Office ID는 저장 API가 JWT에서 결정하며 요청 본문에 넣지 않습니다.
        return await self.request(
            "POST", self.cfg["inquiry_add_path"], token, payload=payload
        )

    async def conversation_history(self, token, conversation_id):
        return await self.request('GET', f'api/chatbot/conversations/{conversation_id}/messages', token)

    async def get_public_parking_spaces(self, token):
        # 기존 사용자 서버 주소와 JWT 전달 방식을 그대로 재사용합니다.
        data = await self.request("GET", "api/parking/spaces", token)
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise BackendError("사용자 주차 현황 API 응답이 목록 형식이 아닙니다.")
        return data

    # ----------로그인시 삭제해야함
    async def get_test_reservations(self):
        if (
            self.cfg["env"] != "development"
            or self.cfg["mode"] != "MOCK"
            or not self.cfg["test_reservation_enabled"]
        ):
            raise PermissionError("개발용 예약 조회가 비활성화되어 있습니다.")
        try:
            async with httpx.AsyncClient(
                base_url=self.cfg["base_url"], timeout=15
            ) as client:
                response = await client.get("api/chatbot/reservations/1")
                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            raise BackendError("테스트 예약 조회 실패") from e

    # ----------------

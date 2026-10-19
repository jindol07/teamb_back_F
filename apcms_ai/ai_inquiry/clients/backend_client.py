"""인증 토큰을 Spring Boot에 전달. 임의 user_id를 사용해 DB를 조회하지 않는다."""

import httpx
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
                    path,
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                )
                if r.status_code in (401, 403):
                    raise PermissionError("인증되지 않았거나 권한이 없습니다.")
                r.raise_for_status()
                return r.json() if r.content else {}
        except httpx.HTTPError as e:
            raise BackendError(f"Spring Boot API 호출 실패: {method} {path}") from e

    async def authenticate(self, token):
        data = await self.request("GET", self.cfg["auth_path"], token)
        # 실제 응답 구조 확정 시 여기 한 군데만 매핑
        candidate = data.get("data", data) if isinstance(data, dict) else {}
        if not isinstance(candidate, dict):
            raise BackendError("인증 응답 JSON 형식 불일치")
        office = (
            candidate.get("officeId")
            or candidate.get("office_id")
            or candidate.get("user_id")
        )
        if office is None:
            raise BackendError("인증 응답에 officeId/user_id가 없습니다.")
        return str(office)

    async def get(self, category, token):
        if category not in self.PATH:
            raise BackendError("지원하지 않는 조회 유형")
        return await self.request("GET", self.cfg[self.PATH[category]], token)

    async def add_conversation(self, token, payload):
        # 필드 매핑은 서버 DTO가 확정되면 변경. 현재 contract.md 참조
        return await self.request(
            "POST", self.cfg["inquiry_add_path"], token, payload=payload
        )

    async def get_public_parking_spaces(self):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    "http://127.0.0.1:81/alpharking/admin/api/parking/spaces/public"
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            raise BackendError("실시간 주차 현황 조회 실패") from e

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

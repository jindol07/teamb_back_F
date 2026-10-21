# D:/finalProjectB/back/apcms_ai/ai_vision/upload_limits.py

"""이미지 업로드의 전체 본문과 multipart 임시 파일 생성을 제한합니다."""

import threading
import asyncio
import math
from time import monotonic
from fastapi.routing import APIRoute
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse

from ai_vision.upload_policy import MAX_MULTIPART_BYTES


class SingleImageUploadRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def limited_handler(request):
            # 1. 파일 하나만 받는 API에서 기본 최대 1000개의 임시 파일이 생기지 않게 합니다.
            async with request.form(max_files=1, max_fields=0):
                return await original(request)
        return limited_handler


class UploadLimitsMiddleware:
    def __init__(self, app, max_bytes=None, capacity=2, read_timeout=15, upload_timeout=60):
        self.app = app
        self.max_bytes = MAX_MULTIPART_BYTES if max_bytes is None else max_bytes
        if type(self.max_bytes) is not int or self.max_bytes < 1 or type(capacity) is not int or capacity < 1:
            raise ValueError("업로드 본문·동시 처리 한도는 양의 정수여야 합니다.")
        if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 300
               for value in (read_timeout, upload_timeout)):
            raise ValueError("업로드 대기 시간은 0초 초과 300초 이하로 지정합니다.")
        self.read_timeout, self.upload_timeout = read_timeout, upload_timeout
        self._slots = threading.BoundedSemaphore(capacity)

    async def __call__(self, scope, receive, send):
        path, root = scope.get("path", ""), scope.get("root_path", "")
        if root and path.startswith(root + "/"):
            path = path[len(root):]
        if scope["type"] != "http" or scope.get("method") != "POST" or path.rstrip("/") != "/recognize":
            await self.app(scope, receive, send)
            return
        lengths = [value for key, value in scope.get("headers", []) if key.lower() == b"content-length"]
        if lengths and (len(lengths) != 1 or not lengths[0].isdigit()):
            await JSONResponse({"detail": "Content-Length가 올바르지 않습니다."}, status_code=400)(scope, receive, send)
            return
        # 과도하게 긴 숫자는 int 변환 전에 비교해 파싱 오류로 인한 500을 방지합니다.
        if lengths and (len(lengths[0]) > 20 or int(lengths[0]) > self.max_bytes):
            await self._too_large(scope, receive, send)
            return
        if not self._slots.acquire(blocking=False):
            await JSONResponse({"detail": "이미지 업로드 요청이 많습니다. 잠시 후 다시 시도해 주세요."},
                               status_code=503, headers={"Retry-After": "1"})(scope, receive, send)
            return
        received, rejected_status, replacement_sent = 0, None, False
        started = monotonic()

        async def bounded_receive():
            nonlocal received, rejected_status
            # 빈 연결이 업로드 슬롯을 계속 차지하지 않도록 읽기 공백과 수집 전체 시간을 제한합니다.
            remaining = self.upload_timeout - (monotonic() - started)
            try:
                if remaining <= 0:
                    raise TimeoutError
                message = await asyncio.wait_for(receive(), timeout=min(self.read_timeout, remaining))
            except TimeoutError as error:
                rejected_status = 408
                raise MultiPartException("업로드 수집 시간 한도 초과") from error
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    rejected_status = 413
                    # 2. 파서의 표준 오류 경로로 이미 생성된 임시 파일도 정리합니다.
                    raise MultiPartException("업로드 본문 크기 한도 초과")
            return message

        async def bounded_send(message):
            nonlocal replacement_sent
            if rejected_status is not None:
                # multipart 파서는 위 오류를 400으로 바꾸므로 실제 원인인 413으로 응답합니다.
                if not replacement_sent:
                    replacement_sent = True
                    if rejected_status == 413:
                        await self._too_large(scope, receive, send)
                    else:
                        await JSONResponse({"detail": "이미지 업로드 수집 시간이 초과됐습니다."}, status_code=408)(scope, receive, send)
                return
            await send(message)

        try:
            await self.app(scope, bounded_receive, bounded_send)
        finally:
            self._slots.release()

    async def _too_large(self, scope, receive, send):
        await JSONResponse({"detail": "이미지 업로드 전체 본문은 최대 11MB입니다."}, status_code=413)(scope, receive, send)

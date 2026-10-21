# D:/finalProjectB/back/apcms_ai/ai_vision/http_diagnostics.py

"""요청 본문·번호판·접속 정보를 제외한 HTTP 처리 진단을 기록합니다."""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from starlette.responses import JSONResponse


REQUEST_ID = ContextVar("vision_request_id", default=None)
LOGGER = logging.getLogger("uvicorn.error")


def _log(record, level=logging.INFO):
    # 진단 출력 실패가 완료된 API 응답을 실패로 바꾸지 않도록 분리합니다.
    try:
        LOGGER.log(level, json.dumps(record, ensure_ascii=False, allow_nan=False))
    except Exception:
        pass


def log_inference_error(error):
    _log({"event": "VISION_INFERENCE_ERROR", "request_id": REQUEST_ID.get(),
          "error_type": type(error).__name__}, logging.WARNING)


def response_headers(request_id, started):
    return {"X-Request-ID": request_id,
            "Server-Timing": f"app;dur={max(0, (time.perf_counter() - started) * 1000):.3f}"}


class RequestDiagnosticsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # 1. 사용자 헤더를 신뢰하지 않고 서버에서 새 식별값을 발급합니다.
        request_id, started = uuid.uuid4().hex, time.perf_counter()
        state = scope.setdefault("state", {})
        state["vision_request_id"], state["vision_request_started"] = request_id, started
        token = REQUEST_ID.set(request_id)
        status, error_type, completed, response_started = None, None, False, False

        async def diagnostic_send(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status, response_started = message["status"], True
                headers = [(key, value) for key, value in message.get("headers", []) if key.lower() != b"x-request-id"]
                headers.extend((key.lower().encode("ascii"), value.encode("ascii"))
                               for key, value in response_headers(request_id, started).items())
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, diagnostic_send)
            completed = True
        except Exception as error:
            error_type = type(error).__name__
            status = 500 if status is None else status
            if response_started:
                # 이미 보낸 응답을 500으로 바꿀 수 없으므로 스트림 실패는 상위 서버에 알립니다.
                raise
            await JSONResponse({"detail": "AI 서버 처리 중 오류가 발생했습니다."}, status_code=500)(scope, receive, diagnostic_send)
            completed = True
        finally:
            # 2. 실제 경로·쿼리·헤더 대신 라우트 틀과 고정된 진단 항목만 기록합니다.
            route = getattr(scope.get("route"), "path", "UNMATCHED")
            method = scope.get("method")
            _log({"event": "VISION_HTTP_REQUEST", "request_id": request_id,
                  "method": method if method in {"GET", "POST", "HEAD", "OPTIONS", "PUT", "PATCH", "DELETE"} else "OTHER",
                  "route": route, "status": status,
                  "duration_ms": round(max(0, (time.perf_counter() - started) * 1000), 3),
                  "completed": completed, "response_started": response_started, "error_type": error_type})
            REQUEST_ID.reset(token)

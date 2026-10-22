"""Spring Boot API 계약 확정 전, localhost 전용 화재 알림 수신 모의 서버.

사용: python -m ai_vision.tests.safety.mock_fire_alert_api --port 8765
Ctrl+C로 종료합니다. 데이터는 메모리에서만 유지되며 DB에는 저장하지 않습니다.
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


# 1. localhost 전용 모의 수신기
class MockAlertHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/mock/fire-alerts":
            self._respond(404, {"error": "unknown_path"})
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if not 1 <= n <= 64 * 1024:
                self._respond(413, {"error": "payload_too_large"})
                return
            request = json.loads(self.rfile.read(n).decode("utf-8"))
            transition_id = self.headers.get("X-Idempotency-Key")
            if (not isinstance(request, dict)
                    or not isinstance(transition_id, str)
                    or transition_id != request.get("transition_id")
                    or request.get("schema_version") != "1.0"
                    or request.get("is_test") is not True
                    or request.get("hazard_type") not in ("FIRE", "SMOKE")):
                self._respond(400, {"error": "invalid_test_payload"})
                return
        except (ValueError, UnicodeDecodeError):
            self._respond(400, {"error": "invalid_json"})
            return
        if transition_id in self.server.received_ids:
            self._respond(200, {"result": "already_received"})
            return
        self.server.received_ids.add(transition_id)
        print(f"[수신] {request['hazard_type']} {request.get('status')} | "
              f"incident={str(request.get('incident_id', ''))[:8]} | "
              f"transition={transition_id[:12]} | 시험 데이터", flush=True)
        self._respond(201, {"result": "received", "transition_id": transition_id})

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "unique_alerts": len(self.server.received_ids)})
        else:
            self._respond(404, {"error": "unknown_path"})

    def _respond(self, code, content):
        raw = json.dumps(content).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


def create_server(port=8765):
    """1-1. 외부 네트워크에 공개하지 않고 루프백 인터페이스만 바인딩."""
    server = ThreadingHTTPServer(("127.0.0.1", port), MockAlertHandler)
    server.received_ids = set()
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description="화재·연기 전송 시험용 localhost 모의 서버")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("포트는 1~65535 사이여야 합니다.")
    with create_server(args.port) as server:
        print(f"[모의 수신기 시작] http://127.0.0.1:{args.port}/api/mock/fire-alerts")
        print("실제 Spring Boot 서버가 아닙니다. Ctrl+C로 종료합니다.")
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            print("\n[모의 수신기 종료]")


if __name__ == "__main__":
    main()

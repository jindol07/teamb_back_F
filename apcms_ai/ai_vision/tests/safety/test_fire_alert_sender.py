"""화재/연기 Spring Boot 연동 이전의 로컬 JSON 계약 및 HTTP 모의 서버 테스트."""

import contextlib
import io
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from ai_vision.safety import fire_alert_sender as sender


# 1. 공통 테스트 데이터
SAMPLE_SUMMARY = {
    "record_type": "FIRE_SMOKE_LIVE_TEST",
    "source": "VIDEO",
    "source_name": "fire_incident_sequence.mp4",
    "started_at_utc": "2026-10-21T12:07:11.550580+00:00",
}


def transition(status="SUSPECTED", frame=17, incident="event-1", confidence=0.8):
    return {
        "event_id": incident,
        "region_id": "region-1",
        "status": status,
        "type": "FIRE",
        "source_seconds": frame / 15.0,
        "frame_index": frame,
        "confidence": confidence,
        "bbox": [10, 20, 110, 120],
        "hits_in_window": 3,
        "started_at_seconds": 1.0,
        "reason": None,
        "logged_at_utc": "2026-10-21T12:07:12+00:00",
    }


class _CollectorHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers["Content-Length"])
        data = json.loads(self.rfile.read(size))
        self.server.requests.append((self.path, data, dict(self.headers)))
        if self.server.codes:
            code = self.server.codes.pop(0)
        else:
            code = 201
        # Spring Boot FireSafetyResponse와 동일한 성공 ACK를 반환합니다.
        ack = {
            "transitionId": data["transition_id"],
            "outcome": "STORED",
            "aiDetectionEventId": 1,
            "safetyIncidentId": None if data["status"] == "CLEARED" else 1,
            "notificationsCreated": 0,
            "isTest": data["is_test"],
        }
        raw = json.dumps(ack).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


@contextlib.contextmanager
def mock_server(codes=None):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CollectorHandler)
    server.requests = []
    server.codes = list(codes or [])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_address[1]}/api/alerts"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class FireAlertSenderTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.set_results([transition(), transition("CLEARED", frame=120),
                          transition("REOPENED", frame=240), transition("ONGOING", frame=260),
                          transition("SESSION_ENDED", frame=300)])

    def set_results(self, transitions, summary=None):
        (self.folder / "summary.json").write_text(json.dumps(summary or SAMPLE_SUMMARY), encoding="utf-8")
        (self.folder / "incident_history.json").write_text(json.dumps({"transitions": transitions}), encoding="utf-8")

    # 2. 저장 데이터 -> DTO 검증
    def test_01_default_includes_three_actionable_statuses(self):
        values = sender.build_payloads(self.folder)
        self.assertEqual([x["status"] for x in values], ["SUSPECTED", "CLEARED", "REOPENED"])
        self.assertTrue(all(x["is_test"] and x["requires_human_review"] for x in values))

    def test_02_optional_statuses(self):
        values = sender.build_payloads(self.folder, include_ongoing=True, include_session_ended=True)
        self.assertEqual(len(values), 5)

    def test_03_stable_transition_id(self):
        one = sender.build_payloads(self.folder)
        two = sender.build_payloads(self.folder)
        self.assertEqual([x["transition_id"] for x in one], [x["transition_id"] for x in two])
        self.assertEqual(len({x["transition_id"] for x in one}), 3)

    def test_04_duplicate_records_removed(self):
        same = transition()
        self.set_results([same, same])
        self.assertEqual(len(sender.build_payloads(self.folder)), 1)

    def test_05_two_fire_regions_separate(self):
        a = transition(incident="event-a")
        b = transition(incident="event-b")
        b["region_id"] = "right-region"
        self.set_results([a, b])
        self.assertEqual(len(sender.build_payloads(self.folder)), 2)

    def test_06_missing_json_fails(self):
        (self.folder / "incident_history.json").unlink()
        with self.assertRaises(FileNotFoundError):
            sender.build_payloads(self.folder)

    def test_07_invalid_confidence_fails(self):
        record = transition(confidence=1.5)
        self.set_results([record])
        with self.assertRaises(ValueError):
            sender.build_payloads(self.folder)

    def test_08_malformed_bbox_fails(self):
        record = transition()
        record["bbox"] = [50, 40, 20, 60]
        self.set_results([record])
        with self.assertRaises(ValueError):
            sender.build_payloads(self.folder)

    def test_09_json_duplicate_keys_fails(self):
        (self.folder / "incident_history.json").write_text('{"transitions":[],"transitions":[]}', encoding="utf-8")
        with self.assertRaises(ValueError):
            sender.build_payloads(self.folder)

    def test_10_invalid_timezone_fails(self):
        record = transition()
        record["logged_at_utc"] = "2026-10-22T09:00:00"
        self.set_results([record])
        with self.assertRaises(ValueError):
            sender.build_payloads(self.folder)

    def test_11_empty_history(self):
        self.set_results([])
        self.assertEqual(sender.build_payloads(self.folder), [])

    # 3. API 주소/전송 안정성
    def test_12_http_remote_rejected(self):
        with self.assertRaises(ValueError):
            sender.validate_endpoint("http://example.com/api/alerts")

    def test_13_https_and_local_http_allowed(self):
        self.assertEqual(sender.validate_endpoint("https://example.com/alerts"), "https://example.com/alerts")
        self.assertEqual(sender.validate_endpoint("http://127.0.0.1:8080/alerts"), "http://127.0.0.1:8080/alerts")

    def test_14_urls_with_password_rejected(self):
        with self.assertRaises(ValueError):
            sender.validate_endpoint("https://foo:bar@example.com/alerts")

    def test_15_real_local_mock_receives_same_idempotency_key(self):
        payload = sender.build_payloads(self.folder)[0]
        with mock_server() as (server, url):
            code = sender.post_payload(payload, url, token="fake-token", max_retries=0)
            self.assertEqual(code, 201)
            self.assertEqual(server.requests[0][1], payload)
            self.assertEqual(server.requests[0][2]["X-Idempotency-Key"], payload["transition_id"])
            self.assertEqual(server.requests[0][2]["Authorization"], "Bearer fake-token")

    def test_16_server_error_retried(self):
        payload = sender.build_payloads(self.folder)[0]
        with mock_server(codes=[503, 200]) as (server, url):
            with patch.object(sender.time, "sleep", lambda _: None):
                code = sender.post_payload(payload, url, max_retries=1)
            self.assertEqual(code, 200)
            self.assertEqual(len(server.requests), 2)

    def test_17_bad_request_not_retried(self):
        payload = sender.build_payloads(self.folder)[0]
        with mock_server(codes=[400, 201]) as (server, url):
            with self.assertRaises(RuntimeError):
                sender.post_payload(payload, url, max_retries=2)
            self.assertEqual(len(server.requests), 1)

    def test_18_success_checkpoint_prevents_repeat(self):
        payloads = sender.build_payloads(self.folder)
        state_file = self.folder / "checkpoint.json"
        with mock_server() as (server, url):
            first = sender.send_pending(payloads, url, state_file=state_file, max_retries=0)
            again = sender.send_pending(payloads, url, state_file=state_file, max_retries=0)
            self.assertEqual(first["sent"], 3)
            self.assertEqual(again["sent"], 0)
            self.assertEqual(again["already_sent"], 3)
            self.assertEqual(len(server.requests), 3)

    def test_19_checkpoint_only_successes(self):
        payloads = sender.build_payloads(self.folder)
        state_file = self.folder / "checkpoint.json"
        with mock_server(codes=[201, 400, 201, 201]) as (server, url):
            with self.assertRaises(RuntimeError):
                sender.send_pending(payloads, url, state_file=state_file, max_retries=0)
            current = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(len(current["acknowledged_transition_ids"]), 1)
            result = sender.send_pending(payloads, url, state_file=state_file, max_retries=0)
            self.assertEqual(result["sent"], 2)
            self.assertEqual(result["already_sent"], 1)

    def test_20_mock_receiver_duplicate_ack(self):
        from ai_vision.tests.safety.mock_fire_alert_api import create_server
        server = create_server(0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/api/mock/fire-alerts"
            payload = sender.build_payloads(self.folder)[0]
            self.assertEqual(sender.post_payload(payload, url, max_retries=0), 201)
            self.assertEqual(sender.post_payload(payload, url, max_retries=0), 200)
            self.assertEqual(len(server.received_ids), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_21_mock_receiver_health(self):
        import urllib.request
        from ai_vision.tests.safety.mock_fire_alert_api import create_server
        server = create_server(0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{server.server_address[1]}/health", timeout=2) as r:
                data = json.loads(r.read())
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["unique_alerts"], 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    # 4. 사용자의 명시적 요청 없이는 전송 금지
    def test_20_cli_default_dry_run(self):
        output = io.StringIO()
        with patch("sys.stdout", output):
            code = sender.main(["--results", str(self.folder)])
        self.assertEqual(code, 0)
        self.assertIn("DRY-RUN", output.getvalue())
        self.assertFalse((self.folder / "fire_alert_sent_state.json").exists())

    def test_21_cli_rejects_send_without_url(self):
        with patch("sys.stdout", io.StringIO()):
            self.assertEqual(sender.main(["--results", str(self.folder), "--send"]), 1)

    def test_22_cli_rejects_test_records_without_opt_in(self):
        with patch("sys.stdout", io.StringIO()):
            self.assertEqual(sender.main(["--results", str(self.folder), "--send",
                                          "--url", "http://127.0.0.1:9999/alerts"]), 1)

    def test_23_preview_file_created_without_send(self):
        path = self.folder / "preview.json"
        with patch("sys.stdout", io.StringIO()):
            result = sender.main(["--results", str(self.folder), "--preview-out", str(path)])
        self.assertEqual(result, 0)
        self.assertEqual(len(json.loads(path.read_text(encoding="utf-8"))["alerts"]), 3)

    def test_24_cli_local_end_to_end(self):
        with mock_server() as (server, url):
            with patch("sys.stdout", io.StringIO()):
                result = sender.main(["--results", str(self.folder), "--send", "--allow-test-records", "--url", url])
            self.assertEqual(result, 0)
            self.assertEqual(len(server.requests), 3)


if __name__ == "__main__":
    unittest.main()

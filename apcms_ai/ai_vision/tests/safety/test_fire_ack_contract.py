"""HTTP 2xx라도 Spring Boot의 의미상 ACK가 다르면 체크포인트를 남기지 않는지 검증."""
from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from ai_vision.safety import fire_alert_sender as sender


URL = "http://127.0.0.1:81/alpharking/admin/api/parking/ai/fire-alerts"
PAYLOAD = {
    "transition_id": "a" * 64,
    "status": "SUSPECTED",
    "is_test": True,
}


def valid_ack(payload=PAYLOAD):
    return {
        "transitionId": payload["transition_id"],
        "outcome": "STORED",
        "aiDetectionEventId": 42,
        "safetyIncidentId": 6,
        "notificationsCreated": 3,
        "isTest": payload["is_test"],
    }


class FakeResponse:
    def __init__(self, value, status=200):
        self.status = status
        self._data = io.BytesIO(value)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._data.close()

    def read(self, amount=-1):
        return self._data.read(amount)


class FakeOpener:
    def __init__(self, raw, status=200):
        self.raw = raw
        self.status = status
        self.calls = 0

    def open(self, request, timeout=5.0):
        self.calls += 1
        return FakeResponse(self.raw, self.status)


def raw_ack(data):
    return json.dumps(data).encode("utf-8")


class FireAckContractTest(unittest.TestCase):
    def assert_rejected(self, data):
        opener = FakeOpener(raw_ack(data))
        with self.assertRaisesRegex(RuntimeError, "서버 ACK|HTTP 2xx|중복 전이"):
            sender.post_payload(PAYLOAD, URL, opener=opener, max_retries=0)
        self.assertEqual(opener.calls, 1)

    def test_01_valid_stored_ack(self):
        self.assertEqual(sender.post_payload(PAYLOAD, URL, opener=FakeOpener(raw_ack(valid_ack())), max_retries=0), 200)

    def test_02_valid_duplicate_ack(self):
        ack = valid_ack()
        ack.update(outcome="DUPLICATE", notificationsCreated=0)
        self.assertEqual(sender.post_payload(PAYLOAD, URL, opener=FakeOpener(raw_ack(ack)), max_retries=0), 200)

    def test_03_wrong_transition_id(self):
        ack = valid_ack()
        ack["transitionId"] = "b" * 64
        self.assert_rejected(ack)

    def test_04_unrecognized_outcome(self):
        ack = valid_ack()
        ack["outcome"] = "OK"
        self.assert_rejected(ack)

    def test_05_invalid_event_id(self):
        ack = valid_ack()
        ack["aiDetectionEventId"] = 0
        self.assert_rejected(ack)

    def test_06_wrong_test_flag(self):
        ack = valid_ack()
        ack["isTest"] = False
        self.assert_rejected(ack)

    def test_07_duplicate_with_new_notifications(self):
        ack = valid_ack()
        ack["outcome"] = "DUPLICATE"
        self.assert_rejected(ack)

    def test_08_reject_empty_ack(self):
        with self.assertRaisesRegex(RuntimeError, "HTTP 2xx"):
            sender.post_payload(PAYLOAD, URL, opener=FakeOpener(b""), max_retries=0)

    def test_09_reject_html_on_http_200(self):
        with self.assertRaisesRegex(RuntimeError, "HTTP 2xx"):
            sender.post_payload(PAYLOAD, URL, opener=FakeOpener(b"<html>OK</html>"), max_retries=0)

    def test_10_reject_oversized_ack(self):
        with self.assertRaisesRegex(RuntimeError, "16KiB"):
            sender.post_payload(PAYLOAD, URL, opener=FakeOpener(b"x" * (16 * 1024 + 1)), max_retries=0)

    def test_11_cleared_cannot_create_notification(self):
        payload = {**PAYLOAD, "status": "CLEARED"}
        ack = valid_ack(payload)
        with self.assertRaises(RuntimeError):
            sender.post_payload(payload, URL, opener=FakeOpener(raw_ack(ack)), max_retries=0)

    def test_12_cleared_stored_valid_without_incident(self):
        payload = {**PAYLOAD, "status": "CLEARED"}
        ack = valid_ack(payload)
        ack["safetyIncidentId"] = None
        ack["notificationsCreated"] = 0
        self.assertEqual(sender.post_payload(payload, URL, opener=FakeOpener(raw_ack(ack)), max_retries=0), 200)

    def test_13_invalid_ack_does_not_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "fire_alert_sent_state.json"
            bad_opener = FakeOpener(b'{}')
            def post(payload, url, *, token=None, timeout=5.0, max_retries=0):
                return sender.post_payload(payload, url, token=token, timeout=timeout,
                                           max_retries=max_retries, opener=bad_opener)
            with self.assertRaises(RuntimeError):
                sender.send_pending([copy.deepcopy(PAYLOAD)], URL, state_file=state,
                                    post=post, max_retries=0)
            self.assertFalse(state.exists())


if __name__ == "__main__":
    unittest.main()

# APCMS AI 점유 이벤트 전송 및 재시도 테스트

# 실제 Spring Boot 서버로 HTTP 요청하지 않고 가짜 응답을 사용하여 전송 로직을 검증한다.

import tempfile
import unittest
import requests

from pathlib import Path
from unittest.mock import patch, Mock

from ai_vision.parking import parking_event_sender as sender


# 1. TestParkingEventRetry - 전송 및 재시도 검증
class TestParkingEventRetry(unittest.TestCase):

    # 1-1. setUp() - 각 테스트 실행 전 임시 환경 준비
    def setUp(self):

        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        # 기존 설정값 보관
        self.original_pending = sender.PENDING_PATH
        self.original_rejected = sender.REJECTED_PATH
        self.original_enabled = sender.SEND_ENABLED
        self.original_key = sender.API_KEY

        # 테스트 전용 파일 경로 사용
        sender.PENDING_PATH = (
            Path(self.temp_dir.name) / "pending_events.json"
        )

        sender.REJECTED_PATH = (
            Path(self.temp_dir.name) / "rejected_events.json"
        )

        sender.SEND_ENABLED = True
        sender.API_KEY = "TEST_KEY"

        # 테스트 후 원래 설정 복구
        self.addCleanup(self.restore_settings)

        # 테스트 이벤트 생성
        self.event = sender.create_occupancy_event(
            "A-01",
            "OCCUPIED",
            0.8
        )

    # 1-2. restore_settings() - 테스트 설정 복구
    def restore_settings(self):

        sender.PENDING_PATH = self.original_pending
        sender.REJECTED_PATH = self.original_rejected
        sender.SEND_ENABLED = self.original_enabled
        sender.API_KEY = self.original_key

    # 2. test_connection_failure_and_retry()
    # 연결 실패 후 동일 이벤트 재전송 검사
    def test_connection_failure_and_retry(self):

        # 2-1. 첫 번째 POST에서 연결 오류 발생
        with patch.object(
            sender.requests,
            "post",
            side_effect=requests.ConnectionError("테스트 연결 실패")
        ):
            sender.queue_occupancy_event(self.event)

        # 2-2. 이벤트가 대기 파일에 남았는지 검사
        pending = sender.load_pending_events()

        self.assertEqual(len(pending), 1)
        self.assertEqual(
            pending[0]["event_id"],
            self.event["event_id"]
        )

        self.assertEqual(
            pending[0]["detected_at"],
            self.event["detected_at"]
        )

        # 2-3. 두 번째 POST는 정상 성공 처리
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"outcome": "UPDATED"}
        response.raise_for_status.return_value = None

        with patch.object(
            sender.requests,
            "post",
            return_value=response
        ) as mocked_post:

            sender.retry_pending_events()

            # 2-4. 같은 UUID의 이벤트를 보냈는지 확인
            sent_event = mocked_post.call_args.kwargs["json"]

            self.assertEqual(
                sent_event["event_id"],
                self.event["event_id"]
            )

            self.assertEqual(
                sent_event["detected_at"],
                self.event["detected_at"]
            )

        # 2-5. 성공한 이벤트는 대기 목록에서 제거
        self.assertEqual(
            sender.load_pending_events(),
            []
        )

    # 3. test_http_409_rejected()
    # HTTP 409 이벤트 별도 보관 검사
    def test_http_409_rejected(self):

        # 3-1. HTTP 409 응답 객체 생성
        response = Mock()
        response.status_code = 409
        response.text = "Conflict"

        # 3-2. 실제 HTTP 요청 대신 409 반환
        with patch.object(
            sender.requests,
            "post",
            return_value=response
        ):
            sender.queue_occupancy_event(self.event)

        # 3-3. 409 이벤트는 대기 목록에서 제거
        self.assertEqual(
            sender.load_pending_events(),
            []
        )

        # 3-4. 거부 파일에 보관했는지 확인
        self.assertTrue(sender.REJECTED_PATH.is_file())

        import json

        with open(
            sender.REJECTED_PATH,
            "r",
            encoding="utf-8"
        ) as file:
            rejected = json.load(file)

        self.assertEqual(len(rejected), 1)
        self.assertEqual(
            rejected[0]["event"]["event_id"],
            self.event["event_id"]
        )

        self.assertEqual(
            rejected[0]["http_status"],
            409
        )


# 4. 테스트 실행부
if __name__ == "__main__":
    unittest.main()
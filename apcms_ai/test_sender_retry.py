# APCMS AI 이벤트 동일 UUID 재전송 테스트
# 첫 번째 요청은 연결 실패, 두 번째 요청은 처리 성공으로 가정
# 실제 Spring Boot 서버나 Oracle DB에는 접근하지 않음

import requests

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from ai_vision.parking import parking_event_sender as sender


# 1. 백엔드의 정상 처리 응답을 가상으로 생성
mock_response = Mock()
mock_response.status_code = 200
mock_response.json.return_value = {
    "outcome": "PROCESSED",
    "parkingUsageId": 37
}


# 2. 임시 폴더를 사용하여 실제 대기 이벤트 파일 보호
with TemporaryDirectory() as temp_dir:

    test_pending_path = Path(temp_dir) / "pending_events.json"

    # 3. HTTP 요청 결과를 순서대로 지정
    # 첫 번째 POST : 연결 실패
    # 두 번째 POST : 정상 처리(PROCESSED)
    with (
        patch.object(sender, "SEND_ENABLED", True),
        patch.object(sender, "API_KEY", "test-key"),
        patch.object(sender, "PENDING_PATH", test_pending_path),
        patch.object(
            sender.requests,
            "post",
            side_effect=[
                requests.ConnectionError("모의 연결 실패"),
                mock_response
            ]
        ) as mock_post
    ):

        # 4. 입차 이벤트 생성
        event = sender.create_vehicle_event(
            "91소6408",
            "ENTRY",
            0.95,
            plate_type="KOREAN_VALID"
        )

        original_id = event["event_id"]

        # 5. 첫 번째 전송 - 실패
        sender.queue_ai_event(event)

        pending_after_failure = sender.load_pending_events()

        print("\n=== 첫 번째 전송 결과 ===")
        print("대기 이벤트 개수:", len(pending_after_failure))

        assert len(pending_after_failure) == 1
        assert pending_after_failure[0]["event_id"] == original_id

        # 6. 두 번째 전송 - 기존 대기 이벤트 재전송
        result = sender.retry_pending_events()

        pending_after_success = sender.load_pending_events()

        # 7. 두 요청에 사용된 이벤트의 UUID 확인
        first_event = mock_post.call_args_list[0].kwargs["json"]
        second_event = mock_post.call_args_list[1].kwargs["json"]

        print("\n=== 재전송 결과 ===")
        print("첫 번째 UUID:", first_event["event_id"])
        print("두 번째 UUID:", second_event["event_id"])
        print("재전송 결과:", result[0]["status"])
        print("남은 대기 이벤트:", len(pending_after_success))
        print("HTTP 요청 시도 횟수:", mock_post.call_count)

        # 8. 원본 이벤트 유지 및 정상 처리 검증
        assert mock_post.call_count == 2
        assert first_event["event_id"] == second_event["event_id"]
        assert first_event["detected_at"] == second_event["detected_at"]
        assert result[0]["status"] == "PROCESSED"
        assert len(pending_after_success) == 0

        print("\n동일 UUID 재전송 테스트: PASS")
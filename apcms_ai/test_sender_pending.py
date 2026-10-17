# APCMS AI 이벤트 PENDING 응답 처리 테스트
# 실제 Spring Boot 서버와 Oracle DB에는 접근하지 않음

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock

from ai_vision.parking import parking_event_sender as sender


# 1. 실제 이벤트 파일을 변경하지 않도록 임시 폴더 사용
with TemporaryDirectory() as temp_dir:

    test_pending_path = Path(temp_dir) / "pending_events.json"
    test_held_path = Path(temp_dir) / "held_events.json"

    # 2. HTTP 200이지만 실제 처리가 보류된 응답 생성
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "outcome": "PENDING",
        "detail": "선행 조건 확인 필요"
    }

    # 3. 실제 전송을 막고 테스트용 설정으로 변경
    with (
        patch.object(sender, "SEND_ENABLED", True),
        patch.object(sender, "API_KEY", "test-key"),
        patch.object(sender, "PENDING_PATH", test_pending_path),
        patch.object(sender, "HELD_PATH", test_held_path),
        patch.object(
            sender.requests,
            "post",
            return_value=mock_response
        ) as mock_post
    ):

        # 4. 차량과 주차구획 매칭 이벤트 생성
        event = sender.create_space_match_event(
            "91소6408",
            "A-01",
            0.92,
            "TRACKING",
            plate_type="KOREAN_VALID"
        )

        original_id = event["event_id"]

        # 5. 백엔드가 PENDING을 반환한 상황 테스트
        result = sender.queue_ai_event(event)

        # 6. 이벤트가 어느 파일에 보관됐는지 확인
        pending_events = sender.load_pending_events()
        held_events = sender.load_event_list(
            sender.HELD_PATH
        )

        print("\n=== PENDING 테스트 결과 ===")
        print("대기 이벤트 개수:", len(pending_events))
        print("보류 이벤트 개수:", len(held_events))
        print("원본 UUID:", original_id)
        print("보류 UUID:", held_events[0]["event"]["event_id"])
        print("보류 사유:", held_events[0]["reason"])
        print("처리 결과:", result)

        # 7. PENDING이 완료 처리되지 않았는지 검증
        assert len(pending_events) == 0
        assert len(held_events) == 1
        assert held_events[0]["event"]["event_id"] == original_id
        assert held_events[0]["reason"] == "BACKEND_PENDING"
        assert result[0]["status"] == "PENDING"
        assert mock_post.call_count == 1

        print("PENDING 응답 처리 테스트: PASS")
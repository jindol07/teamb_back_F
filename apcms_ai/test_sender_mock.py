# 1. 테스트에 사용할 라이브러리
import requests

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ai_vision.parking import parking_event_sender as sender


# 2. 임시 폴더를 사용해 실제 이벤트 보관 파일 보호
with TemporaryDirectory() as temp_dir:

    test_pending_path = Path(temp_dir) / "pending_events.json"

    # 3. 실제 HTTP 전송 대신 연결 실패 상황을 재현
    with (
        patch.object(sender, "SEND_ENABLED", True),
        patch.object(sender, "API_KEY", "test-key"),
        patch.object(sender, "PENDING_PATH", test_pending_path),
        patch.object(
            sender.requests,
            "post",
            side_effect=requests.ConnectionError("모의 연결 실패")
        )
    ):

        # 4. 입차 이벤트 생성
        event = sender.create_vehicle_event(
            "91소6408",
            "ENTRY",
            0.95,
            plate_type="KOREAN_VALID"
        )

        original_id = event["event_id"]

        # 5. 전송 시도: 연결 오류를 발생시키도록 설정함
        sender.queue_ai_event(event)

        # 6. 실패한 이벤트가 파일에 저장되었는지 확인
        pending_events = sender.load_pending_events()

        print("\n=== 테스트 결과 ===")
        print("대기 파일 생성:", test_pending_path.is_file())
        print("대기 이벤트 개수:", len(pending_events))
        print("원본 UUID:", original_id)
        print("저장된 UUID:", pending_events[0]["event_id"])

        # 7. 원본 UUID와 저장된 UUID가 동일한지 검증
        assert len(pending_events) == 1
        assert pending_events[0]["event_id"] == original_id

        print("통신 실패 이벤트 보관 테스트: PASS")

# 8. 테스트 종료 시 임시 폴더와 파일 자동 삭제
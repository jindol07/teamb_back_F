# ai_vision/recognition/live_gate_lifecycle.py
"""카메라, 처리기, 세션의 종료 작업을 안전하게 순차 실행합니다."""


# 1. 실행이 끝났거나 실패했을 때 관련 자원을 해제하는 함수
# 1-1. capture: OpenCV 카메라 등 release()를 갖는 입력 객체
# 1-2. processor: 처리 버퍼 등을 정리하는 close()를 갖는 객체
# 1-3. session: 추가 처리 금지를 위해 close()를 갖는 세션 객체
# 1-4. None은 해당 자원이 생성되지 않았다는 뜻으로 허용합니다.
def close_resources(capture=None, processor=None, session=None):
    # 2. 실패 횟수 누적
    failures = 0
    # 2-1. 카메라 → 처리기 → 세션 순서로 정리할 메서드를 선택합니다.
    for resource, method in ((capture, "release"), (processor, "close"), (session, "close")):
        # 2-2. 초기화 도중 실패하여 객체가 없다면 다음 자원으로 넘어갑니다.
        if resource is None:
            continue
        try:
            # 3. 메서드 이름으로 함수를 가져온 뒤 호출합니다.
            # 3-1. getattr(resource, method)는 예를 들어 capture.release를 얻습니다.
            getattr(resource, method)()
        except Exception:
            # 3-2. 한 객체에서 실패해도 다른 객체의 종료를 계속 시도합니다.
            # 3-3. 예외 내용은 외부 결과에 노출하지 않고 건수만 기록합니다.
            failures += 1
    # 4. 전체 정리 실패 건수를 호출자에게 돌려줍니다.
    return failures

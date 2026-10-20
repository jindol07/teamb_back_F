# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_lifecycle.py

"""실행 실패 중에도 카메라·처리기·세션의 정리를 각각 시도합니다."""


def close_resources(capture=None, processor=None, session=None):
    failures = 0
    # 1. 앞 자원의 정리 실패가 뒤 자원의 정리를 막지 않도록 분리합니다.
    for resource, method in ((capture, "release"), (processor, "close"), (session, "close")):
        if resource is None:
            continue
        try:
            getattr(resource, method)()
        except Exception:
            failures += 1
    return failures

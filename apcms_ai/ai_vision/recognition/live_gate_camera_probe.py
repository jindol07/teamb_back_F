# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_camera_probe.py

"""명시적으로 요청한 카메라에서 한 프레임만 읽고 자원을 해제합니다."""


def probe_camera(index, capture_factory=None, frame_consumer=None):
    if type(index) is not int or not 0 <= index <= 32:
        raise ValueError("카메라 번호는 0~32 정수여야 합니다.")
    if frame_consumer is not None and not callable(frame_consumer):
        raise ValueError("프레임 처리 함수가 필요합니다.")
    capture = None
    failure_reason = "CAMERA_EXCEPTION"
    result = {"status": "FAILED", "camera_index": index, "reason": "OPEN_FAILED",
              "width": None, "height": None, "released": False}
    try:
        # 1. 기본 환경 점검에서는 이 함수 자체를 호출하지 않습니다.
        if capture_factory is None:
            import cv2
            capture_factory = cv2.VideoCapture
        capture = capture_factory(index)
        if capture.isOpened():
            ok, frame = capture.read()
            if not ok:
                result["reason"] = "READ_FAILED"
            else:
                import numpy as np
                if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or
                        frame.shape[2] != 3 or not frame.size):
                    result["reason"] = "INVALID_FRAME"
                else:
                    # 선택한 소비자에만 프레임을 전달하며 일반 점검 결과에는 이미지를 넣지 않습니다.
                    if frame_consumer is not None:
                        failure_reason = "FRAME_CONSUMER_FAILED"
                        frame_consumer(frame)
                    result.update(status="FRAME_READ", reason=None, height=int(frame.shape[0]), width=int(frame.shape[1]))
    except Exception:
        # 2. 장치 오류의 원문 대신 고정 코드를 남기며 자동 재연결하지 않습니다.
        result.update(status="FAILED", reason=failure_reason)
    finally:
        if capture is not None:
            try:
                capture.release()
                result["released"] = True
            except Exception:
                result.update(status="FAILED", reason="RELEASE_FAILED")
    return result

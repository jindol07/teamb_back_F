# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_camera_probe.py

"""명시적으로 요청한 카메라에서 한 프레임만 읽고 자원을 해제합니다."""


# 1. 카메라 접근과 한 프레임 확인
# 1-1. index는 0~32의 카메라 장치 번호입니다.
# 1-2. capture_factory를 넣으면 실제 장치 대신 테스트용 객체를 사용할 수 있습니다.
# 1-3. frame_consumer는 확보한 이미지에 추가 작업을 할 선택적 콜백입니다.
# 함수 설명: probe_camera() — 카메라를 한 번만 열고 프레임 형식을 확인한 후 해제 상태를 포함한 결과를 반환합니다.
def probe_camera(index, capture_factory=None, frame_consumer=None):
    # 2. 입력값을 검사합니다.
    # 2-1. bool을 정수로 오인하지 않기 위해 type(...) is int를 사용합니다.
    if type(index) is not int or not 0 <= index <= 32:
        raise ValueError("카메라 번호는 0~32 정수여야 합니다.")
    if frame_consumer is not None and not callable(frame_consumer):
        raise ValueError("프레임 처리 함수가 필요합니다.")
    # 3. 처음에는 실패를 기본 상태로 두고 정상 완료 때만 성공으로 변경합니다.
    capture = None
    failure_reason = "CAMERA_EXCEPTION"
    result = {"status": "FAILED", "camera_index": index, "reason": "OPEN_FAILED",
              "width": None, "height": None, "released": False}
    # 4. 카메라 열기·읽기·프레임 형식을 확인합니다.
    try:
        # 1. 기본 환경 점검에서는 이 함수 자체를 호출하지 않습니다.
        if capture_factory is None:
            import cv2
            capture_factory = cv2.VideoCapture
        # 4-1. 카메라를 열고 한 번만 read()합니다. 자동 재연결은 하지 않습니다.
        capture = capture_factory(index)
        if capture.isOpened():
            ok, frame = capture.read()
            if not ok:
                result["reason"] = "READ_FAILED"
            else:
                import numpy as np
                # 4-2. OpenCV용 BGR 3채널 uint8 영상인지 확인합니다.
                if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or
                        frame.shape[2] != 3 or not frame.size):
                    result["reason"] = "INVALID_FRAME"
                else:
                    # 선택한 소비자에만 프레임을 전달하며 일반 점검 결과에는 이미지를 넣지 않습니다.
                    # 4-3. 필요하면 반환 전에 전달된 콜백으로 한 장을 처리합니다.
                    if frame_consumer is not None:
                        failure_reason = "FRAME_CONSUMER_FAILED"
                        frame_consumer(frame)
                    result.update(status="FRAME_READ", reason=None, height=int(frame.shape[0]), width=int(frame.shape[1]))
    # 5. 내부 예외 문자열 대신 사전에 정의한 실패 코드만 반환합니다.
    except Exception:
        # 2. 장치 오류의 원문 대신 고정 코드를 남기며 자동 재연결하지 않습니다.
        result.update(status="FAILED", reason=failure_reason)
    # 6. 읽기가 실패해도 열었던 장치를 해제합니다.
    finally:
        if capture is not None:
            try:
                capture.release()
                result["released"] = True
            except Exception:
                result.update(status="FAILED", reason="RELEASE_FAILED")
    # 7. 성공 여부·해상도·해제 여부를 포함한 진단 딕셔너리를 반환합니다.
    return result

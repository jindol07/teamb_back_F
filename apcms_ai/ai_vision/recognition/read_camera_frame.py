# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/read_camera_frame.py

"""카메라 한 프레임의 독립 사본을 만들고 장치 해제 성공 후에만 반환합니다."""

from ai_vision.recognition.live_gate_camera_probe import probe_camera


def read_camera_frame(index, capture_factory=None):
    frames = []
    # 1. 드라이버가 배열을 재사용할 수 있으므로 장치를 닫기 전에 복사합니다.
    result = probe_camera(index, capture_factory, frame_consumer=lambda frame: frames.append(frame.copy()))
    if result["status"] != "FRAME_READ" or not result["released"] or len(frames) != 1:
        # 2. 읽기·해제 실패가 있으면 확보했던 이미지도 호출자에게 전달하지 않습니다.
        raise ValueError("카메라 프레임 확보 실패: " + result["reason"])
    return frames[0]

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/read_camera_frame.py

"""카메라 한 프레임의 독립 사본을 만들고 장치 해제 성공 후에만 반환합니다."""

# 1. 카메라 장치를 확인하고 프레임 한 장을 읽는 공용 함수
# 1-1. probe_camera()는 프레임 읽기와 장치 해제 결과를 함께 보고합니다.
from ai_vision.recognition.live_gate_camera_probe import probe_camera


# 2. 카메라 프레임 한 장을 안전하게 읽어 반환하는 함수
# 2-1. index는 카메라 번호이며 capture_factory는 테스트용 카메라 객체 생성 함수를 주입할 때 사용합니다.
# 함수 설명: read_camera_frame() — 카메라에서 한 장을 읽어 별도 메모리 복사본을 돌려줍니다. 자원 해제 실패를 성공으로 취급하지 않습니다.
def read_camera_frame(index, capture_factory=None):
    # 읽은 이미지의 독립 사본을 잠시 보관할 리스트입니다.
    frames = []
    # 2-2. probe_camera가 전달한 프레임을 즉시 copy()하여 리스트에 담습니다.
    # 카메라 드라이버가 내부 이미지 버퍼를 재사용하더라도 사본의 픽셀은 바뀌지 않습니다.
    # lambda frame: ... 은 프레임을 전달받아 복사 후 저장하는 짧은 콜백 함수입니다.
    result = probe_camera(index, capture_factory, frame_consumer=lambda frame: frames.append(frame.copy()))
    # 2-3. 프레임을 정상적으로 읽고 장치를 해제했으며 이미지가 정확히 한 장인지 검사합니다.
    # 읽기만 성공하거나 release()가 실패한 상태는 정상 완료로 취급하지 않습니다.
    if result["status"] != "FRAME_READ" or not result["released"] or len(frames) != 1:
        # 2-4. 실패하면 이미 복사한 프레임이 있어도 반환하지 않고 이유를 포함한 예외를 발생시킵니다.
        raise ValueError("카메라 프레임 확보 실패: " + result["reason"])
    # 2-5. 장치 해제까지 확인된 독립 이미지 배열을 호출자에게 전달합니다.
    return frames[0]

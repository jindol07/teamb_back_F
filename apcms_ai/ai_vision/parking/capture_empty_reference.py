# D:/finalProjectB/back/apcms_ai/ai_vision/parking/capture_empty_reference.py
import cv2
from ai_vision.camera_runtime import open_camera

from ai_vision.paths import DATA_DIR

SAVE_PATH = DATA_DIR / "parking_spaces" / "empty_reference.jpg" # 빈 주차면 기준 이미지 저장 경로


# 1. capture_empty_reference() - 빈 주차면 기준 이미지 촬영
def capture_empty_reference():

    # 기본 웹캠 연결
    # 0: 기본 웹캠, CAP_DSHOW: Windows DirectShow 사용
    cap = open_camera(0)

    if not cap.isOpened():
        cap.release()
        print("웹캠을 연결할 수 없습니다.")
        return

    try:
        frame = None

        # 카메라에서 30프레임 읽기(카메라 초기 노출 및 밝기 안정화)
        # 마지막으로 읽은 프레임을 기준 이미지로 사용
        for _ in range(30):
            ret, frame = cap.read()

            if not ret:
                print("웹캠 촬영에 실패했습니다.")
                return

        # 이미지 저장 폴더 생성
        SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)

        # 기준 이미지 저장 및 결과 출력
        if cv2.imwrite(str(SAVE_PATH), frame):
            print("빈 주차면 기준 이미지 저장 완료!")
            print("저장 위치:", SAVE_PATH)
            print("이미지 크기:", frame.shape[1], "x", frame.shape[0])
        else:
            print("이미지 저장에 실패했습니다.")

    finally:
        # 성공 또는 실패 여부와 관계없이 웹캠 해제
        cap.release()


# 프로그램 실행부
if __name__ == "__main__":
    capture_empty_reference()

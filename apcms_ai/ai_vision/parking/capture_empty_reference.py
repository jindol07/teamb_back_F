import sys
import cv2

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paths import DATA_DIR


SAVE_PATH = DATA_DIR / "parking_spaces" / "empty_reference.jpg"


def capture_empty_reference():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("웹캠을 연결할 수 없습니다.")
        return

    try:
        frame = None

        for _ in range(30):
            ret, frame = cap.read()

            if not ret:
                print("웹캠 촬영에 실패했습니다.")
                return

        SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)

        if cv2.imwrite(SAVE_PATH, frame):
            print("빈 주차면 기준 이미지 저장 완료!")
            print("저장 위치:", SAVE_PATH)
            print("이미지 크기:", frame.shape[1], "x", frame.shape[0])
        else:
            print("이미지 저장에 실패했습니다.")

    finally:
        cap.release()


if __name__ == "__main__":
    capture_empty_reference()

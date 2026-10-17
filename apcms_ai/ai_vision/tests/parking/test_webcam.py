from pathlib import Path
import cv2

BASE_DIR = Path(__file__).resolve().parents[2]

SAVE_DIR = BASE_DIR / "results" / "parking"
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# 기본 웹캠 연결
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("웹캠을 연결할 수 없습니다.")
    raise SystemExit(1)

print("웹캠 연결 성공")

# 몇 프레임을 읽어 카메라 노출을 안정화
for i in range(30):
    ret, frame = cap.read()

    if not ret:
        print("웹캠 화면을 읽지 못했습니다.")
        cap.release()
        raise SystemExit(1)

# 사진 저장
save_path = SAVE_DIR / "webcam_frame.jpg"

success = cv2.imwrite(save_path, frame)

cap.release()

if success:
    print("웹캠 이미지 저장 성공")
    print(save_path)
    print("해상도:", frame.shape[1], "x", frame.shape[0])
else:
    print("이미지 저장 실패")
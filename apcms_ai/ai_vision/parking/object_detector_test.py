# 원본 프레임 전체 탐지 실험
from pathlib import Path

import cv2
from ultralytics import YOLO

# AI 프로젝트 최상위 폴더
BASE_DIR = Path(__file__).resolve().parent.parent

# 파일 경로
MODEL_PATH = BASE_DIR / "models" / "yolo11n.pt"
VIDEO_PATH = BASE_DIR / "data" / "videos" / "parking_test.mp4"

# 결과 저장 폴더
RESULT_DIR = BASE_DIR / "results" / "parking"
RESULT_DIR.mkdir(parents=True, exist_ok=True)


# COCO 모델의 차량 관련 클래스 번호
# YOLO 모델이 인식할 수 있는 클래스는 COCO 데이터셋 기준으로 80개이며, 차량 관련 클래스 번호는 아래와 같음
# car=2, motorcycle=3, bus=5, truck=7 / 사람은 0번, 자전거는 1번, 동물은 16~23번 등
# print(MODEL_PATH.names) 이거 하면 80개 다나옴
VEHICLE_CLASSES = [2, 3, 5, 7]


def detect_objects():

    # YOLO 모델 로딩
    model = YOLO(MODEL_PATH)

    # 영상 열기
    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        print("영상을 열 수 없습니다.")
        return

    # 첫 번째 프레임 읽기
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("프레임을 읽지 못했습니다.")
        return

    # YOLO 차량 탐지
    results = model.predict(
        source=frame,
        conf=0.25,
        imgsz=1280,
        classes=VEHICLE_CLASSES,
        verbose=False
    )

    result = results[0]

    print("=== 차량 객체 탐지 결과 ===")

    counts = {
        "car": 0,
        "motorcycle": 0,
        "bus": 0,
        "truck": 0
    }

    for box in result.boxes:

        class_id = int(box.cls[0])
        confidence = float(box.conf[0])

        vehicle_type = model.names[class_id]

        counts[vehicle_type] += 1

        print(
            f"{vehicle_type} / "
            f"신뢰도: {confidence:.4f}"
        )

    print("\n=== 차량 종류별 개수 ===")

    for vehicle_type, count in counts.items():
        print(f"{vehicle_type}: {count}대")

    print(f"전체 탐지 수: {sum(counts.values())}대")

    # 탐지된 객체를 사각형으로 표시한 이미지 생성
    annotated_frame = result.plot()

    # 결과 이미지 저장
    save_path = RESULT_DIR / "detected_objects.jpg"

    cv2.imwrite(save_path, annotated_frame)

    print(f"\n결과 이미지 저장: {save_path}")


if __name__ == "__main__":
    detect_objects()

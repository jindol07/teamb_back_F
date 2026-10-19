# 12개 영역 분할 탐지 실험 (레이어를 나누어 탐지)
from pathlib import Path
from collections import Counter

import cv2
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = BASE_DIR / "models" / "yolo11n.pt"
VIDEO_PATH = BASE_DIR / "data" / "videos" / "parking_test.mp4"

RESULT_DIR = BASE_DIR / "results" / "parking"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# 분할 크기
ROWS = 3
COLS = 4

# 차량 클래스
VEHICLE_CLASSES = [2, 3, 5, 7]


def detect_objects():

    model = YOLO(MODEL_PATH)

    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        print("영상을 열 수 없습니다.")
        return

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("프레임을 읽지 못했습니다.")
        return

    height, width = frame.shape[:2]

    tile_width = width // COLS
    tile_height = height // ROWS
    
    print(f"tile_width : {tile_width}, tile_height : {tile_height}")

    # 원본 프레임 복사
    annotated = frame.copy()

    counts = Counter()

    print("=== 분할 이미지 YOLO 탐지 ===")

    for row in range(ROWS):
        for col in range(COLS):

            x1 = col * tile_width
            y1 = row * tile_height

            # 마지막 행/열까지 포함
            x2 = (col + 1) * tile_width if col < COLS - 1 else width
            y2 = (row + 1) * tile_height if row < ROWS - 1 else height

            tile = frame[y1:y2, x1:x2]

            # 이미지 조각에서 객체 탐지
            results = model.predict(
                source=tile,
                conf=0.10,
                imgsz=640,
                verbose=False
            )

            result = results[0]

            for box in result.boxes:

                class_id = int(box.cls[0])
                confidence = float(box.conf[0])

                object_type = model.names[class_id]

                counts[object_type] += 1

                # 조각 내부 좌표
                bx1, by1, bx2, by2 = map(
                    int, box.xyxy[0].tolist()
                )

                # 원본 이미지 좌표로 변환
                bx1 += x1
                by1 += y1
                bx2 += x1
                by2 += y1

                # 차량은 초록색, 나머지는 빨간색
                if class_id in VEHICLE_CLASSES:
                    color = (0, 255, 0)
                else:
                    color = (0, 0, 255)

                cv2.rectangle(
                    annotated,
                    (bx1, by1),
                    (bx2, by2),
                    color,
                    2
                )

                label = f"{object_type} {confidence:.2f}"

                cv2.putText(
                    annotated,
                    label,
                    (bx1, max(by1 - 5, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35,
                    color,
                    1
                )

            print(
                f"영역 ({row + 1}, {col + 1}) : "
                f"{len(result.boxes)}개 탐지"
            )

    print("\n=== 전체 객체 탐지 결과 ===")

    for object_type, count in counts.items():
        print(f"{object_type}: {count}개")

    vehicle_count = sum(
        counts.get(model.names[class_id], 0)
        for class_id in VEHICLE_CLASSES
    )

    print(f"\n차량 관련 탐지 수: {vehicle_count}개")
    print("※ 타일 경계의 중복 탐지는 제거하지 않은 수치입니다.")

    save_path = RESULT_DIR / "detected_objects_tiled.jpg"

    cv2.imwrite(save_path, annotated)

    print(f"\n결과 이미지 저장: {save_path}")


if __name__ == "__main__":
    detect_objects()

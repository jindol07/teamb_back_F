from ultralytics import YOLO
import cv2, os

os.makedirs("results/plates", exist_ok=True)

# 번호판 탐지 모델
model = YOLO("models/license_plate_yolov8n.pt")

# 앞 단계에서 잘라낸 차량 이미지
image_path = "results/vehicle_2.jpg"

# 번호판 탐지
results = model(image_path, conf=0.25)

image = cv2.imread(image_path)

plate_count = 0

for result in results:
    for box in result.boxes:
        plate_count += 1

        confidence = float(box.conf[0])

        x1, y1, x2, y2 = map(int, box.xyxy[0])

        print(
            f"번호판 {plate_count}: "
            f"신뢰도: {confidence:.2f}, "
            f"좌표: ({x1}, {y1}) ~ ({x2}, {y2})"
        )

        # 번호판 영역 Crop
        plate_crop = image[y1:y2, x1:x2]

        cv2.imwrite(
            f"results/plates/plate_{plate_count}.jpg",
            plate_crop
        )

    result.save(
        filename="results/plates/result_plate.jpg"
    )

print("번호판 탐지 완료")
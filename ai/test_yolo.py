from ultralytics import YOLO
import cv2, os

os.makedirs("results", exist_ok=True)

model = YOLO("models/yolo11n.pt")

image_path = "test_images/car.jpg"

results = model(image_path, conf=0.5) # conf=0.5 : 신뢰도 0.5 미만인 객체는 무시

vehicle_classes = {
    "car",
    "truck",
    "bus",
    "motorcycle"
}

# 원본 이미지 읽기
image = cv2.imread(image_path)

vehicle_count = 0

for result in results:
    for box in result.boxes:
        class_id = int(box.cls[0])
        class_name = model.names[class_id]
        confidence = float(box.conf[0])

        if class_name in vehicle_classes:
            vehicle_count += 1

            # Bounding Box 좌표
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            print(
                f"차량 {vehicle_count}: "
                f"{class_name}, "
                f"신뢰도: {confidence:.2f}, "
                f"좌표: ({x1}, {y1}) ~ ({x2}, {y2})"
            )

            # 차량 부분만 잘라내기
            crop = image[y1:y2, x1:x2]

            # 저장
            cv2.imwrite(
                f"results/vehicle_{vehicle_count}.jpg",
                crop
            )

    result.save(filename="results/result_vehicle.jpg")

print("탐지 및 차량 Crop 완료")
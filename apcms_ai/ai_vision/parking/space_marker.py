from pathlib import Path

import cv2
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent

IMAGE_PATH = BASE_DIR / "results" / "parking" / "first_frame.jpg"

# 이미지 읽기
image = cv2.imread(IMAGE_PATH)

# OpenCV는 BGR, Matplotlib은 RGB 사용
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# 이미지 표시
plt.figure(figsize=(16, 9))
plt.imshow(image)

plt.title("주차면의 네 모서리를 클릭하세요.")

# 마우스로 네 점 선택
points = plt.ginput(4, timeout=0)

plt.close()

print("선택한 좌표:")

for x, y in points:
    print(int(x), int(y))
# ai_vision/parking/space_marker.py
"""주차장 이미지에서 주차면 네 꼭짓점을 마우스로 선택하는 수동 보조 도구.

주의: 이 파일은 import 시에도 아래 실행문이 동작합니다. GUI가 필요한
Matplotlib 입력 도구이며 네 점을 직접 클릭해야 완료됩니다.
"""

# 1. 필요한 라이브러리 불러오기
# 1-1. pathlib.Path는 운영체제에 맞게 파일 경로를 조립합니다.
from pathlib import Path
# 1-2. OpenCV는 원본 이미지를 읽고 색상 채널을 변환합니다.
import cv2
# 1-3. Matplotlib은 이미지를 표시하고 클릭 위치를 입력받습니다.
import matplotlib.pyplot as plt

# 2. 사용할 이미지 경로 설정
# 2-1. 현재 스크립트의 상위 폴더(ai_vision)를 기준으로 경로를 구합니다.
BASE_DIR = Path(__file__).resolve().parent.parent
# 2-2. 주차장 첫 프레임 이미지의 위치입니다.
IMAGE_PATH = BASE_DIR / "results" / "parking" / "first_frame.jpg"

# 3. 이미지 파일 열기
# 3-1. cv2.imread는 기본적으로 BGR 채널 순서로 이미지를 불러옵니다.
image = cv2.imread(IMAGE_PATH)
# 3-2. Matplotlib은 RGB 채널 순서를 사용하므로 변환합니다.
# 원본 코드와 동일하게 읽기 실패에 대한 별도 분기는 두지 않습니다.
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# 4. 클릭을 받을 이미지 창 표시
# 4-1. 16×9인치의 그림 영역을 생성합니다.
plt.figure(figsize=(16, 9))
# 4-2. 변환된 RGB 이미지를 표시합니다.
plt.imshow(image)
# 4-3. 사용자가 해야 할 작업을 제목에 표시합니다.
plt.title("주차면의 네 모서리를 클릭하세요.")

# 5. 네 꼭짓점 좌표 수집
# 5-1. ginput(4)는 그림에서 마우스 클릭 4개를 입력받습니다.
# 5-2. timeout=0은 시간 제한 없이 사용자의 클릭을 기다립니다.
points = plt.ginput(4, timeout=0)
# 5-3. 입력을 마치면 그림 창을 닫습니다.
plt.close()

# 6. 선택한 좌표 출력
print("선택한 좌표:")
# 6-1. ginput이 반환한 실수 좌표를 정수로 바꿔 출력합니다.
# 6-2. 현재 코드는 좌표를 파일에 저장하지 않고 콘솔에만 표시합니다.
for x, y in points:
    print(int(x), int(y))

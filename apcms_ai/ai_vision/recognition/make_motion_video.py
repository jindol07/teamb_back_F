# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/make_motion_video.py
# APCMS 입출차 방향 판별용 테스트 영상 생성
# 기존 car12.png 사진을 좌우로 이동시켜
# ENTRY와 EXIT 방향 테스트에 사용할 영상 생성

import cv2
import numpy as np

from ai_vision.paths import TEST_IMAGE_DIR, RESULT_DIR


# 1. 이미지 및 영상 경로 설정

IMAGE_PATH = TEST_IMAGE_DIR / "car12.png"
SAVE_DIR = RESULT_DIR / "recognition"

# 1-1. 출력 영상 설정
WIDTH = 1280
HEIGHT = 720
FPS = 15
TOTAL_FRAMES = 90


# 2. 차량 사진 불러오기

def load_car_image():

    image = cv2.imread(str(IMAGE_PATH))

    if image is None:
        raise FileNotFoundError(
            f"차량 이미지를 읽을 수 없습니다: {IMAGE_PATH}"
        )

    # 2-1. 원본 비율을 유지하면서 영상 안에 들어갈 크기로 조정
    height, width = image.shape[:2]

    scale = min(620 / width, 500 / height, 1.0)

    new_width = int(width * scale)
    new_height = int(height * scale)

    return cv2.resize(
        image,
        (new_width, new_height),
        interpolation=cv2.INTER_AREA
    )


# 3. 차량 사진이 이동하는 영상 생성

def create_motion_video(car_image, direction, save_path):

    # 3-1. 영상 파일 생성
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    writer = cv2.VideoWriter(
        str(save_path),
        fourcc,
        FPS,
        (WIDTH, HEIGHT)
    )

    if not writer.isOpened():
        raise RuntimeError(
            f"영상 저장을 시작할 수 없습니다: {save_path}"
        )

    car_height, car_width = car_image.shape[:2]

    # 3-2. 사진이 화면 왼쪽 끝에서 오른쪽 끝까지 이동할 범위
    start_x = 0
    end_x = WIDTH - car_width

    # 세로 위치는 고정하고 가로 위치만 변경
    y = (HEIGHT - car_height) // 2

    try:
        for frame_index in range(TOTAL_FRAMES):

            # 3-3. 현재 영상 진행 비율
            progress = frame_index / (TOTAL_FRAMES - 1)

            # ENTRY : 왼쪽에서 오른쪽
            # EXIT : 오른쪽에서 왼쪽
            if direction == "ENTRY":
                x = int(start_x + (end_x - start_x) * progress)
            else:
                x = int(end_x - (end_x - start_x) * progress)

            # 3-4. 매 프레임 동일한 배경 생성
            frame = np.full(
                (HEIGHT, WIDTH, 3),
                70,
                dtype=np.uint8
            )

            # 3-5. 현재 위치에 차량 사진 배치
            frame[
                y:y + car_height,
                x:x + car_width
            ] = car_image

            # 3-6. 화면 중앙에 입출차 판단 기준선 표시
            cv2.line(
                frame,
                (WIDTH // 2, 0),
                (WIDTH // 2, HEIGHT),
                (0, 255, 255),
                2
            )

            # 3-7. 테스트 영상 방향 표시
            cv2.putText(
                frame,
                f"SIMULATION: {direction}",
                (30, 45),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2
            )

            writer.write(frame)

    finally:
        writer.release()

    print(f"{direction} 영상 생성 완료: {save_path}")


# 4. ENTRY / EXIT 영상 각각 생성

def main():

    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    car_image = load_car_image()

    create_motion_video(
        car_image,
        "ENTRY",
        SAVE_DIR / "test_entry.mp4"
    )

    create_motion_video(
        car_image,
        "EXIT",
        SAVE_DIR / "test_exit.mp4"
    )

    print("입출차 방향 테스트 영상 2개 생성 완료")


# 5. 프로그램 실행부

if __name__ == "__main__":
    main()

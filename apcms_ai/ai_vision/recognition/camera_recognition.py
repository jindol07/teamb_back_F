# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/camera_recognition.py
# APCMS 웹캠 차량번호 인식 테스트
# 0번 웹캠 영상을 확인하고 R 키를 누르면
# 현재 프레임에서 YOLO + PaddleOCR 차량번호 인식 실행

import cv2

from ai_vision.recognition.recognizer import recognize_image
from ai_vision.camera_runtime import open_camera, require_display


# 1. 웹캠 설정

# 0번 : 입출차 차량 인식용 웹캠
CAMERA_ID = 0


# 2. 인식 결과 출력

def print_recognition_result(result):

    # 2-1. 차량 인식에 실패한 경우
    if not result["success"]:
        print(f'[인식 실패] {result["message"]}')
        return

    # 2-2. 탐지된 차량 수 출력
    print(f'\n탐지된 차량 수: {result["vehicle_count"]}')

    # 2-3. 차량별 번호판 인식 결과 출력
    for vehicle in result["vehicles"]:

        print(f'\n[차량 {vehicle["vehicle_index"]}]')
        print(f'차량 종류: {vehicle["vehicle_type"]}')
        print(f'차량 탐지 신뢰도: {vehicle["vehicle_confidence"]}')
        print(f'번호판 탐지 여부: {vehicle["plate_detected"]}')
        print(f'번호판 탐지 신뢰도: {vehicle["plate_confidence"]}')
        print(f'인식 번호판: {vehicle["plate_number"]}')
        print(f'번호판 형식: {vehicle["plate_type"]}')

        # 실제 번호판 문자열을 확정하기 어려운 경우
        # 이벤트 전송 대상으로 사용하지 않도록 구분
        if vehicle["plate_type"] != "KOREAN_VALID":
            print("번호판 확정 실패 또는 추가 확인 필요")


# 3. 웹캠 차량번호 인식 실행

def run_camera_recognition():

    # 3-1. 입출차 전용 웹캠 연결
    # GUI 전용 수동 도구이므로 화면 없는 서버에서는 카메라를 열기 전에 안내합니다.
    require_display()
    cap = open_camera(CAMERA_ID)

    if not cap.isOpened():
        cap.release()
        print(f"{CAMERA_ID}번 웹캠을 연결할 수 없습니다.")
        return

    print("\n=== 웹캠 차량번호 인식 시작 ===")
    print("R 키 : 현재 화면 차량번호 인식")
    print("Q 키 : 프로그램 종료")

    try:
        # 3-2. 실시간 영상 표시
        while True:

            ret, frame = cap.read()

            if not ret:
                print("웹캠 프레임을 읽지 못했습니다.")
                break

            # 카메라 영상을 확인하는 화면
            cv2.imshow("APCMS Vehicle Recognition", frame)

            key = cv2.waitKey(1) & 0xFF

            # 3-3. Q 키를 누르면 종료
            if key == ord("q"):
                break

            # 3-4. R 키를 누르면 현재 프레임 인식
            if key == ord("r"):

                print("\n[차량번호 인식 시작]")

                # 현재 프레임을 복사하여 기존 인식 함수에 전달
                # 인식 중에는 화면 갱신이 잠시 멈출 수 있음
                captured_frame = frame.copy()

                try:
                    # 3-5. 기존 YOLO + PaddleOCR 함수 재사용
                    result = recognize_image(captured_frame)

                    # 3-6. 인식 결과 출력
                    print_recognition_result(result)

                except Exception as error:
                    print(f"[AI 인식 오류] {error}")

    except KeyboardInterrupt:
        print("\n사용자가 프로그램을 종료했습니다.")

    finally:
        # 3-7. 웹캠 및 OpenCV 창 정리
        try:
            cap.release()
        finally:
            cv2.destroyAllWindows()

        print("웹캠 차량번호 인식을 종료합니다.")


# 4. 프로그램 실행부

if __name__ == "__main__":
    run_camera_recognition()

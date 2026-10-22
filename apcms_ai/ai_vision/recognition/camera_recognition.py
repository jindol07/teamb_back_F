# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/camera_recognition.py
# APCMS 웹캠 차량번호 인식 테스트
# 0번 웹캠 영상을 확인하고 R 키를 누르면
# 현재 프레임에서 YOLO + PaddleOCR 차량번호 인식 실행

import argparse
import cv2

from ai_vision.recognition.recognizer import recognize_image
from ai_vision.camera_runtime import open_camera, require_display
from ai_vision.recognition.remote_plate_reader import RemotePlateReader


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

def run_camera_recognition(camera_index=CAMERA_ID, vision_api_url=None):

    # 3-0. 주소를 먼저 검사합니다. 원격 모드에서는 로컬 OCR 모델을 생성하지 않습니다.
    reader = RemotePlateReader(vision_api_url) if vision_api_url is not None else None

    # 3-1. 입출차 전용 웹캠 연결
    # GUI 전용 수동 도구이므로 화면 없는 서버에서는 카메라를 열기 전에 안내합니다.
    require_display()
    cap = open_camera(camera_index)

    if not cap.isOpened():
        cap.release()
        print(f"{camera_index}번 웹캠을 연결할 수 없습니다.")
        return

    print("\n=== 웹캠 차량번호 인식 시작 ===")
    print("R 키 : 현재 화면 차량번호 인식")
    print("Q 키 : 프로그램 종료")
    print("원격 인식" if reader is not None else "로컬 인식")
    print("사진 재촬영은 연결 확인용입니다. 입출차 전송·사진 저장은 하지 않습니다.")

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
                    if reader is None:
                        result = recognize_image(captured_frame)
                        print_recognition_result(result)
                    else:
                        # 3-6. 차량 한 대가 보이도록 촬영합니다. 여러 차량 응답은 판독기가 차단합니다.
                        sample = reader.read(captured_frame)
                        print(f'인식 번호판: {sample["plate_number"]}')
                        print(f'번호판 형식: {sample["plate_type"]}')
                        print(f'보류 사유: {sample["review_reasons"]}')
                    print("형식 통과만으로 정확한 번호라고 판단하지 말고 원본 번호판과 비교하세요.")

                except Exception as error:
                    # 서버 주소 등이 포함될 수 있는 예외 원문은 화면에 노출하지 않습니다.
                    print(f"[AI 인식 오류] {type(error).__name__}")

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

def main(argv=None):
    # 4-1. 기존 기본 실행은 유지하고 AWS 연결 시험을 선택할 수 있게 합니다.
    parser = argparse.ArgumentParser(description="웹캠 수동 인식 확인: R 인식, Q 종료. 입출차 전송 없음")
    parser.add_argument("--camera-index", type=int, default=CAMERA_ID)
    parser.add_argument("--vision-api-url", help="SSH 터널 등으로 연결한 Vision API 주소")
    args = parser.parse_args(argv)
    if args.camera_index < 0:
        parser.error("카메라 번호는 0 이상으로 지정하세요.")
    run_camera_recognition(args.camera_index, args.vision_api_url)


if __name__ == "__main__":
    main()

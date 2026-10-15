from pathlib import Path
import cv2

# AI 프로젝트 최상위 폴더
BASE_DIR = Path(__file__).resolve().parents[2]

# 테스트 영상 경로
VIDEO_PATH = BASE_DIR / "data" / "videos" / "parking_test.mp4"

# 결과 저장 경로
RESULT_DIR = BASE_DIR / "results" / "parking"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":

    # 영상 파일 존재 여부 확인
    if not VIDEO_PATH.exists():
        print("영상 파일이 없습니다.")
        print(VIDEO_PATH)
        raise SystemExit(1)

    # 영상 열기
    # cv2.VideoCapture() : OpenCV에서 영상 파일을 열고, 프레임 단위로 읽을 수 있는 객체를 생성하는 함수
    cap = cv2.VideoCapture(str(VIDEO_PATH)) 

    if not cap.isOpened():
        print("영상을 열 수 없습니다.")
        raise SystemExit(1)

    # 영상 정보
    fps = cap.get(cv2.CAP_PROP_FPS) # cv2.CAP_PROP_FPS : 1초당 프레임 수
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) # cv2.CAP_PROP_FRAME_COUNT : 총 프레임 수
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) # cv2.CAP_PROP_FRAME_WIDTH : 프레임 너비
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) # cv2.CAP_PROP_FRAME_HEIGHT : 프레임 높이

    print("=== 주차장 영상 정보 ===")
    print(f"FPS: {fps}")
    print(f"총 프레임: {frame_count}")
    print(f"영상 크기: {width} x {height}")

    # 첫 번째 프레임 읽기
    ret, frame = cap.read() # cap.read() : 영상에서 프레임 한 장을 가져옴
    # ret : 읽기 성공 여부 (True/False)
    # frame : 읽은 프레임 이미지 데이터 (numpy 배열)

    if ret:
        # 첫 프레임 저장
        save_path = RESULT_DIR/"first_frame.jpg"
        cv2.imwrite(str(save_path), frame)

        print("첫 번째 프레임 저장 완료")
        print(save_path)
    else:
        print("첫 번째 프레임을 읽지 못했습니다.")

    cap.release()
    
    print("영상 처리 완료")

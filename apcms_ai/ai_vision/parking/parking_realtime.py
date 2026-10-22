# D:/finalProjectB/back/apcms_ai/ai_vision/parking/parking_realtime.py
# APCMS 실시간 주차면 점유 감지
# 빈 주차면 기준 사진과 실시간 웹캠 영상을 비교하여
# 주차면별 점유 상태를 독립적으로 판단하는 프로그램

# 1. 기준 이미지 및 주차면 좌표 불러오기
# 2. 주차면별 분석 마스크 생성
# 3. 웹캠에서 현재 프레임 읽기
# 4. 기준 이미지와 현재 이미지의 픽셀 차이 분석
# 5. 같은 상태가 5회 연속 감지되면 확정
# 6. 이후 실행·전송은 run_parking_camera에 위임
# 7. 모든 주차면 상태가 확정되면 결과 이미지와 JSON 저장
# 8. 카메라 실행과 전송 정책은 run_parking_camera에서 공통 관리

# 자동차를 직접 인식하는 YOLO 방식이 아니라 기준 이미지 대비 픽셀 변화율로 점유 상태를 판단함

import cv2

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.parking.parking_validation import validate_occupancy




# 1. 경로 및 설정값

# 1-3. 결과 이미지와 JSON을 저장할 폴더
SAVE_DIR = RESULT_DIR / "parking"

IMAGE_PATH = SAVE_DIR / "realtime_occupancy_result.jpg" # 결과 이미지
OUTPUT_PATH = SAVE_DIR / "realtime_occupancy_result.json" # JSON

# 1-4. 픽셀 변화 감지 임계값
# 기준 이미지와 현재 이미지 사이의 픽셀 밝기 차이가 35보다 크면 변화가 발생한 픽셀로 인정
PIXEL_THRESHOLD = 35

# 1-5. 주차면 점유 판단 임계값
# 주차면 내부 픽셀 중 5% 이상이 변하면 OCCUPIED
OCCUPANCY_THRESHOLD = 0.05

# 2. detect_spaces() - 현재 프레임의 점유 상태 분석

def detect_spaces(reference_gray, frame, spaces):

    # 2-1. 현재 웹캠 프레임 전처리

    # BGR 컬러 이미지를 흑백 이미지로 변환
    current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # GaussianBlur() : 주변 픽셀을 부드럽게 만들어 작은 노이즈 감소
    current_gray = cv2.GaussianBlur(
        current_gray,
        (5, 5),
        0
    )

    # 2-2. 기준 이미지와 현재 이미지 비교

    # absdiff() : 두 이미지의 같은 위치에 있는 픽셀값 차이 계산
    difference = cv2.absdiff(
        reference_gray,
        current_gray
    )

    # threshold() : 밝기 차이가 PIXEL_THRESHOLD보다 크면 255, 그렇지 않으면 0으로 변환
    # 예 : 기준 픽셀 = 200, 현재 픽셀 = 150 일 때 차이 : 50 -> 변화한 픽셀로 판단
    _, changed = cv2.threshold(
        difference,
        PIXEL_THRESHOLD,
        255,
        cv2.THRESH_BINARY
    )

    # 2-3. 주차면별 변화율 계산

    results = []

    for space in spaces:

        # 해당 주차면 내부만 흰색으로 표시한 마스크
        mask = space["mask"]

        # bitwise_and() : 전체 이미지 중 해당 주차면의 변화만 추출
        changed_in_space = cv2.bitwise_and(
            changed,
            changed,
            mask=mask
        )

        # 주차면 전체 픽셀 개수
        total_pixels = cv2.countNonZero(mask)

        # 실제 변화한 픽셀 개수
        changed_pixels = cv2.countNonZero(
            changed_in_space
        )

        # 주차면 마스크가 비어 있다면 계산할 수 없음
        if total_pixels == 0:
            raise ValueError(
                f'{space["id"]}: 주차면 마스크가 비어 있습니다.'
            )

        # 2-4. 주차면 내부의 픽셀 변화율 계산
        # ex) 10,000픽셀 중 600픽셀이 변경됐다면
        # change_ratio = 600 / 10000 = 0.06 (6%)
        change_ratio = changed_pixels / total_pixels

        # 2-5. 현재 순간의 점유 상태 판정

        if change_ratio >= OCCUPANCY_THRESHOLD:
            status = "OCCUPIED"
        else:
            status = "EMPTY"

        # 분석한 주차면의 결과를 리스트에 추가
        results.append({
            "space_id": space["id"],
            "status": status,
            "change_ratio": round(change_ratio, 4)
        })

    # 이 결과는 아직 확정된 상태가 아니라 현재 프레임 한 장에서 판단한 임시 상태임
    return results


# 3. save_results() - 확정된 점유 상태 저장

def save_results(frame, spaces, results):

    # 3-1. 결과 저장 폴더 생성

    SAVE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # 3-2. 결과 이미지 생성

    # copy() : 원본 웹캠 프레임을 변경하지 않고 복사
    annotated = frame.copy()

    # zip() : spaces와 results의 같은 위치 요소를 함께 처리
    for space, result in zip(spaces, results):

        # 점유 중이면 빨간색, 비어 있으면 초록색 (BGR)
        if result["status"] == "OCCUPIED":
            color = (0, 0, 255) # 빨간색
        else:
            color = (0, 255, 0) # 초록색

        # 주차면 다각형 좌표
        points = space["points"]

        # polylines() : 주차면 테두리를 결과 이미지에 표시
        cv2.polylines(
            annotated,
            [points],
            True,
            color,
            2
        )

        # 첫 번째 좌표를 텍스트 표시 기준으로 사용
        x, y = points[0]

        # putText() : 주차면 ID와 확정된 상태를 이미지에 표시
        cv2.putText(
            annotated,
            f'{space["id"]}: {result["status"]}',
            (int(x), max(int(y) - 10, 15)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1
        )

    # 3-3. 전체 주차면 현황 계산

    # OCCUPIED 상태인 주차면의 개수
    occupied_count = sum(1 for result in results if result["status"] == "OCCUPIED")

    # 기존 JSON 응답 구조를 그대로 유지
    # parking_api.py에서 이 데이터를 조회함
    output = {
        "total_spaces": len(results),
        "occupied_count": occupied_count,
        "empty_count": len(results) - occupied_count,
        "spaces": results
    }

    # 3-4. 결과 이미지 저장

    # 한글 경로에서도 바이트로 저장하고, 실패하면 JSON만 성공한 것처럼 갱신하지 않습니다.
    saved, encoded = cv2.imencode('.jpg', annotated)
    if not saved:
        raise OSError('결과 이미지를 인코딩하지 못했습니다.')
    IMAGE_PATH.write_bytes(encoded.tobytes())
    print('결과 이미지 저장 성공')

    # 3-5. 결과 JSON 파일 저장

    # with open() : 파일 사용이 끝나면 자동으로 닫음
    # "w": 쓰기 모드이므로 기존 파일을 덮어씀
    # API가 읽는 중에도 반쪽짜리 JSON을 보지 않도록 같은 폴더에서 원자적으로 교체합니다.
    write_json_atomic(OUTPUT_PATH, validate_occupancy(output))

    print("결과 JSON 저장 완료")


# 4. 이전 실행 이름도 공식 실행부를 사용하여 카메라 루프를 한 곳에서 관리합니다.
def run_realtime(argv=None):
    from ai_vision.parking.run_parking_camera import main
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(run_realtime())

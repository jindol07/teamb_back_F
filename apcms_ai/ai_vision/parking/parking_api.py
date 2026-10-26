# D:/finalProjectB/back/apcms_ai/ai_vision/parking/parking_api.py
# APCMS 실시간 주차면 점유 현황 조회 API
# parking_realtime.py가 저장한 JSON 파일을 읽어서 React 또는 Spring Boot의 요청에 응답하는 기능

# 실제 주차면 분석을 수행하는 파일은 아니고 이미 저장된 최신 결과를 조회하는 역할

import json
import uvicorn
import time

from fastapi import APIRouter, FastAPI, HTTPException, Response

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import read_json
from ai_vision.parking.parking_validation import validate_occupancy


# 1. FastAPI 라우터 및 조회 파일 경로 설정

# 1-1. 주차면 API 라우터 생성
router = APIRouter(
    prefix="/parking", # /parking 경로 설정
    tags=["Parking"] # /docs에서 Parking 그룹으로 표시
)

# 1-2. 실시간 주차면 감지 결과 JSON 파일
# parking_realtime.py의 save_results()가 생성
RESULT_PATH = RESULT_DIR / "parking" / "realtime_occupancy_result.json"
MAX_RESULT_AGE_SECONDS = 30


# 2. get_parking_occupancy() - 주차면 점유 현황 조회

# 2-1. GET 요청 등록
# /parking/occupancy
@router.get("/occupancy")
def get_parking_occupancy(response: Response = None):

    # 2-2. 결과 파일 존재 여부 확인
    # 아직 실시간 감지를 실행하지 않았다면 JSON 파일이 없을 수 있음

    # 2-3. 결과 JSON 파일 읽기
    try:
        # 파일 교체 전 시각을 사용하여 오래된 데이터에 새 파일 시각을 붙이지 않습니다.
        modified = RESULT_PATH.stat().st_mtime
        # 크기·중복 키·NaN·인코딩 오류를 응답 직렬화 전에 검사합니다.
        data = validate_occupancy(read_json(RESULT_PATH))
        # 수집 중단과 큰 시계 역행을 정상적인 현재 관찰로 표시하지 않습니다.
        if not -5 <= time.time() - modified <= MAX_RESULT_AGE_SECONDS:
            raise ValueError('주차면 관찰 결과의 유효시간이 지났습니다.')

    # 2-4. 파일 읽기 또는 JSON 해석 실패 처리
    # OSError : 파일 접근 또는 읽기 관련 오류
    # JSONDecodeError : JSON 형식이 올바르지 않아 해석할 수 없는 경우
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="주차면 점유 결과가 없거나 손상되었거나 최신 상태가 아닙니다.",
            headers={'Cache-Control': 'no-store'}
        ) from error

    # 2-5. 조회 결과 반환
    # FastAPI가 Python 딕셔너리를 JSON으로 변환해 응답
    if response is not None:
        response.headers['Cache-Control'] = 'no-store'
    return data


# 3. 독립 실행용 FastAPI 앱 생성

# 3-1. 통합 서버와 별개로 주차면 API만 테스트할 때 사용
# 통합 서버에서는 ai_vision/main.py가 router를 가져가므로 여기서 별도로 만든 app이 중복 실행되지 않음
app = FastAPI(
    title="APCMS Parking API",
    version="1.0.0"
)

# 3-2. 주차면 조회 라우터 등록
app.include_router(router)


# 4. 프로그램 직접 실행 시 독립 서버 시작

# 4-1. 다른 Python 파일에서 import할 때는 실행하지 않음
if __name__ == "__main__":

    # 4-2. 주차면 조회 API 독립 테스트
    # 127.0.0.1: 자기 PC에서만 접근
    # 8001: 주차면 테스트 서버 포트
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8001
    )

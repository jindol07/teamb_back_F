# APCMS 실시간 주차면 점유 현황 조회 API
# parking_realtime.py가 저장한 JSON 파일을 읽어서 React 또는 Spring Boot의 요청에 응답하는 기능

# 실제 주차면 분석을 수행하는 파일은 아니고 이미 저장된 최신 결과를 조회하는 역할

import json
import uvicorn

from fastapi import APIRouter, FastAPI, HTTPException

from ai_vision.paths import RESULT_DIR


# 1. FastAPI 라우터 및 조회 파일 경로 설정

# 1-1. 주차면 API 라우터 생성
router = APIRouter(
    prefix="/parking", # /parking 경로 설정
    tags=["Parking"] # /docs에서 Parking 그룹으로 표시
)

# 1-2. 실시간 주차면 감지 결과 JSON 파일
# parking_realtime.py의 save_results()가 생성
RESULT_PATH = RESULT_DIR / "parking" / "realtime_occupancy_result.json"


# 2. get_parking_occupancy() - 주차면 점유 현황 조회

# 2-1. GET 요청 등록
# /parking/occupancy
@router.get("/occupancy")
def get_parking_occupancy():

    # 2-2. 결과 파일 존재 여부 확인
    # 아직 실시간 감지를 실행하지 않았다면 JSON 파일이 없을 수 있음
    if not RESULT_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="주차면 점유 감지 결과가 아직 없습니다."
        )

    # 2-3. 결과 JSON 파일 읽기
    try:
        with open(RESULT_PATH, "r", encoding="utf-8") as file:
            data = json.load(file) #  JSON 파일 내용을 Python 딕셔너리로 변환

    # 2-4. 파일 읽기 또는 JSON 해석 실패 처리
    # OSError : 파일 접근 또는 읽기 관련 오류
    # JSONDecodeError : JSON 형식이 올바르지 않아 해석할 수 없는 경우
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=503,
            detail="주차면 점유 감지 결과를 읽을 수 없습니다."
        ) from error

    # 2-5. 조회 결과 반환
    # FastAPI가 Python 딕셔너리를 JSON으로 변환해 응답
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
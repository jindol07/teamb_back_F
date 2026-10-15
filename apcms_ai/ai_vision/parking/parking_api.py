# 실시간 주차면 점유 감지 결과를 조회하는 FastAPI
# parking_realtime.py가 저장한 JSON 파일을 읽어서 반환

import json
import sys
import uvicorn

from fastapi import APIRouter, FastAPI, HTTPException

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paths import RESULT_DIR


# 1. API 및 파일 경로 설정

router = APIRouter(prefix="/parking", tags=["Parking"])

RESULT_PATH = RESULT_DIR / "parking" / "realtime_occupancy_result.json"


# 2. get_parking_occupancy() - 주차면 점유 현황 조회

# 2-1. GET /parking/occupancy 요청 처리
@router.get("/occupancy")
def get_parking_occupancy():

    # 2-2. 결과 JSON 파일 존재 여부 확인
    if not RESULT_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="주차면 점유 감지 결과가 아직 없습니다."
        )

    # 2-3. JSON 파일 읽기
    try:
        with open(RESULT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

    except (OSError, json.JSONDecodeError):
        raise HTTPException(
            status_code=503,
            detail="주차면 점유 감지 결과를 읽을 수 없습니다."
        )

    # 2-4. JSON 데이터를 API 응답으로 반환
    return data


# 3. FastAPI 앱 생성 및 라우터 등록

app = FastAPI(title="APCMS Parking API")
app.include_router(router)


# 4. 프로그램 실행부

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/results_api.py

"""모델 실행·카메라 접근·송신 없이 저장된 Vision 결과만 조회하는 API."""

from fastapi import APIRouter, FastAPI, HTTPException, Path, Query

from ai_vision.recognition.results_catalog import ResultCatalog


def create_router(catalog=None):
    # 1. 결과 위치는 서버 코드가 결정합니다. 요청에서 임의 파일 경로를 받지 않음
    catalog = catalog if catalog is not None else ResultCatalog()
    router = APIRouter(prefix="/vision/runs", tags=["Vision Results"])

    def read_result(operation):
        try:
            return operation()
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail="요청한 결과가 없습니다.") from error
        except (OSError, ValueError, KeyError, TypeError) as error:
            # 2. 손상된 결과나 로컬 절대 경로를 외부 오류 메시지로 노출하지 않음
            raise HTTPException(status_code=503, detail="결과를 읽을 수 없거나 검증이 필요합니다.") from error

    @router.get("")
    def list_runs(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        return read_result(lambda: catalog.list_runs(offset, limit))

    @router.get("/{run_id}")
    def get_run(run_id: str = Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")):
        return read_result(lambda: catalog.overview(run_id))

    @router.get("/{run_id}/passages")
    def get_passages(run_id: str = Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$"),
                     offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        return read_result(lambda: catalog.passages(run_id, offset, limit))

    return router


# 3. 기존 통합 AI 서버에서는 router만 등록하고, 독립 검증 시 app을 사용합니다.
router = create_router()
app = FastAPI(title="APCMS 저장된 Vision 결과 조회")
app.include_router(router)

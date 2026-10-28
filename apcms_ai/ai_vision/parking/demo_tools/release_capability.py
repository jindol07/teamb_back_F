"""실제 해제 이벤트를 보내지 않고 배포 API의 해제 기능 활성 여부를 확인합니다."""
import requests
from ai_vision.parking.parking_event_sender import _build_event_urls, _configured_api_key
from ai_vision.parking.demo_tools.deployed_outcome import FixtureFailure


def require_release_enabled(context_url, environment, *, session_factory=None):
    key=_configured_api_key(environment)
    if not key:raise FixtureFailure('RELEASE_CHECK_FAILED')
    url=_build_event_urls(context_url)['VEHICLE_SPACE_MATCH'].rsplit('/',1)[0]+'/space-release-events'
    session=(session_factory or requests.Session)();session.trust_env=False
    try:
        # UUID·차량·이용·구획이 없으므로 검증을 통과하거나 DB를 갱신할 수 없는 요청입니다.
        response=session.post(url,json={'event_type':'INVALID_CAPABILITY_CHECK_ONLY'},
                              headers={'X-AI-API-Key':key},timeout=(3,5),allow_redirects=False)
        try:status=response.status_code
        finally:response.close()
    except requests.RequestException as error:
        raise FixtureFailure('RELEASE_CHECK_FAILED') from error
    finally:session.close()
    if status==503:raise FixtureFailure('SPACE_RELEASE_DISABLED')
    if status!=400:raise FixtureFailure('RELEASE_CHECK_FAILED')
    return {'status':'ENABLED_VALIDATION_REACHED','http_status':400,'db_mutation':False}


def main():
    import os
    from pathlib import Path
    from dotenv import dotenv_values
    environment={**dotenv_values(Path(__file__).resolve().parents[3]/'.env',encoding='utf-8-sig',interpolate=False),**os.environ}
    try:
        result=require_release_enabled('http://52.79.133.132:3000/admin-api',environment)
        print('RELEASE_CAPABILITY: '+result['status']+' / 카메라·DB 변경 없음')
        return 0
    except FixtureFailure as error:
        print('RELEASE_CAPABILITY: '+error.code+' / '+str(error))
        return 2


if __name__=='__main__':raise SystemExit(main())

"""공유 화재 송신은 별도 명시 설정과 시험 승인 조건에서만 활성화합니다."""
from ai_vision.safety.fire_alert_sender import validate_endpoint


def load_shared_delivery(environment):
    raw=environment.get('SAFETY_SHARED_SEND_ENABLED','false').lower()
    if raw not in ('true','false','1','0'):raise ValueError('공유 화재 송신 설정은 true/false입니다.')
    if raw in ('false','0'):return None
    if environment.get('SAFETY_SHARED_ALLOW_TEST','false').lower() not in ('true','1'):
        raise ValueError('공유 화재 시험 전송을 별도로 허용해야 합니다.')
    role=environment.get('SAFETY_SHARED_SEND_ROLE','gate')
    if role not in ('gate','parking','both'):raise ValueError('공유 화재 송신 역할이 올바르지 않습니다.')
    url=environment.get('SAFETY_SHARED_ALERT_URL','').strip()
    if not url:raise ValueError('공유 화재 수신 주소가 필요합니다.')
    validate_endpoint(url)
    token=environment.get('FIRE_ALERT_TOKEN','')
    if not token or any(c in token for c in ('\r','\n')):raise ValueError('공유 화재 인증 설정이 필요합니다.')
    return dict(role=role,url=url,token=token)

"""두 창 공유 감시 실행 전 설정만 검증합니다. 카메라·추론·HTTP는 실행하지 않습니다."""
import json,os
from ai_vision.parking.parking_runtime_config import load_runtime_config
from ai_vision.recognition.model_files import require_model_file
from ai_vision.safety.fire_smoke_detector import MODEL_PATH


def check_deployed_monitor(environment):
    """1. 일반 서버의 실제 송신 계약만 검사합니다. 시험 행·HTTP·카메라는 만들지 않습니다."""
    from ai_vision.safety.shared_delivery_config import load_shared_delivery
    if environment.get('SAFETY_SHARED_AUTOSTART','false').lower() not in ('true','1'):
        raise ValueError('화재 송신뿐 아니라 공유 화재 자동 시작도 활성화해야 합니다.')
    if environment.get('SAFETY_CAMERA_AUTOSTART','true').lower() not in ('false','0','no','off'):
        raise ValueError('공유 감시에서는 화재의 직접 카메라 자동 실행을 꺼야 합니다.')
    config=load_runtime_config(environment,check_safety=True)
    if config is None or not config.get('delivery_enabled'):
        raise ValueError('배포 연동 서버에는 주차 실제 전송 설정이 필요합니다.')
    if not config.get('enable_space_release_http'):
        raise ValueError('차량 이동 반영에는 구획 연결 해제 전송이 필요합니다.')
    if not config.get('preview') or not config.get('frame_export_dir'):
        raise ValueError('현재 로컬 연동에는 두 카메라 미리보기와 공유 프레임 설정이 필요합니다.')
    mapping=config.get('space_code_map')
    if not mapping or set(config['allowed_codes'])!=set(mapping.values()):
        raise ValueError('매핑된 모든 구획을 실제 전송 허용 목록에 포함해야 합니다.')
    delivery=load_shared_delivery(environment)
    if not delivery or delivery['role']!='both':
        raise ValueError('배포 연동 서버에는 A/B 양쪽 화재 전송이 필요합니다.')
    expected=config['boot_context_url'].rstrip('/')+'/api/parking/ai/fire-alerts'
    if delivery['url']!=expected:
        raise ValueError('주차와 화재의 배포 관리자 API 대상이 다릅니다.')
    for name in ('yolo11n.pt','license_plate_yolov8n.pt','fire_smoke.pt'):
        require_model_file(MODEL_PATH.parent/name)
    return {'status':'CONFIGURED_FOR_DEPLOYED_DELIVERY',
            'gate_camera':config['gate_camera'],'parking_camera':config['parking_camera'],
            'parking_http_enabled':True,'space_release_enabled':True,
            'fire_http_enabled':True,'fire_send_role':'both','fire_records_are_test':True,
            'identity_mode':'SINGLE_VEHICLE_GATE_HANDOFF',
            'scope':'SETTINGS_ONLY_NOT_DELIVERY_ACK'}


def check_monitor(environment):
    config=load_runtime_config(environment,check_safety=True)
    if config is None or not config.get('frame_export_dir'):
        raise ValueError('활성 주차 설정과 공유 프레임 경로가 필요합니다.')
    if config.get('delivery_enabled'):
        raise ValueError('이 실행기는 관찰 전용입니다. 주차 delivery_enabled=false를 사용하세요.')
    if environment.get('SAFETY_SHARED_SEND_ENABLED','false').lower() not in ('false','0'):
        raise ValueError('이 실행기는 실제 화재 전송을 허용하지 않습니다.')
    for name in ('yolo11n.pt','license_plate_yolov8n.pt'):
        require_model_file(MODEL_PATH.parent/name)
    require_model_file(MODEL_PATH)
    return {'status':'READY_FOR_LOCAL_OBSERVATION','gate_camera':config['gate_camera'],
            'parking_camera':config['parking_camera'],'preview':config.get('preview',False),
            'shared_frame_fps':config.get('frame_export_fps',2),'http_enabled':False,
            'scope':'FILES_AND_SETTINGS_ONLY_NOT_CAMERA_TEST'}


def main():
    print(json.dumps(check_monitor(os.environ),ensure_ascii=False))


if __name__=='__main__':main()

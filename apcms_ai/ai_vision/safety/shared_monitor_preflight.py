"""두 창 공유 감시 실행 전 설정만 검증합니다. 카메라·추론·HTTP는 실행하지 않습니다."""
import json,os
from ai_vision.parking.parking_runtime_config import load_runtime_config
from ai_vision.recognition.model_files import require_model_file
from ai_vision.safety.fire_smoke_detector import MODEL_PATH


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

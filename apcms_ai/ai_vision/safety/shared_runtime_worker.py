"""서버가 소유한 공유 화재 작업. 물리 카메라는 사용하지 않으며 송신은 별도 명시 설정에서만 허용합니다."""
from pathlib import Path
import threading


def run_shared_worker(role, camera_id, shared_dir, output_dir, show, stop_event, delivery=None):
    from ai_vision.parking.parking_process_scope import isolate_worker
    from ai_vision.safety.live_fire_smoke import LiveConfig, run_live
    from ai_vision.safety.shared_alert_loop import process_alerts
    isolate_worker()
    output=Path(output_dir)
    alert_stop=threading.Event();errors=[]
    def publish(frame,detections,meta):
        from ai_vision.safety.preview_overlay import publish_overlay
        if not isinstance(meta,dict):raise RuntimeError('공유 분석 시각 정보 누락')
        publish_overlay(output/'preview_overlay.json',frame,detections,role=role,camera_id=camera_id,
                        run_id=Path(shared_dir).name,captured_monotonic=meta['captured_monotonic'])
    thread=threading.Thread(target=process_alerts,args=(output,alert_stop,errors,delivery),daemon=True)
    thread.start()
    try:
        result=run_live(LiveConfig(shared_run_dir=Path(shared_dir),shared_role=role,
            shared_camera_id=camera_id,output_dir=output,show=False,max_seconds=0,
            fire_conf=.3,smoke_conf=.3,save_evidence=True,publish_alert_session=True),stop_event=stop_event,on_detections=publish)
        if result['status']!='STOP_REQUESTED':
            raise RuntimeError('공유 화재 관찰이 종료됐습니다: '+result['status'])
    finally:
        alert_stop.set();thread.join(timeout=15)
    if thread.is_alive() or errors:raise RuntimeError('알림 작업 미전송 또는 정리 실패')

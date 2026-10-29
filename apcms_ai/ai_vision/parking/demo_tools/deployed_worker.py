"""통합 시험에서만 두 창의 제목에 현재 단계를 표시합니다. 분석 원본은 그대로입니다."""
from pathlib import Path


def run_worker(role, config, run_dir, stop_event, heartbeat):
    from ai_vision.parking.parking_process_scope import isolate_worker
    isolate_worker()
    import cv2
    from ai_vision.parking.parking_runtime_worker import run_worker as native
    original=cv2.imshow
    windows=set()
    phase_path=Path(config['output_dir']).parent/'phase.txt'
    acknowledge=lambda:None
    def show(name, image):
        if name not in windows:
            cv2.namedWindow(name,cv2.WINDOW_NORMAL)
            cv2.resizeWindow(name,640,480)
            cv2.moveWindow(name,10 if role=='gate' else 660,40)
            windows.add(name)
        original(name,image)
        try:label=phase_path.read_text(encoding='utf-8').split(' / ',1)[0]
        except OSError:label='PREPARING'
        if 'FREE_PARKING' in label:
            label+=' / ACTUAL POSITION / RESERVED A01'
        cv2.setWindowTitle(name,('A GATE' if role=='gate' else 'B PARKING')+' / '+label)
        if role=='gate':acknowledge()
    cv2.imshow=show
    from ai_vision.parking.demo_tools.deployed_delivery_gate import parking_delivery_gate
    import os
    from ai_vision.recognition.vehicle_delivery_flow import SpaceMatchDeliveryFlow
    original_flow_init=SpaceMatchDeliveryFlow.__init__
    def flow_init(self,*args,**kwargs):
        kwargs['allow_unreserved_move']=os.environ.get('DEPLOYED_DEMO_NO_RESERVATION')=='1'
        original_flow_init(self,*args,**kwargs)
    SpaceMatchDeliveryFlow.__init__=flow_init
    try:
        with parking_delivery_gate(phase_path.parent) as acknowledge:
            return native(role,config,run_dir,stop_event,heartbeat)
    finally:
        cv2.imshow=original
        SpaceMatchDeliveryFlow.__init__=original_flow_init

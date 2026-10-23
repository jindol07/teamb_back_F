from pathlib import Path
import cv2,time,os

def main():
    from ai_vision.parking.demo_session import load_demo_profile
    profile=load_demo_profile(os.environ['PARKING_DEMO_PROFILE_DIR'])
    from dotenv import dotenv_values
    from ai_vision.parking import run_parking_camera as camera
    from ai_vision.parking.parking_preview import ParkingPreview
    from ai_vision.parking import parking_event_sender as sender
    original_preview_init=ParkingPreview.__init__
    def preview_init(self,*args,**kwargs):
        original_preview_init(self,*args,**kwargs)
        cv2.namedWindow(self.name,cv2.WINDOW_NORMAL);cv2.resizeWindow(self.name,600,480);cv2.moveWindow(self.name,640,60)
    ParkingPreview.__init__=preview_init
    root=Path(os.environ['PARKING_DEMO_RUN_DIR']);layout=profile['root'];out=root/'parking'
    # 이번 프로세스에서만 종이 A-01을 합성 시험 구획으로 연결합니다.
    sender.SPACE_CODE_MAP['A-01']='999F-Z01'
    settings=dotenv_values('apcms_ai/.env',encoding='utf-8-sig',interpolate=False)
    key=settings.get('AI_OCCUPANCY_API_KEY');assert key,'AI key missing'
    env={'PARKING_AI_BASE_URL':profile['boot_context_url'],'PARKING_AI_API_KEY':key,'AI_OCCUPANCY_API_KEY':key}
    original_show=ParkingPreview.show
    def show(self,frame,*args,**kwargs):
        try:
            if (root/'fixture_ready.flag').exists():self.source_label=(root/'phase.txt').read_text(encoding='utf-8')
        except OSError:pass
        return original_show(self,frame,*args,**kwargs)
    ParkingPreview.show=show
    native=camera.open_camera;state={'cap':None,'frame':None}
    class Capture:
        def __init__(self,native):self.native=native
        def read(self):
            if (root/'stop_requested.flag').exists():raise RuntimeError('SAFETY_ABORT_REQUESTED')
            ok,frame=self.native.read()
            if ok:state['frame']=frame.copy()
            return ok,frame
        def release(self):self.native.release()
        def __getattr__(self,k):return getattr(self.native,k)
    def capture(index,backend='default'):
        if index!=profile['parking_camera']:raise ValueError('Unexpected parking camera index')
        state['cap']=Capture(native(index,backend=backend));return state['cap']
    camera.open_camera=capture
    original_ready=ParkingPreview.wait_until_ready
    def empty_start(self,capture,check_ready=None):
        if original_ready(self,capture) is None:return None
        (root/'parking_started.flag').write_text('SPACE_PRESSED',encoding='utf-8')
        from ai_vision.parking.parking_processor import ParkingOccupancyProcessor
        from ai_vision.parking.parking_realtime import detect_spaces
        reference=cv2.imread(str(profile['reference']))
        processor=ParkingOccupancyProcessor(reference,self.config,detect_spaces,emit_events=False)
        started=time.monotonic()
        while True:
            ok,frame=capture.read()
            if not ok:raise RuntimeError('Empty preflight camera read failed')
            processor.process(frame,time.monotonic()-started)
            self.source_label='EMPTY CHECK / NO HTTP YET / Q: cancel'
            occupancy=processor.occupancy()
            if occupancy is not None and occupancy['empty_count']!=occupancy['total_spaces']:
                self.source_label='NOT EMPTY / CHECK PAPER, HANDS AND LIGHT / Q: CANCEL'
            if self.show(frame)==ord('q'):return None
            if occupancy is not None:
                if occupancy['empty_count']!=occupancy['total_spaces']:
                    # 빈 기준 불일치는 예외 종료하지 않고 미리보기에서 재확인을 기다립니다.
                    continue
                (root/'parking_ready.flag').write_text('EMPTY_PREFLIGHT_PASSED',encoding='utf-8')
                self.source_label='B READY / WAIT FOR BOTH START BUTTONS'
                while not (root/'fixture_ready.flag').exists():
                    ok,frame=capture.read()
                    if not ok:raise RuntimeError('B preparation camera read failed')
                    if self.show(frame)==ord('q'):return None
                return frame
    ParkingPreview.wait_until_ready=empty_start
    try:
        report=camera.run_camera(Path(str(profile['reference'])),profile['spaces_config'],out,camera_index=profile['parking_camera'],seconds=profile['seconds'],preview=True,
                camera_backend='msmf',track_vehicles=True,tracking_target='plate',camera_id=f"E2E_PARKING_{profile['parking_camera']}",
                handoff_path=root/'gate/single_vehicle_handoff.json',enable_http=True,enable_space_http=True,
                allowed_codes=['999F-Z01'],environment=env)
        if report['status'] in ('FAILED','INCOMPLETE'):
            raise RuntimeError('B camera did not complete safely: '+str(report.get('error_type')))
    finally:
        if state['cap'] is not None:state['cap'].release()
        if state['frame'] is not None:
            out.mkdir(exist_ok=True);cv2.imwrite(str(out/'last_frame.png'),state['frame'])
        cv2.destroyAllWindows();print('B_CAMERA_RELEASED',flush=True)
if __name__=='__main__':main()

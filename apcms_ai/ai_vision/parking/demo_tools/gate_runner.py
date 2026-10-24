from pathlib import Path
import json,cv2,time,os

def main():
    from ai_vision.parking.demo_session import load_demo_profile
    profile=load_demo_profile(os.environ['PARKING_DEMO_PROFILE_DIR'])
    from ai_vision.recognition.run_live_gate import main as execute
    from ai_vision.recognition.preview_gate_config import LiveGatePreview
    from ai_vision.recognition.vehicle_http import VehicleHTTPClient
    from ai_vision.recognition.live_gate_processor import LiveGateProcessor
    original_preview_init=LiveGatePreview.__init__
    def preview_init(self,*args,**kwargs):
        original_preview_init(self,*args,**kwargs)
        cv2.namedWindow(self._name,cv2.WINDOW_NORMAL);cv2.resizeWindow(self._name,600,480);cv2.moveWindow(self._name,20,60)
    LiveGatePreview.__init__=preview_init
    root=Path(os.environ['PARKING_DEMO_RUN_DIR']);layout=profile['root'];out=root/'gate'
    original_track=LiveGateProcessor._track
    observed={'rows':[],'frame':0,'saved_bytes':0}
    (root/'gate_frames').mkdir(exist_ok=True)
    def track(self,frame):
        sampled_at=time.monotonic()
        observed['gap_seconds']=sampled_at-observed.get('last_sampled_at',sampled_at)
        observed['last_sampled_at']=sampled_at
        rows=original_track(self,frame);observed['rows']=rows;observed['frame']+=1
        observed['inference_seconds']=time.monotonic()-sampled_at
        saved=None
        if observed['saved_bytes']<256*1024*1024 and observed['frame']<=2000:
            ok,data=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,85])
            if ok and observed['saved_bytes']+data.nbytes<=256*1024*1024:
                saved=f"gate_frames/{observed['frame']:06d}.jpg"
                (root/saved).write_bytes(data.tobytes());observed['saved_bytes']+=data.nbytes
        with (root/'tracking_observations.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'frame':observed['frame'],'monotonic':sampled_at,'processed_at':time.monotonic(),'image':saved,'rows':rows})+'\n')
        return rows
    LiveGateProcessor._track=track
    original_show=LiveGatePreview.__call__
    def show(self,frame):
        try:text=(root/'phase.txt').read_text(encoding='utf-8')
        except OSError:text='WAIT: KEEP BOTH EMPTY'
        display=frame.copy();cv2.putText(display,text,(15,95),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,255,255),2)
        gap=observed.get('gap_seconds',0)
        label=f"A inference {observed.get('inference_seconds',0):.2f}s / sample gap {gap:.2f}s"
        cv2.putText(display,label,(15,130),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,255,255),2)
        if gap>1:
            cv2.putText(display,'SLOW PROCESSING: TRACK CONTINUITY MAY RESET',(15,165),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,255),2)
        h,w=display.shape[:2];line=int(h*.5)
        for y in (line-12,line+12):cv2.line(display,(int(w*.15),y),(int(w*.85),y),(0,255,255),1)
        cv2.putText(display,'UPPER AREA: HOLD PLATE CENTER 2s',(190,line-65),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,255,0),2)
        cv2.putText(display,'LOWER AREA: HOLD PLATE CENTER 2s',(190,line+90),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,255,0),2)
        for row in observed['rows']:
            x1,y1,x2,y2=row['box'];cx=(x1+x2)//2;cy=(y1+y2)//2
            cv2.rectangle(display,(x1,y1),(x2,y2),(0,255,0),2);cv2.circle(display,(cx,cy),5,(0,255,255),-1)
            cv2.putText(display,f"ID {row['track_id']} / Y {cy}",(x1,max(20,y1-10)),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,0),2)
        return original_show(self,display)
    LiveGatePreview.__call__=show
    native=cv2.VideoCapture;state={'cap':None,'frame':None}
    send=VehicleHTTPClient.send
    def guarded_send(self,event):
        if not (root/'fixture_ready.flag').exists() or not (root/'parking_ready.flag').exists():raise RuntimeError('B empty preflight not ready; no HTTP sent')
        if event.get('plate_number')!=profile['plate_number']:raise ValueError('Unexpected plate; no HTTP sent')
        with (root/'gate_http_journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'stage':'BEFORE_SEND','payload':event},ensure_ascii=False)+'\n')
        receipt=send(self,event)
        with (root/'gate_http_journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'stage':'RECEIPT','payload':event,'receipt':receipt},ensure_ascii=False)+'\n')
        if event.get('direction')=='ENTRY' and receipt.get('state')=='UNCHANGED':raise RuntimeError('Existing open usage detected; stop test')
        return receipt
    VehicleHTTPClient.send=guarded_send
    class Capture:
        def __init__(self,index):
            if index!=profile['gate_camera']:raise ValueError('Unexpected gate camera index')
            self.native=native(index,cv2.CAP_MSMF);self.native.set(cv2.CAP_PROP_FRAME_WIDTH,1280);self.native.set(cv2.CAP_PROP_FRAME_HEIGHT,1024);state['cap']=self
        def read(self):
            if (root/'stop_requested.flag').exists():raise RuntimeError('SAFETY_ABORT_REQUESTED')
            ok,frame=self.native.read()
            if ok:(root/'gate_ready.flag').write_text('READY',encoding='utf-8')
            if ok:state['frame']=frame.copy()
            return ok,frame
        def release(self):self.native.release()
        def __getattr__(self,k):return getattr(self.native,k)
    original_ready=LiveGatePreview.wait_until_ready
    def manual_start(self,capture):
        if not original_ready(self,capture):return False
        (root/'gate_started.flag').write_text('SPACE_PRESSED',encoding='utf-8')
        while not (root/'fixture_ready.flag').exists():
            ok,frame=capture.read()
            if not ok:raise RuntimeError('A preparation camera read failed')
            if not self(frame):return False
        return True
    cv2.VideoCapture=Capture;LiveGatePreview.wait_until_ready=manual_start
    try:
        execute(['--camera-index',str(profile['gate_camera']),'--camera-id',f"E2E_GATE_{profile['gate_camera']}",'--down-direction','ENTRY','--tracking-target','plate','--tracking-imgsz','960','--preview','--seconds',str(profile['seconds']),'--config',str(profile['gate_config']),'--output-dir',str(out),'--single-vehicle-handoff','--enable-http','--boot-context-url',profile['boot_context_url']])
    finally:
        if state['cap'] is not None:state['cap'].release()
        if state['frame'] is not None:
            out.mkdir(exist_ok=True);cv2.imwrite(str(out/'last_frame.png'),state['frame'])
        cv2.destroyAllWindows();print('A_CAMERA_RELEASED',flush=True)
if __name__=='__main__':main()

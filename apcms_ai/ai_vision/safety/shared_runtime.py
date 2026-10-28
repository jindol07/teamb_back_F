"""주차가 준비한 현재 실행의 A/B 공유 화재 작업을 서버 수명주기에 연결합니다."""
import multiprocessing
import os
from pathlib import Path
import threading
import time
from ai_vision.parking.frame_exchange import read_latest
from ai_vision.parking.parking_process_scope import terminate_worker_tree
from ai_vision.safety.shared_runtime_worker import run_shared_worker


class SharedSafetyRuntime:
    def __init__(self, parking, *, context=None, worker=None):
        self.parking=parking;self.context=context;self.worker=worker or run_shared_worker
        self.state='DISABLED';self.reason=None;self.processes=[]
        self.closing=threading.Event();self.lock=threading.RLock();self.stop_event=None
        self.monitor=None;self.shared_dir=None;self.config=None;self.delivery=None

    def prepare(self):
        raw=os.environ.get('SAFETY_SHARED_AUTOSTART','false').lower()
        if raw not in ('true','false','1','0'):raise ValueError('SAFETY_SHARED_AUTOSTART는 true/false입니다.')
        if raw in ('false','0'):return
        direct=os.environ.get('SAFETY_CAMERA_AUTOSTART',str(os.name=='nt')).lower()
        if direct not in ('false','0','no','off'):raise ValueError('공유 감시에서는 SAFETY_CAMERA_AUTOSTART=false를 명시하세요.')
        self.config=self.parking.load_config()
        if not self.config or not self.config.get('frame_export_dir'):
            raise ValueError('공유 화재 자동 시작에는 활성 주차와 frame_export_dir이 필요합니다.')
        from ai_vision.safety.shared_delivery_config import load_shared_delivery
        self.delivery=load_shared_delivery(os.environ)
        self.state='WAITING_FOR_PARKING'

    def start(self):
        if self.state=='DISABLED':return
        self.monitor=threading.Thread(target=self._watch,daemon=True);self.monitor.start()

    def tick(self):
        # 1. 최신 폴더를 추측하지 않고 현재 서버가 소유한 주차 run_id만 사용합니다.
        with self.lock:
            if self.closing.is_set():return
            state=self.parking.snapshot()['state']
            if state in ('FAILED','STOPPED','DISABLED'):
                raise RuntimeError('PARKING_UNAVAILABLE')
            if self.state=='WAITING_FOR_PARKING' and state=='RUNNING':
                run=self.parking.run_dir
                if run is None:raise RuntimeError('PARKING_RUN_MISSING')
                shared=Path(self.config['frame_export_dir'])/run.name
                for role in ('gate','parking'):
                    try:item=read_latest(shared/(role+'.frame'))
                    except PermissionError:return
                    if item is None:return
                    meta,_=item
                    if meta['run_id']!=run.name or meta['role']!=role or meta['camera_id']!=self.config[role+'_id']:
                        raise RuntimeError('SHARED_IDENTITY_MISMATCH')
                self.shared_dir=shared
                context=self.context or multiprocessing.get_context('spawn')
                self.stop_event=context.Event()
                for role in ('gate','parking'):
                    output=run/'shared_safety'/role
                    delivery=self.delivery if self.delivery and self.delivery['role'] in (role,'both') else None
                    child=context.Process(target=self.worker,args=(role,self.config[role+'_id'],str(shared),str(output),self.config.get('preview',False),self.stop_event,delivery),name='shared-safety-'+role)
                    child.start();self.processes.append(child)
                self.state='RUNNING'
            if self.state=='RUNNING' and any(not child.is_alive() for child in self.processes):
                raise RuntimeError('SHARED_SAFETY_CHILD_EXITED')

    def _watch(self):
        started=time.monotonic()
        try:
            while not self.closing.wait(.25):
                self.tick()
                if self.state=='WAITING_FOR_PARKING' and time.monotonic()-started>210:
                    raise RuntimeError('SHARED_PREPARATION_TIMEOUT')
        except Exception as error:
            self.state='FAILED';self.reason=str(error) if isinstance(error,RuntimeError) else type(error).__name__
            self.stop()

    def stop(self):
        with self.lock:
            self.closing.set()
            if self.stop_event is not None:self.stop_event.set()
            deadline=time.monotonic()+20
            for child in self.processes:child.join(timeout=max(0,deadline-time.monotonic()))
            for child in self.processes:
                if child.is_alive():
                    terminate_worker_tree(child);self.state='FAILED';self.reason='FORCED_STOP_REQUIRES_REVIEW'
            if self.state not in ('DISABLED','FAILED'):self.state='STOPPED'
        if self.monitor is not None and self.monitor is not threading.current_thread():self.monitor.join(timeout=2)

    def snapshot(self):
        return {'state':self.state,'reason':self.reason,'delivery':'TEST_HTTP_ENABLED' if self.delivery else 'DRY_RUN_NO_HTTP',
                'send_role':self.delivery['role'] if self.delivery else None,
                'shared_run_id':self.shared_dir.name if self.shared_dir else None,
                'processes':[{'role':p.name,'alive':p.is_alive(),'exit_code':p.exitcode} for p in self.processes]}

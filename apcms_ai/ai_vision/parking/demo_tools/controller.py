import sys,os,subprocess,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'apcms_ai'))
from ai_vision.parking.demo_session import finalize_trial,load_demo_profile,demo_phase
PROFILE=load_demo_profile(os.environ['PARKING_DEMO_PROFILE_DIR'])
RUN=Path(os.environ['PARKING_DEMO_RUN_DIR'])
DB=PROFILE['root']/'.demo_helper'
MANIFEST=RUN/'camera_e2e_fixture.properties'
CP=str(DB)+os.pathsep+(DB/'classpath.txt').read_text(encoding='utf-8-sig').strip()

def read_snapshot(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return None

def read_journal(path):
    try:lines=path.read_text(encoding='utf-8').splitlines()
    except FileNotFoundError:return []
    rows=[]
    for line in lines:
        try:row=json.loads(line)
        except ValueError:continue
        if isinstance(row,dict):rows.append(row)
    return rows

sys.path.insert(0,str(ROOT/'apcms_ai'))
from ai_vision.parking.demo_session import finalize_trial

children=[];logs=[];report={'scope':'REAL_TWO_CAMERAS_HTTP_SHARED_ORACLE','schema_changed':False,
    'identity_verification_required':os.environ.get('PARKING_DEMO_VERIFY_HANDOFF_PLATE')=='1'}
def db(mode):
    r=subprocess.run(['java','-cp',CP,'CameraE2EFixture',mode],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=40,env=dict(os.environ,CAMERA_E2E_MANIFEST=str(MANIFEST),CAMERA_E2E_DB_URL=PROFILE['expected_db_url'],CAMERA_E2E_PLATE=PROFILE['plate_number']))
    if r.returncode:raise RuntimeError('DB '+mode+' failed: '+r.stderr[-2000:])
    return r.stdout.strip()
if __name__=='__main__':
    assert not MANIFEST.exists(),'Existing E2E manifest requires review'
    prepared=False
    try:
        env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'apcms_ai');env['PYTHONIOENCODING']='utf-8'
        for name in ['gate','parking']:
            log=(RUN/(name+'_stdout.log')).open('w',encoding='utf-8');logs.append(log)
            children.append(subprocess.Popen([sys.executable,str(Path(__file__).with_name(name+'_runner.py'))],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT))
        print('PREVIEW_ONLY: PRESS SPACE IN EACH WINDOW; NO DB WRITES YET',flush=True)
        started=None
        while any(p.poll() is None for p in children):
            if any(p.poll() not in (None,0) for p in children):
                (RUN/'stop_requested.flag').write_text('CHILD_FAILED',encoding='utf-8')
            if any(p.poll() is not None for p in children) and not prepared:
                (RUN/'stop_requested.flag').write_text('PREPARATION_CANCELLED',encoding='utf-8')
            phase='PREVIEW: PRESS SPACE IN EACH WINDOW / KEEP EMPTY'
            if (not prepared and not (RUN/'stop_requested.flag').exists()
                            and all((RUN/name).exists() for name in ('gate_started.flag','parking_started.flag','parking_ready.flag'))):
                print(db('prepare'),flush=True);prepared=True;started=time.monotonic()
                (RUN/'fixture_ready.flag').write_text('DB_FIXTURE_READY',encoding='utf-8')
            if prepared:
                try: rows=read_journal(RUN/'gate_http_journal.jsonl')
                except OSError: rows=[]
                phase=demo_phase(rows,read_snapshot(RUN/'parking/parking_camera_check.json'),PROFILE['plate_number'],
                                 require_identity_verification=report['identity_verification_required'])
                if phase.startswith('STOP:'):
                    (RUN/'stop_requested.flag').write_text('USAGE_ID_MISMATCH',encoding='utf-8')
            if (RUN/'stop_requested.flag').exists() and not phase.startswith('STOP:'):phase='STOP: PRECHECK FAILED / NO RETRY'
            (RUN/'phase.txt').write_text(phase,encoding='utf-8')
            if started is not None and time.monotonic()-started>380:raise RuntimeError('Camera watchdog exceeded; inspect processes before cleanup')
            time.sleep(.25)
        report['process_exit_codes']=[p.returncode for p in children]
    except BaseException as error:
        report['controller_error_type']=type(error).__name__
        (RUN/'stop_requested.flag').write_text('CONTROLLER_FAILED',encoding='utf-8')
        # 카메라를 강제 종료하지 않고 다음 읽기에서 종료·사진 저장하도록 기다립니다.
        deadline=time.monotonic()+45
        for child in children:
            try:child.wait(timeout=max(.1,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:pass
        raise
    finally:
        for log in logs:log.close()
        report['process_exit_codes']=[p.poll() for p in children]
        report=finalize_trial(RUN,report,children_stopped=all(p.poll() is not None for p in children),fixture_prepared=prepared,db=db,expected_plate=PROFILE['plate_number'])
        print('RESULT='+str(RUN/'http_e2e_result.json'),flush=True)
        print('TEST_SUCCESS='+str(report.get('success',False)),flush=True)
        print('CLEANUP='+str(report['cleanup']),flush=True)
        if report.get('cleanup','').startswith('NOT_EXECUTED'):print('CLEANUP_PENDING: DO NOT START ANOTHER RUN',flush=True)

"""시험 소유 파일과 검증된 입차 근거가 있는 실행만 정리합니다."""
import re
from datetime import datetime
from pathlib import Path
from ai_vision.recognition.local_io import read_json, write_json_atomic
from ai_vision.parking.demo_tools.deployed_fixture import DeployedFixture


def properties(path):
    if not path.is_file():return {}
    if path.stat().st_size>65536:raise ValueError('시험 소유 파일 크기 초과')
    result={}
    for line in path.read_text(encoding='ascii').splitlines():
        if not line or line.startswith(('#','!')):continue
        key,sep,value=line.partition('=')
        if not sep or key in result:raise ValueError('시험 소유 파일 형식 오류')
        result[key]=value
    return result


def verified_active(handoff):
    active=handoff.get('active') or {}
    usage=active.get('parking_usage_id');at=active.get('detected_at')
    if (handoff.get('record_type')!='SINGLE_VEHICLE_HANDOFF' or not handoff.get('owner_session_id')
        or handoff.get('status') not in ('ACTIVE','BLOCKED') or active.get('plate_number')!='91소6408'
        or type(usage) is not int or usage<1 or not isinstance(at,str)):
        return None
    try:stamp=datetime.fromisoformat(at.replace('Z','+00:00'))
    except ValueError:return None
    return (usage,at) if stamp.tzinfo is not None else None


def cleanup_owned_run(run, *, fixture=None):
    run=Path(run).resolve();meta=properties(run/'reservation.properties')
    if meta.get('committed')!='true':return {'status':'NO_COMMITTED_FIXTURE'}
    if not re.fullmatch(r'AI_SITE_TEST_[0-9a-f]{8}',meta.get('marker','')):
        raise ValueError('미확인 시험 소유 표식')
    fixture=fixture or DeployedFixture(run)
    result={};owned={}
    for gate in sorted((run/'parking_runs').glob('*/gate/single_vehicle_handoff.json')):
        if not re.fullmatch(r'[0-9a-f]{32}',gate.parents[1].name):raise ValueError('미확인 카메라 실행 폴더')
        handoff=read_json(gate);active=verified_active(handoff)
        if handoff.get('active') is not None and active is None:
            raise ValueError('입차 소유 근거가 불완전하여 자동 정리하지 않습니다.')
        if active:
            usage,at=active
            result['usage']=fixture.call('close-usage',usage,entry_at=at)
        report=gate.parents[1]/'parking/parking_camera_check.json'
        if not report.is_file():continue
        data=read_json(report,max_bytes=16*1024*1024)
        events={event.get('event_id'):event for event in data.get('events',[]) if isinstance(event,dict)}
        for receipt in data.get('deliveries',[]):
            event=events.get(receipt.get('event_id')) or {};response=receipt.get('response') or {}
            code=event.get('space_code');identifier=response.get('aiDetectionEventId')
            if (code not in ('3F-A01','3F-A02','3F-A03','3F-A04') or type(identifier) is not int or identifier<1
                or receipt.get('status') not in ('UPDATED','UNCHANGED','DUPLICATE')):continue
            event_id=event.get('event_id','')
            if not re.fullmatch(r'[0-9a-f-]{36}',event_id):raise ValueError('점유 소유 ID 형식 오류')
            space=45+int(code[-2:])
            if identifier>int(owned.get('id_'+str(space),'0')):
                owned['id_'+str(space)]=str(identifier);owned['event_'+str(space)]=event_id
    result['reservation']=fixture.call('cancel')
    if owned:
        (run/'owned_occupancy.properties').write_text(''.join(k+'='+v+'\n' for k,v in owned.items()),encoding='ascii')
        result['spaces']=fixture.call('restore-spaces')
    result['status']='CLEANED'
    write_json_atomic(run/'automatic_cleanup.json',result)
    return result


def recover_pending_runs(parent, current):
    results=[]
    for run in sorted(Path(parent).iterdir()):
        if not run.is_dir() or run.resolve()==Path(current).resolve() or not re.fullmatch(r'[0-9a-f]{32}',run.name):continue
        if (run/'automatic_cleanup.json').is_file():continue
        try:
            meta=properties(run/'reservation.properties')
            if meta.get('committed')!='true':continue
            result=run/'result.json'
            if result.is_file() and read_json(result).get('success') is True:continue
            fixture=DeployedFixture(run);fixture.compile()
            results.append({'run_id':run.name,'cleanup':cleanup_owned_run(run,fixture=fixture)})
        except Exception as error:
            # 잘못된 과거 파일 자체로 실행을 실패시키지 않습니다. DB 충돌 검사는 그대로 수행합니다.
            results.append({'run_id':run.name,'cleanup':{'status':'REVIEW_REQUIRED','error_type':type(error).__name__}})
    return results

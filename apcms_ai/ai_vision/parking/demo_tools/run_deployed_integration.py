"""실제 지하 3층 예약·주차 확인 후 공유 화재 A→B 시험을 순서대로 실행합니다."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid
from dotenv import dotenv_values
from ai_vision.parking.parking_runtime import ParkingRuntime
from ai_vision.safety.shared_runtime import SharedSafetyRuntime
from ai_vision.recognition.local_io import read_json, write_json_atomic
from ai_vision.parking.demo_tools.deployed_fixture import DeployedFixture
from ai_vision.parking.demo_tools.deployed_sequence import active_usage, decision, exited, acknowledged_fire, empty_ready, trial_config
from ai_vision.parking.demo_tools.deployed_worker import run_worker

PHASE_FILE=None


def snapshot(path):
    try:return read_json(path)
    except (OSError,ValueError):return {}


def wait_for(check, seconds, runtime, safety=None):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if runtime.snapshot()['state'] in ('FAILED','STOPPED'):
            raise RuntimeError('주차 작업 중단')
        if safety and safety.snapshot()['state']=='FAILED':raise RuntimeError('공유 화재 작업 중단')
        value=check()
        if value:return value
        time.sleep(.25)
    raise TimeoutError('현재 단계 제한 시간 초과')


def phase(value):
    if PHASE_FILE is not None:PHASE_FILE.write_text(value,encoding='utf-8')
    print('PHASE: '+value,flush=True)


def main(argv=None):
    global PHASE_FILE
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--no-reservation',action='store_true')
    parser.add_argument('--free-parking',action='store_true')
    args=parser.parse_args(argv)
    if args.free_parking and args.no_reservation:parser.error('자유 주차 시험은 A01 예약 방식입니다.')
    os.environ['DEPLOYED_DEMO_NO_RESERVATION']='1' if args.no_reservation else '0'
    source=args.config.resolve()
    config=read_json(source)
    ai=Path(__file__).resolve().parents[3]
    settings=dotenv_values(ai/'.env',encoding='utf-8-sig',interpolate=False)
    for key,value in settings.items():
        if value is not None:os.environ.setdefault(key,value)
    os.environ.update(SAFETY_CAMERA_AUTOSTART='false',SAFETY_SHARED_AUTOSTART='true',
        SAFETY_SHARED_SEND_ENABLED='true',SAFETY_SHARED_ALLOW_TEST='true',SAFETY_SHARED_SEND_ROLE='both',
        SAFETY_SHARED_ALERT_URL='http://52.79.133.132:3000/admin-api/api/parking/ai/fire-alerts',
        SAFETY_TEST_AWS_HTTP='1',SAFETY_CAMERA_SEND_MODE='test',PARKING_RUNTIME_ENABLED='true')
    if not os.environ.get('FIRE_ALERT_TOKEN'):raise ValueError('화재 송신 인증 설정 없음')
    expected={f'A-{i:02d}':f'3F-A{i:02d}' for i in range(1,5)}
    if config.get('space_code_map')!=expected:raise ValueError('지하 3층 네 구획 매핑이 필요합니다.')
    if config.get('boot_context_url')!='http://52.79.133.132:3000/admin-api':raise ValueError('배포 API 대상이 다릅니다.')
    # 1. 매번 별도 실행 폴더를 만들어 증거와 예약 소유 정보를 덮어쓰지 않습니다.
    root=ai/'ai_vision/results/deployed_integration'/uuid.uuid4().hex
    root.mkdir(parents=True)
    PHASE_FILE=root/'phase.txt';phase('PREPARING')
    config=trial_config(config,source,root)
    path=root/'runtime.json';write_json_atomic(path,config)
    os.environ['PARKING_RUNTIME_CONFIG']=str(path)
    fixture=DeployedFixture(root,reservation_required=not args.no_reservation);fixture.compile()
    runtime=ParkingRuntime(worker_target=run_worker);runtime.load_config()
    from ai_vision.safety.shared_delivery_config import load_shared_delivery
    load_shared_delivery(os.environ)
    if args.check_only:
        print('PREFLIGHT_OK: 카메라·HTTP·DB 작업 없음',flush=True)
        return 0
    # 2. 루프백 실행 잠금부터 잡고 나서 예약을 만듭니다. 다른 주차 실행과 겹치지 않습니다.
    import socket
    lease=socket.socket()
    try:lease.bind(('127.0.0.1',47632));lease.listen(1)
    except OSError:
        lease.close();raise RuntimeError('다른 통합 시험이 실행 중입니다.')
    report={'scope':'AWS_EXISTING_FLOOR3_PARKING_AND_FIRE_TEST','run_dir':str(root),'success':False,
            'reservation_required':not args.no_reservation,'free_parking':args.free_parking}
    safety=None;prepared=False
    try:
        contract_marker=source.parent/'backend_contract.json'
        if contract_marker.is_file() and read_json(contract_marker).get('status')=='PENDING_POLICY_ALIGNMENT':
            from ai_vision.parking.demo_tools.deployed_outcome import FixtureFailure
            raise FixtureFailure('BACKEND_POLICY_CHANGED')
        # 기존 카메라 런타임의 잠금도 검사하여 중복 실행 전 DB 변경을 막습니다.
        check_lease=socket.socket()
        try:check_lease.bind(('127.0.0.1',47631))
        finally:check_lease.close()
        from ai_vision.parking.demo_tools.deployed_recovery import recover_pending_runs
        report['previous_test_recovery']=recover_pending_runs(root.parent,root)
        if report['previous_test_recovery']:
            cleaned=sum(row['cleanup']['status']=='CLEANED' for row in report['previous_test_recovery'])
            print('RECOVERY: CLEANED='+str(cleaned)+' / REVIEW_REQUIRED='+str(len(report['previous_test_recovery'])-cleaned),flush=True)
        from ai_vision.parking.demo_tools.release_capability import require_release_enabled
        report['release_capability']=require_release_enabled(config['boot_context_url'],os.environ)
        reservation=fixture.call('prepare');prepared=True;report['reservation']=reservation
        print('RESERVATION: NONE' if args.no_reservation else 'RESERVATION: 3F-A01 / ID='+reservation['RESERVATION_ID'],flush=True)
        runtime.start()
        wait_for(lambda:runtime.run_dir and empty_ready(snapshot(runtime.run_dir/'parking/parking_camera_check.json')),210,runtime)
        run=runtime.run_dir;report['parking_run']=str(run)
        camera_pids=[child.pid for child in runtime.processes]
        report['camera_pids_at_start']=camera_pids
        phase('1 ENTRY / 입차')
        usage=wait_for(lambda:active_usage(snapshot(run/'gate/single_vehicle_handoff.json')),300,runtime)
        report['parking_usage_id']=usage
        def deliveries():return snapshot(run/'parking/parking_camera_check.json').get('vehicle_space',{}).get('deliveries',[])
        if args.free_parking:
            from ai_vision.parking.demo_tools.free_parking import update_free_observation
            state={};report['free_parking_observation']=state
            phase('2 FREE_PARKING / A01 예약·네 칸 자유 이동 후 출차')
            def free_complete():
                update_free_observation(state,snapshot(run/'parking/parking_camera_check.json'),usage)
                return exited(snapshot(run/'gate/single_vehicle_handoff.json'),usage)
            wait_for(free_complete,600,runtime)
            if not state.get('observed_occupied_codes'):raise RuntimeError('주차면 점유 관찰 근거 없음')
            if not state.get('confirmed_position_events'):raise RuntimeError('실제 위치 연결 응답 근거 없음')
        else:
            run_fixed_parking(args,run,runtime,fixture,usage,report,deliveries)
        phase('4 EXIT_CONFIRMED / 사진 제거')
        ended=fixture.call('inspect',usage);report['exit_db']=ended
        if ended.get('EXITED_ROWS')!='1':raise RuntimeError('DB 출차 확인 실패')
        finish_parking_and_fire(root,run,runtime,fixture,report,camera_pids)
        prepared=False
        report['sequence_complete']=True
    except KeyboardInterrupt:
        report.update(cancelled=True,error_type='KeyboardInterrupt',error_code='USER_CANCELLED')
        print('TEST_CANCELLED: 사용자가 Ctrl+C로 중단했습니다. 시험 완료와는 다릅니다.',flush=True)
    except Exception as error:
        report['error_type']=type(error).__name__
        from ai_vision.parking.demo_tools.deployed_outcome import FixtureFailure
        if isinstance(error,FixtureFailure):
            report.update(error_code=error.code,error_message=str(error))
        else:
            report.update(error_code='EXECUTION_FAILED',error_message='시험 단계 실행 중 중단됐습니다. 결과 파일을 확인하세요.')
        print('TEST_STOPPED: '+report['error_code']+' / '+report['error_message'],flush=True)
    finally:
        # 공유 감시 객체는 아래 함수의 finally에서 카메라보다 먼저 종료됩니다.
        runtime.stop();report['runtime_final']=runtime.snapshot()
        if prepared:
            from ai_vision.parking.demo_tools.deployed_recovery import cleanup_owned_run
            try:report['automatic_cleanup']=cleanup_owned_run(root,fixture=fixture)
            except Exception as error:report['automatic_cleanup_error']=type(error).__name__
        lease.close()
        from ai_vision.parking.demo_tools.deployed_outcome import result_exit_code, final_completion_checks
        parked=Path(report['parking_run']) if report.get('parking_run') else None
        report['completion_checks']=final_completion_checks(report,
            snapshot(parked/'parking/parking_camera_check.json') if parked else {},
            snapshot(parked/'gate/summary.json') if parked else {})
        report['success']=all(report['completion_checks'].values())
        exit_code=result_exit_code(report)
        write_json_atomic(root/'result.json',report)
        print('RESULT='+str(root/'result.json'),flush=True)
        print('TEST_SUCCESS='+str(report['success']),flush=True)
        print('TEST_STATUS='+report['status'],flush=True)
    return exit_code


def run_fixed_parking(args,run,runtime,fixture,usage,report,deliveries):
    first_decision='NO_VALID_RESERVATION' if args.no_reservation else 'WRONG_SPACE'
    second_decision='NO_VALID_RESERVATION' if args.no_reservation else 'MATCHED'
    phase('2 '+first_decision+' / A-02')
    wait_for(lambda:decision(deliveries(),usage,'3F-A02',first_decision,require_link=True),180,runtime)
    wrong=fixture.call('inspect',usage);report['wrong_space_db']=wrong
    if wrong.get('LINKED_SPACE_ID')!='47' or wrong.get('LINKED_RESERVATION_ID')!='0':
        raise RuntimeError('A02 실제 위치 연결·예약 미연결 확인 실패')
    phase('3 '+second_decision+' / A-01')
    wait_for(lambda:decision(deliveries(),usage,'3F-A01',second_decision,require_link=True),180,runtime)
    matched=fixture.call('inspect',usage);report['matched_db']=matched
    if args.no_reservation:
        if matched.get('LINKED_SPACE_ID')!='46' or matched.get('LINKED_RESERVATION_ID')!='0':
            raise RuntimeError('예약 없는 차량의 실제 위치 연결 확인 실패')
    elif matched.get('MATCHED_ROWS')!='1':raise RuntimeError('예약 자리 DB 연결 확인 실패')
    phase('4 EXIT / 사진 제거 후 출차')
    wait_for(lambda:exited(snapshot(run/'gate/single_vehicle_handoff.json'),usage),180,runtime)


def finish_parking_and_fire(root,run,runtime,fixture,report,camera_pids):
    safety=None
    try:
        # 출차 후 주차 송신을 중단합니다. 휴대전화로 구획이 가려져도 업무 점유를 바꾸지 않습니다.
        wait_for(lambda:empty_ready(snapshot(run/'parking/parking_camera_check.json')),60,runtime)
        time.sleep(5)
        (root/'parking_delivery_paused.flag').touch()
        wait_for(lambda:all((root/('parking_delivery_paused.'+role+'.ack')).exists() for role in ('gate','parking')),30,runtime)
        report['parking_delivery_paused']=True
        report['reservation_cancel']=fixture.call('cancel')
        phase('FIRE PREPARING / 차량 사진과 손 제거')
        safety=SharedSafetyRuntime(runtime);safety.prepare();safety.start()
        wait_for(lambda:runtime.run_dir and all((runtime.run_dir/'shared_safety'/role/'preview_overlay.json').is_file() for role in ('gate','parking')),210,runtime,safety)
        report['fire_run']=str(runtime.run_dir)
        report['camera_pids_at_fire']=[child.pid for child in runtime.processes]
        report['camera_continuity_verified']=(report['fire_run']==report['parking_run']
            and report['camera_pids_at_fire']==camera_pids and all(child.is_alive() for child in runtime.processes))
        if not report['camera_continuity_verified']:raise RuntimeError('카메라 연속 실행 확인 실패')
        for role,label in (('gate','5 FIRE_A / 입출차 카메라 불꽃'),('parking','6 FIRE_B / 주차면 카메라 불꽃')):
            output=runtime.run_dir/'shared_safety'/role
            excluded=snapshot(output/'fire_alert_sent_state.json').get('acknowledged_transition_ids',[])
            phase(label)
            wait_for(lambda:acknowledged_fire(output,excluded),120,runtime,safety)
            report[role+'_fire_ack']=True
            time.sleep(5)
        phase('DONE / 휴대전화 제거')
        time.sleep(5)
    finally:
        if safety:
            safety.stop()
            report['fire_final']=safety.snapshot()


if __name__=='__main__':raise SystemExit(main())

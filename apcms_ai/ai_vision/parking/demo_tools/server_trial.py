"""승인된 임시 시험 범위에서만 서버 수명주기+실제 HTTP를 검증합니다.

운영 JSON의 시험 구획 차단은 변경하지 않습니다. PowerShell -ServerTrial에서만 실행합니다.
"""
import asyncio
import importlib
import os
import re
import socket
import threading
import time
from pathlib import Path
from fastapi import FastAPI
from ai_vision.parking.parking_runtime import ParkingRuntime, install_parking_runtime
from ai_vision.parking.demo_session import load_demo_profile, finalize_trial
from ai_vision.recognition.local_io import write_json_atomic


def load_trial_config(environment, **_):
    profile = load_demo_profile(environment["PARKING_DEMO_PROFILE_DIR"])
    run = Path(environment["PARKING_DEMO_RUN_DIR"]).resolve()
    if run.parent != profile["root"] or not re.fullmatch(r"e2e_manual_[0-9a-f]{8}", run.name):
        raise ValueError("전용 시험 실행 폴더가 필요합니다.")
    if not (profile["root"]/".demo_helper"/"classpath.txt").is_file():
        raise ValueError("기존 DB 시험 도우미 준비가 필요합니다.")
    return {"output_dir":str(run), "delivery_enabled":True, "profile_dir":str(profile["root"])}


def trial_worker(role, config, run_dir, stop_event, heartbeat):
    # 1. 실제 운영과 같은 실행 관리자·종료 신호를 사용하고 시험 구획 매핑은 자식에만 둡니다.
    from ai_vision.parking.parking_process_scope import isolate_worker
    isolate_worker()
    os.environ["PARKING_DEMO_PROFILE_DIR"]=config["profile_dir"]
    os.environ["PARKING_DEMO_RUN_DIR"]=run_dir
    def observed():
        heartbeat.value=time.monotonic()
    runner=importlib.import_module("ai_vision.parking.demo_tools."+role+"_runner")
    runner.main(stop_event=stop_event,on_frame=observed,autostart=True)


def create_trial_app():
    # 주차 전용 시험 앱입니다. 문의·추천·화재를 포함한 운영 main:app을 대체하지 않습니다.
    # 일반 서버의 실제 송신 요구를 이전 주차 전용 시험에 상속하지 않습니다.
    os.environ['VISION_REQUIRE_DEPLOYED_DELIVERY']='false'
    os.environ['SAFETY_SHARED_AUTOSTART']='false'
    app=FastAPI(title="APCMS Parking Server Trial")
    runtime=ParkingRuntime(check_safety=False,config_loader=load_trial_config,worker_target=trial_worker)
    install_parking_runtime(app,runtime=runtime)
    return app


def run_locked(lock,function,*args,**kwargs):
    # DB 준비가 진행 중에 취소돼도 정리가 먼저 시작되지 않게 합니다.
    with lock:
        return function(*args,**kwargs)


async def monitor_trial(runtime,server,report,server_task=None,db_lock=None):
    db_lock=threading.RLock() if db_lock is None else db_lock
    deadline=time.monotonic()+430
    prepared=False;started=None;done_since=None;controller=None
    try:
        while time.monotonic()<deadline:
            if server_task is not None and server_task.done():
                raise RuntimeError("시험 서버가 중간에 종료됐습니다.")
            if runtime.run_dir is not None and controller is None:
                os.environ["PARKING_DEMO_RUN_DIR"]=str(runtime.run_dir)
                controller=importlib.import_module("ai_vision.parking.demo_tools.controller")
                report.update(controller.report)
                report["scope"]="SERVER_LIFECYCLE_REAL_CAMERAS_HTTP_SHARED_ORACLE"
            if runtime.state=="FAILED":
                raise RuntimeError("주차 실행 실패: "+str(runtime.reason))
            if controller is not None:
                prepared,started,phase=await asyncio.to_thread(run_locked,db_lock,controller.update_trial,report,prepared,started,automatic=True)
                if phase.startswith("STOP:"):
                    raise RuntimeError("시험 중단 신호가 발생했습니다.")
                if phase.startswith("4 DONE"):
                    done_since=done_since or time.monotonic()
                    if time.monotonic()-done_since>=5:
                        report["automatic_shutdown_after_done"]=True
                        return controller,prepared
                else:
                    done_since=None
            await asyncio.sleep(.25)
        raise TimeoutError("서버 통합 시험 제한 시간 초과")
    except Exception as error:
        report["controller_error_type"]=type(error).__name__
        if runtime.run_dir is not None:
            (runtime.run_dir/"stop_requested.flag").write_text("SERVER_TRIAL_ABORTED",encoding="utf-8")
        return controller,prepared
    finally:
        server.should_exit=True


def complete_server_result(report):
    # 2. 업무 흐름이 성공했어도 서버 종료까지 확인되지 않으면 전체 성공으로 바꾸지 않습니다.
    checks=report.setdefault("completion_checks",{})
    checks["fixture_result_verified"]=report.get("success") is True
    checks["server_automatic_completion"]=report.get("automatic_shutdown_after_done") is True
    state=report.get("runtime_final_state") or {}
    checks["server_shutdown_confirmed"]=state.get("state")=="STOPPED" and not state.get("reason")
    checks["server_error_free"]=not report.get("server_error_type")
    report["success"]=all(checks.values())
    report["incomplete_reasons"]=[key for key,value in checks.items() if not value]
    return report


async def main():
    import uvicorn
    outer=Path(os.environ["PARKING_DEMO_RUN_DIR"]).resolve()
    listener=socket.socket()
    try:
        listener.bind(("127.0.0.1",8002))
        listener.listen(128)
        listener.setblocking(False)
    except OSError:
        listener.close()
        write_json_atomic(outer/"http_e2e_result.json",dict(success=False,cleanup="NOT_EXECUTED: local test port unavailable"))
        print("시험 포트8002를 사용할 수 없어 카메라/DB 실행 전에 중단했습니다.",flush=True)
        return 1
    app=create_trial_app();runtime=app.state.parking_runtime
    server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=8002,workers=1,
        log_level="warning",access_log=False,timeout_graceful_shutdown=45))
    report={"server_port":8002,"automatic_start":True}
    task=asyncio.create_task(server.serve(sockets=[listener]))
    controller=None;prepared=False
    db_lock=threading.RLock()
    print("SERVER_TRIAL: AUTO START / KEEP BOTH VIEWS EMPTY / NO SPACE INPUT",flush=True)
    try:
        controller,prepared=await monitor_trial(runtime,server,report,task,db_lock)
    finally:
        server.should_exit=True
        try:
            await asyncio.wait_for(task,timeout=70)
        except (Exception,asyncio.CancelledError) as error:
            report["server_error_type"]=type(error).__name__
            await asyncio.to_thread(runtime.stop)
        listener.close()
        report["runtime_final_state"]=runtime.snapshot()
        report["process_exit_codes"]=[p.exitcode for p in runtime.processes]
        stopped=all(not p.is_alive() for p in runtime.processes)
        if controller is not None:
            report=await asyncio.to_thread(run_locked,db_lock,finalize_trial,runtime.run_dir,report,
                children_stopped=stopped,fixture_prepared=prepared,db=controller.db,expected_plate=controller.PROFILE["plate_number"])
            report["server_session_dir"]=str(runtime.run_dir)
            report=complete_server_result(report)
            write_json_atomic(runtime.run_dir/"http_e2e_result.json",report)
        else:
            report.update(success=False,cleanup="NOT_EXECUTED: no fixture controller started")
        write_json_atomic(outer/"http_e2e_result.json",report)
        print("RESULT="+str(outer/"http_e2e_result.json"),flush=True)
        print("TEST_SUCCESS="+str(report["success"]),flush=True)
        print("CLEANUP="+str(report["cleanup"]),flush=True)
    return 0 if report.get("success") else 1


if __name__=="__main__":
    raise SystemExit(asyncio.run(main()))

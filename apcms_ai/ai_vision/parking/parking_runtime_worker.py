"""서버가 관리하는 격리된 카메라 프로세스. 시험 DB 도우미를 사용하지 않습니다."""
import os
import time
from pathlib import Path


def run_worker(role, config, run_dir, stop_event, heartbeat):
    from ai_vision.parking.parking_process_scope import isolate_worker
    isolate_worker()
    # 1. 관찰 모드에서는 기존 환경변수에 키가 있어도 송신을 활성화하지 않습니다.
    sending = config.get("delivery_enabled", False)
    if sending:
        from ai_vision.parking.parking_event_sender import _configured_api_key
        os.environ["AI_OCCUPANCY_API_KEY"] = _configured_api_key(os.environ)
        os.environ["PARKING_AI_BASE_URL"] = config["boot_context_url"]
    def observed():
        heartbeat.value = time.monotonic()
    run = Path(run_dir)
    if role == "gate":
        from ai_vision.recognition.run_live_gate import main
        args = ["--camera-index", str(config["gate_camera"]), "--camera-id", config["gate_id"],
              "--down-direction", config["down_direction"], "--config", config["gate_config"],
              "--output-dir", str(run/"gate"), "--tracking-target", "plate", "--tracking-imgsz", "960"]
        if config.get("preview", False):
            args.append("--preview")
        if sending:
            args += ["--enable-http", "--single-vehicle-handoff", "--boot-context-url", config["boot_context_url"]]
        main(args, stop_event=stop_event, runtime_mode=True, on_frame=observed)
    else:
        from ai_vision.parking.run_parking_camera import run_camera
        report = run_camera(config["reference"], config["spaces_config"], run/"parking",
            camera_index=config["parking_camera"], preview=config.get("preview", False), enable_http=sending,
            allowed_codes=config["allowed_codes"] if sending else (), track_vehicles=True, enable_space_http=sending,
            camera_id=config["parking_id"], tracking_target="plate", tracking_imgsz=1280,
            handoff_path=run/"gate"/"single_vehicle_handoff.json" if sending else None, stop_event=stop_event, runtime_mode=True, on_frame=observed)
        if report["status"] not in ("STOPPED",):
            raise RuntimeError("주차 관찰이 종료됐습니다.")

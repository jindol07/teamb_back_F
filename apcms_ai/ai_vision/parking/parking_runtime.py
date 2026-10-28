"""주차 프로세스 시작·종료·장애 중단. 자동 재시도와 신원 복구는 하지 않습니다."""
import multiprocessing
import asyncio
from contextlib import asynccontextmanager
import os
import socket
import threading
import time
from pathlib import Path
from uuid import uuid4
from ai_vision.parking.parking_runtime_config import load_runtime_config
from ai_vision.parking.parking_runtime_worker import run_worker
from ai_vision.parking.parking_process_scope import terminate_worker_tree
from ai_vision.recognition.local_io import write_json_atomic


class ParkingRuntime:
    def __init__(self, *, check_safety=True, config_loader=None, worker_target=None):
        self.config_loader = config_loader
        self.worker_target = worker_target
        self.check_safety = check_safety
        self.state = "DISABLED"
        self.reason = None
        self.delivery_enabled = False
        self.processes = []
        self.lease = None
        self.stop_event = None
        self.monitor = None
        self.heartbeats = []
        self.started_at = None
        self.closing = threading.Event()
        self.stop_lock = threading.RLock()
        self.run_dir = None
        self.journal_failed = False

    def load_config(self):
        # 시험 도구만 신뢰된 Python 호출로 실행 대상을 주입합니다. 운영 JSON 우회 옵션은 없습니다.
        return (self.config_loader or load_runtime_config)(os.environ, check_safety=self.check_safety)

    def start(self):
        if self.state != "DISABLED":
            raise RuntimeError("주차 실행은 이미 시작됐습니다.")
        config = self.load_config()
        if config is None:
            return
        self.delivery_enabled = config.get("delivery_enabled", False)
        self.state = "STARTING"
        try:
            # 1. 같은 호스트의 중복 uvicorn worker/서버가 카메라를 열지 못하게 합니다.
            self.lease = socket.socket()
            self.lease.bind(("127.0.0.1", 47631))
            context = multiprocessing.get_context("spawn")
            self.stop_event = context.Event()
            run = Path(config["output_dir"])/uuid4().hex
            run.mkdir(parents=True, exist_ok=False)
            self.run_dir = run
            if not self._save_state():
                raise OSError("주차 실행 상태를 저장할 수 없습니다.")
            self.started_at = time.monotonic()
            for role in ("gate", "parking"):
                heartbeat = context.Value("d", 0)
                self.heartbeats.append(heartbeat)
                child = context.Process(target=self.worker_target or run_worker, args=(role, config, str(run), self.stop_event, heartbeat), name="parking-"+role)
                child.start()
                self.processes.append(child)
            if not self._save_state():
                raise OSError("주차 실행 상태를 저장할 수 없습니다.")
            self.state = "STARTING"
            self.monitor = threading.Thread(target=self._watch, daemon=True)
            self.monitor.start()
        except Exception:
            self.state, self.reason = "FAILED", "START_FAILED"
            self.stop()
            raise RuntimeError("주차 자동 실행을 시작하지 못했습니다. 설정·중복 실행을 확인하세요.") from None

    def _watch(self):
        while not self.closing.wait(.5):
            with self.stop_lock:
                if self.closing.is_set():
                    return
                if any(not child.is_alive() for child in self.processes):
                    self.state, self.reason = "FAILED", "CHILD_EXITED"
                    self.stop()
                    return
                now = time.monotonic()
                if self.state == "STARTING" and all(h.value > 0 for h in self.heartbeats):
                    self.state = "RUNNING"
                    if not self._save_state():
                        self.stop()
                        return
                if any(now - (h.value or self.started_at) > (90 if h.value else 180) for h in self.heartbeats):
                    self.state, self.reason = "FAILED", "FRAME_PROGRESS_TIMEOUT"
                    self.stop()
                    return

    def snapshot(self):
        return {"state": self.state, "reason": self.reason,
                "delivery": "HTTP_ENABLED" if self.delivery_enabled else "OBSERVE_ONLY",
                "identity_mode": "GATE_HANDOFF" if self.delivery_enabled else "INDEPENDENT_OBSERVATION",
                "scope": "SINGLE_VEHICLE_LOCAL_CAMERAS", "state_record_failed": self.journal_failed, "inference_ready_verified": self.state == "RUNNING",
                "processes": [{"role": p.name, "alive": p.is_alive(), "exit_code": p.exitcode} for p in self.processes]}

    def _save_state(self):
        # 3. 주소·키·차량번호 없이 종료/실패 상태만 기록합니다. 재시작 복원 기능은 아닙니다.
        if self.run_dir is None:
            return True
        from datetime import datetime, timezone
        try:
            write_json_atomic(self.run_dir / "runtime_state.json",
                {**self.snapshot(), "recorded_at": datetime.now(timezone.utc).isoformat()})
            return True
        except (OSError, ValueError, TypeError):
            self.journal_failed = True
            self.state, self.reason = "FAILED", "STATE_RECORD_FAILED"
            return False

    def stop(self):
        with self.stop_lock:
            self._stop_locked()

    def _stop_locked(self):
        if self.state not in ("DISABLED", "FAILED", "STOPPED"):
            self.state = "STOPPING"
        self.closing.set()
        if self.stop_event is not None:
            self.stop_event.set()
        self._save_state()
        forced, tree_confirmed = False, True
        # 진행 중인 점유 HTTP의 최대 대기(연결3초+읽기15초)와 OCR 정리를 기다립니다.
        deadline = time.monotonic() + 25
        for child in self.processes:
            child.join(timeout=max(0, deadline - time.monotonic()))
        for child in self.processes:
            if child.is_alive():
                forced = True
                tree_confirmed = terminate_worker_tree(child) and tree_confirmed
        if forced:
            self.state, self.reason = "FAILED", "FORCED_STOP_REQUIRES_REVIEW"
        elif any(type(child.exitcode) is int and child.exitcode != 0 for child in self.processes):
            self.state, self.reason = "FAILED", self.reason or "CHILD_EXITED"
        elif self.state != "FAILED" and self.state != "DISABLED":
            self.state = "STOPPED"
        if forced and not tree_confirmed:
            self.state, self.reason = "FAILED", "TREE_CLEANUP_UNCONFIRMED"
        if any(child.is_alive() for child in self.processes):
            self.state, self.reason = "FAILED", "PROCESS_STILL_ALIVE"
            self._save_state()
            return
        if self.lease is not None:
            self.lease.close()
            self.lease = None
        self._save_state()


def install_parking_runtime(app, *, check_safety=True, runtime=None):
    runtime = ParkingRuntime(check_safety=check_safety) if runtime is None else runtime
    app.state.parking_runtime = runtime
    from ai_vision.safety.shared_runtime import SharedSafetyRuntime
    shared_safety = SharedSafetyRuntime(runtime)
    app.state.shared_safety_runtime = shared_safety
    previous_lifespan = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        # 2. 기존 문의·추천·화재의 수명주기를 교체하지 않고 감쌉니다.
        # 장치 충돌은 다른 감시 기능이 시작되기 전에 검사합니다.
        runtime.load_config()
        shared_safety.prepare()
        async with previous_lifespan(application) as state:
            try:
                await asyncio.to_thread(runtime.start)
                shared_safety.start()
                yield state
            finally:
                await asyncio.to_thread(shared_safety.stop)
                await asyncio.to_thread(runtime.stop)
    app.router.lifespan_context = lifespan
    app.add_api_route("/vision/parking/runtime", runtime.snapshot, methods=["GET"], tags=["Vision"])
    app.add_api_route("/vision/safety/shared-runtime", shared_safety.snapshot, methods=["GET"], tags=["Vision"])
    return runtime

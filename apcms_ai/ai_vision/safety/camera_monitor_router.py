"""통합 FastAPI(main:app)에 부착되는 화재·연기 자동감시 라우터.

개발용 기본값: Windows + APP_ENV=development 에서 로컬 웹캠 0번 자동 실행.
운영용 기본값: 비활성화. 명시적으로 SAFETY_CAMERA_AUTOSTART=1을 설정해야 실행.
실제 HTTP 전송은 기본 비활성화(DRY-RUN). 환경변수로 명시적으로 허용할 때만 활성화.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
from typing import BinaryIO
from uuid import uuid4

from fastapi import APIRouter

from ai_vision.paths import MODEL_DIR, RESULT_DIR
from ai_vision.safety.fire_alert_sender import validate_endpoint

LOGGER = logging.getLogger("ai_vision.safety.camera_monitor")


def _bool_setting(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    if value.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if value.strip().lower() in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name}에는 true/false 또는 1/0을 설정하세요.")


def _enabled() -> bool:
    # AWS/Linux나 운영 모드의 main:app을 새 코드를 배포했다는 이유만으로 시작하지 않음.
    dev_windows = os.name == "nt" and os.environ.get("APP_ENV", "development").lower() == "development"
    return _bool_setting("SAFETY_CAMERA_AUTOSTART", dev_windows)


def _camera_index() -> int:
    raw = os.environ.get("SAFETY_CAMERA_INDEX", "0")
    if not raw.isascii() or not raw.isdecimal() or not 0 <= int(raw) <= 99:
        raise ValueError("SAFETY_CAMERA_INDEX는 0~99 사이의 정수여야 합니다.")
    return int(raw)




def _delivery_options() -> tuple[list[str], str, bool]:
    """전송 승인과 입력 주소를 검증합니다. 인증키는 명령행에 넣지 않습니다."""
    if not _bool_setting("SAFETY_CAMERA_SEND_ENABLED", False):
        return [], "DRY_RUN_NO_HTTP", False

    url = os.environ.get("SAFETY_CAMERA_ALERT_URL", "").strip()
    if not url:
        raise ValueError("SAFETY_CAMERA_SEND_ENABLED=1이면 SAFETY_CAMERA_ALERT_URL이 필요합니다.")
    # 기존 송신기가 사용하는 동일한 네트워크 보호 정책.
    validate_endpoint(url)
    mode = os.environ.get("SAFETY_CAMERA_SEND_MODE", "test").strip().lower()
    if mode not in ("test", "production"):
        raise ValueError("SAFETY_CAMERA_SEND_MODE는 test 또는 production이어야 합니다.")

    token = os.environ.get("FIRE_ALERT_TOKEN", "")
    if mode == "production":
        if not _bool_setting("SAFETY_CAMERA_ALLOW_PRODUCTION", False):
            raise ValueError("운영 전송은 SAFETY_CAMERA_ALLOW_PRODUCTION=1의 별도 승인이 필요합니다.")
        if not url.startswith("https://"):
            raise ValueError("운영 이벤트 전송은 HTTPS 주소만 허용합니다.")
        if not token:
            raise ValueError("운영 전송에는 FIRE_ALERT_TOKEN 환경변수가 필요합니다.")
        return ["--send", "--allow-production-records", "--url", url], "PRODUCTION_HTTPS", True

    # localhost 모의 서버만 인증키 없는 시험을 허용합니다.
    # Spring Boot 시험 API에는 로컬이더라도 공유 인증키가 필요합니다.
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    mock_url = (parsed.hostname in ("localhost", "127.0.0.1", "::1")
                and parsed.path == "/api/mock/fire-alerts")
    if not mock_url and not token:
        raise ValueError("Spring Boot 시험 전송에는 FIRE_ALERT_TOKEN 환경변수가 필요합니다.")
    return ["--send", "--allow-test-records", "--url", url], "TEST_HTTP", False


def _acquire_lock(path: Path) -> BinaryIO | None:
    """reload/복수 Uvicorn worker 간 동일 PC의 카메라 중복 점유 방지."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        if path.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                handle.close()
                return None
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                handle.close()
                return None
        return handle
    except BaseException:
        handle.close()
        raise


def _release_lock(handle: BinaryIO | None) -> None:
    if handle is None:
        return
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _stop_tree(process: subprocess.Popen) -> None:
    """fire_alert_live 하위의 YOLO 자식 프로세스까지 종료."""
    if os.name == "nt":
        if process.poll() is None:
            # 생성 시 새 프로세스 그룹에 넣어 FastAPI 자신에게 신호가 번지지 않게 함.
            try:
                process.send_signal(signal.CTRL_BREAK_EVENT)
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if process.poll() is None:
            try:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, check=False, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                LOGGER.warning("YOLO 감시기 프로세스 트리 강제 종료 실패")
    else:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGINT)
                process.wait(timeout=5)
            except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
                pass
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        LOGGER.warning("안전감시 프로세스가 종료되지 않았습니다 (pid=%s)", process.pid)


class _Monitor:
    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.lock: BinaryIO | None = None
        self.result_dir: Path | None = None
        self.error: str | None = None
        self.enabled = False
        self.delivery = "DRY_RUN_NO_HTTP"

    def start(self) -> None:
        self.error = None
        self.result_dir = None
        self.delivery = "DRY_RUN_NO_HTTP"
        try:
            self.enabled = _enabled()
            if not self.enabled:
                LOGGER.info("화재·연기 카메라 자동감시는 설정에 따라 비활성화됨")
                return
            model_path = MODEL_DIR / "fire_smoke.pt"
            if not model_path.is_file():
                self.error = f"모델 파일 없음: {model_path}"
                LOGGER.warning("[SAFETY] %s", self.error)
                return
            index = _camera_index()
            show = _bool_setting("SAFETY_CAMERA_SHOW", os.name == "nt")
            sender_args, delivery, production = _delivery_options()
            self.delivery = delivery
            self.lock = _acquire_lock(RESULT_DIR / "safety" / "camera_autostart.lock")
            if self.lock is None:
                self.error = "다른 안전감시 프로세스가 이미 카메라를 사용 중입니다."
                LOGGER.warning("[SAFETY] %s", self.error)
                return

            self.result_dir = (RESULT_DIR / "safety" /
                               f"autostart_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}")
            args = [sys.executable, "-m", "ai_vision.safety.fire_alert_live",
                    "--output", str(self.result_dir), *sender_args, "--",
                    "--camera", str(index), "--fire-conf", "0.30", "--smoke-conf", "0.30",
                    "--max-seconds", "0", "--save-evidence"]
            if production:
                args.append("--production-camera")
            if show:
                args.append("--show")
            if os.name == "nt":
                self.process = subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                self.process = subprocess.Popen(args, start_new_session=True)
            LOGGER.warning("[SAFETY] 자동 화재·연기 감시 시작 (pid=%s, 전송=%s, 폴더=%s)",
                           self.process.pid, self.delivery, self.result_dir)
        except (OSError, ValueError) as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.delivery = "CONFIGURATION_ERROR"
            LOGGER.warning("[SAFETY] 자동감시 시작 실패: %s", self.error)
            _release_lock(self.lock)
            self.lock = None

    def stop(self) -> None:
        try:
            if self.process is not None:
                _stop_tree(self.process)
                LOGGER.info("[SAFETY] 자동감시 종료")
        finally:
            self.process = None
            _release_lock(self.lock)
            self.lock = None

    def status(self) -> dict:
        process = self.process
        running = process is not None and process.poll() is None
        return {
            "configured": self.enabled,
            "running": running,
            "delivery": self.delivery,
            "exit_code": process.poll() if process is not None and not running else None,
            "error": self.error,
            "result_dir": self.result_dir.name if self.result_dir else None,
        }


monitor = _Monitor()


@asynccontextmanager
async def _lifespan(_app):
    # APIRouter의 lifespan은 상위 FastAPI lifespan에 합쳐지며, reload 시 worker당 실행됨.
    monitor.start()
    try:
        yield
    finally:
        await asyncio.to_thread(monitor.stop)


router = APIRouter(prefix="/safety", tags=["Safety Camera"], lifespan=_lifespan)


@router.get("/camera/status")
def camera_status():
    """화재·연기 감시 프로세스의 실행 상태(실제 화재 안전 판정은 아님)."""
    return monitor.status()

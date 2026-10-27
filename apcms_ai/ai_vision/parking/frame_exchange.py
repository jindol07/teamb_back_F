"""카메라를 열지 않는 로컬 프로세스 간 최신 BGR 프레임 교환."""
import json
import logging
import math
import os
from pathlib import Path
import queue
import struct
import threading
import time
from datetime import datetime, timezone
import numpy as np

MAGIC = b"APCMSF1\n"
MAX_BYTES = 64 * 1024 * 1024


def _identity(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 128


def read_latest(path, max_age=3):
    # 1. 원자 교체된 파일 하나만 열어 메타데이터와 픽셀의 혼합을 방지합니다.
    if type(max_age) not in (int, float) or not math.isfinite(max_age) or max_age <= 0:
        raise ValueError("max_age는 양수여야 합니다.")
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
    except FileNotFoundError:
        return None
    if len(data) > MAX_BYTES or len(data) < 12 or data[:8] != MAGIC:
        raise ValueError("프레임 파일 규격 오류")
    size = struct.unpack("!I", data[8:12])[0]
    if not 0 < size <= 4096 or len(data) < 12 + size:
        raise ValueError("프레임 헤더 오류")
    try:
        meta = json.loads(data[12:12+size])
        if not isinstance(meta, dict) or type(meta.get("version")) is not int or meta["version"] != 1 or meta.get("status") not in ("FRAME", "CLOSED"):
            raise ValueError("프레임 버전/상태 오류")
        # 4. 카메라·실행 식별과 순번이 없는 입력은 분석에 전달하지 않습니다.
        if (meta.get("role") not in ("gate", "parking") or
            not _identity(meta.get("camera_id")) or not _identity(meta.get("run_id")) or
            type(meta.get("sequence")) is not int or
            meta["sequence"] < (1 if meta["status"] == "FRAME" else 0)):
            raise ValueError("프레임 식별 정보 오류")
        published = datetime.fromisoformat(meta["published_at_utc"])
        if published.tzinfo is None or published.utcoffset().total_seconds() != 0:
            raise ValueError("프레임 게시 시각은 UTC여야 합니다.")
        if meta["status"] == "CLOSED":
            if len(data) != 12 + size:
                raise ValueError("종료 상태에 픽셀이 포함됐습니다.")
            return None
        shape = meta["shape"]
        if (meta["dtype"] != "uint8" or meta["color"] != "BGR" or
            not isinstance(shape, list) or len(shape) != 3 or shape[2] != 3 or any(type(n) is not int or n <= 0 for n in shape)):
            raise ValueError("픽셀 규격 오류")
        stamp = meta["captured_monotonic"]
        if type(stamp) not in (int, float) or not math.isfinite(stamp):
            raise ValueError("프레임 시각 오류")
        age = time.monotonic() - stamp
        pixels = data[12+size:]
        if len(pixels) != math.prod(shape):
            raise ValueError("픽셀 크기 오류")
        if age < 0 or age > max_age:
            return None
        return meta, np.frombuffer(pixels, dtype=np.uint8).reshape(shape).copy()
    except (KeyError, TypeError, json.JSONDecodeError, OverflowError) as error:
        raise ValueError("프레임 메타데이터 오류") from error


class FramePublisher:
    def __init__(self, directory, role, camera_id, run_id, fps=2):
        if not _identity(camera_id) or not _identity(run_id) or role not in ("gate", "parking") or type(fps) not in (int, float) or not math.isfinite(fps) or not 0 < fps <= 10:
            raise ValueError("프레임 전달 설정 오류")
        self.path = Path(directory) / (role + ".frame")
        self.base = dict(version=1, role=role, camera_id=camera_id, run_id=run_id)
        self.interval, self.last, self.sequence = 1/fps, -math.inf, 0
        self.pending = queue.Queue(maxsize=1)
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def submit(self, frame, captured_monotonic):
        # 2. 표시/추론 전 복사하며 디스크 작업은 별도 스레드에서 합니다.
        now = time.monotonic()
        if self.stopping.is_set() or now-self.last < self.interval:
            return
        if type(captured_monotonic) not in (int, float) or not math.isfinite(captured_monotonic):
            raise ValueError("유효한 원본 촬영 시각이 필요합니다.")
        if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or frame.size == 0 or frame.nbytes > MAX_BYTES-4108:
            raise ValueError("uint8 BGR 원본 프레임이 필요합니다.")
        self.last = now
        self.sequence += 1
        item = (frame.copy(), captured_monotonic, self.sequence)
        try:
            self.pending.get_nowait()
        except queue.Empty:
            pass
        self.pending.put_nowait(item)

    def _write(self, meta, pixels=b""):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        header = json.dumps(meta, allow_nan=False).encode("utf-8")
        tmp = self.path.with_suffix(".tmp")
        try:
            with tmp.open("wb") as stream:
                stream.write(MAGIC + struct.pack("!I", len(header)) + header + pixels)
            # 5. Windows 소비자가 파일을 읽는 동안 생기는 짧은 교체 충돌만 재시도합니다.
            # 픽셀을 직접 덮어쓰지 않으며 최대 0.2초 후 실패를 기록합니다.
            for attempt in range(21):
                try:
                    os.replace(tmp, self.path)
                    break
                except PermissionError:
                    if attempt == 20:
                        raise
                    time.sleep(.01)
        finally:
            tmp.unlink(missing_ok=True)

    def _run(self):
        try:
            while not self.stopping.is_set():
                try:
                    frame, stamp, sequence = self.pending.get(timeout=.1)
                except queue.Empty:
                    continue
                try:
                    self._write(dict(self.base, status="FRAME", sequence=sequence,
                        captured_monotonic=stamp, published_at_utc=datetime.now(timezone.utc).isoformat(),
                        shape=list(frame.shape), dtype="uint8", color="BGR"), frame.tobytes())
                except Exception:
                    logging.getLogger(__name__).exception("원본 프레임 전달 실패")
        finally:
            try:
                self._write(dict(self.base, status="CLOSED", sequence=self.sequence,
                    published_at_utc=datetime.now(timezone.utc).isoformat()))
            except Exception:
                logging.getLogger(__name__).exception("프레임 종료 상태 기록 실패")

    def close(self):
        self.stopping.set()
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            logging.getLogger(__name__).warning("프레임 전달 종료 대기 초과; 입력 만료로 확인 필요")

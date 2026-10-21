# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/latest_frame_capture.py

"""카메라 읽기를 별도 스레드에서 이어가며 대기 프레임은 최신 한 장만 유지합니다."""

import math
import threading
import time


class LatestFrameCapture:
    def __init__(self, capture, reader=None, read_timeout=5, close_timeout=2, max_frame_bytes=32 * 1024 * 1024):
        # 1. 대기 시간·메모리를 제한합니다. OCR·차량 추적을 병렬화하는 클래스는 아닙니다.
        for value in (read_timeout, close_timeout):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 30:
                raise ValueError("카메라 대기 시간은 0초 초과 30초 이하로 지정하세요.")
        if type(max_frame_bytes) is not int or max_frame_bytes < 1:
            raise ValueError("프레임 메모리 한도를 확인하세요.")
        self._capture, self._reader = capture, time.monotonic if reader is None else reader
        self._read_timeout, self._close_timeout, self._budget = read_timeout, close_timeout, max_frame_bytes
        self._condition = threading.Condition()
        self._thread = None
        self._stop, self._ended, self._error = False, False, None
        self._latest, self._last_timestamp = None, None
        self.captured_monotonic = None
        self._captured = self._delivered = self._dropped = self._peak = 0
        self._duplicate_times = 0
        self._opened = bool(capture.isOpened())

    def isOpened(self):
        return self._opened and not self._stop

    def _collect(self):
        try:
            while True:
                with self._condition:
                    if self._stop:
                        break
                ok, frame = self._capture.read()
                if not ok:
                    break
                # 2. 카메라 읽기 직후의 시각을 저장합니다.
                timestamp = self._reader()
                import numpy as np
                if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or
                        frame.shape[2] != 3 or not 0 < frame.nbytes <= self._budget):
                    raise ValueError("카메라 프레임 형식 또는 메모리 한도를 확인하세요.")
                if (type(timestamp) not in (int, float) or not math.isfinite(timestamp) or timestamp < 0 or
                        (self._last_timestamp is not None and timestamp < self._last_timestamp)):
                    raise ValueError("카메라 수집 시각이 유효하지 않거나 역행했습니다.")
                if timestamp == self._last_timestamp:
                    # Windows 시계 해상도 때문에 연속 read의 시각이 같을 수 있습니다.
                    # 가짜 시각을 만들지 않고 해당 프레임만 제외하며 수집은 계속합니다.
                    with self._condition:
                        if self._stop:
                            break
                        self._captured += 1
                        self._dropped += 1
                        self._duplicate_times += 1
                        self._condition.notify_all()
                    continue
                # 드라이버가 다음 read에서 버퍼를 재사용해도 저장한 화면은 바뀌지 않습니다.
                owned = frame.copy()
                with self._condition:
                    if self._stop:
                        break
                    self._last_timestamp = timestamp
                    self._captured += 1
                    self._dropped += self._latest is not None
                    self._latest = (owned, timestamp)
                    self._peak = max(self._peak, owned.nbytes)
                    self._condition.notify_all()
        except Exception as error:
            with self._condition:
                self._error = type(error).__name__
        finally:
            # 3. 카메라를 읽는 스레드가 직접 해제하여 read/release 동시 호출을 피합니다.
            try:
                self._capture.release()
            except Exception as error:
                with self._condition:
                    self._error = type(error).__name__
            with self._condition:
                self._ended = True
                self._condition.notify_all()

    def read(self):
        with self._condition:
            if self._stop:
                return False, None
            if not self._opened:
                return False, None
            if self._thread is None:
                # 세션 시계가 만들어진 뒤 첫 read에서 수집을 시작합니다.
                self._thread = threading.Thread(target=self._collect, name="vision-camera-capture", daemon=True)
                self._thread.start()
            if not self._condition.wait_for(lambda: self._latest is not None or self._ended or self._stop,
                                            timeout=self._read_timeout):
                raise TimeoutError("카메라 프레임 수신 제한 시간을 초과했습니다.")
            if self._error:
                raise RuntimeError("카메라 수집 스레드에서 오류가 발생했습니다.")
            if self._stop or self._latest is None:
                return False, None
            frame, self.captured_monotonic = self._latest
            self._latest = None
            self._delivered += 1
            return True, frame

    def release(self):
        # 4. 네이티브 드라이버의 멈춘 read를 강제로 끊을 수는 없습니다. 실패를 보고합니다.
        with self._condition:
            if self._stop and (self._thread is None or not self._thread.is_alive()):
                return
            self._stop = True
            self._dropped += self._latest is not None
            self._latest = None
            self._condition.notify_all()
        if self._thread is None:
            self._capture.release()
        else:
            self._thread.join(self._close_timeout)
            if self._thread.is_alive():
                raise TimeoutError("카메라 읽기가 끝나지 않아 수집 스레드를 해제하지 못했습니다.")
            if self._error:
                raise RuntimeError("카메라 수집 또는 해제 오류를 확인하세요.")

    def summary(self):
        with self._condition:
            return {"mode": "LATEST_FRAME_ONLY", "captured_frames": self._captured,
                    "delivered_frames": self._delivered, "dropped_frames": self._dropped,
                    "peak_pending_bytes": self._peak, "worker_alive": self._thread is not None and self._thread.is_alive(),
                    "duplicate_timestamp_frames": self._duplicate_times,
                    "worker_error": self._error}

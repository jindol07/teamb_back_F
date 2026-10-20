# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/recognition_admission.py

"""대기열 없이 동시 인식 요청을 제한하고 작업 완료 시 슬롯을 반환합니다."""

import threading


class RecognitionAdmission:
    def __init__(self, capacity=2):
        if type(capacity) is not int or not 1 <= capacity <= 16:
            raise ValueError("동시 인식 요청 수는 1~16 정수여야 합니다.")
        self._slots = threading.BoundedSemaphore(capacity)

    def try_acquire(self):
        # 1. 기다리는 요청을 쌓지 않고 즉시 수락 여부를 결정합니다.
        if not self._slots.acquire(blocking=False):
            return None
        return _RecognitionLease(self._slots)


class _RecognitionLease:
    def __init__(self, slots):
        self._slots, self._state, self._lock = slots, "PENDING", threading.Lock()

    def cancel_pending(self):
        # 2. 읽기 오류·취소 등으로 작업을 시작하지 않은 슬롯만 반환합니다.
        with self._lock:
            if self._state != "PENDING":
                return False
            self._state = "RELEASED"
            self._slots.release()
            return True

    def run(self, operation, *args, **kwargs):
        with self._lock:
            if self._state != "PENDING":
                raise RuntimeError("취소되었거나 이미 시작된 인식 작업입니다.")
            self._state = "RUNNING"
        try:
            return operation(*args, **kwargs)
        finally:
            # 3. 요청 코루틴이 취소돼도 실행 중인 작업이 끝나기 전에는 슬롯을 열지 않습니다.
            with self._lock:
                self._state = "RELEASED"
                self._slots.release()

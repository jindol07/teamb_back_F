# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/async_gate_processor.py

"""추적은 호출 스레드에 두고 통과 차량의 OCR만 한 작업 스레드에 맡깁니다."""

from collections import deque
from concurrent.futures import ThreadPoolExecutor, CancelledError
import threading


class AsyncGateProcessor:
    def __init__(self, processor, max_pending=2, max_pending_bytes=32 * 1024 * 1024):
        if type(max_pending) is not int or not 1 <= max_pending <= 2:
            raise ValueError("대기 OCR 작업은 실행 중 작업을 포함해 1~2개로 제한합니다.")
        if type(max_pending_bytes) is not int or max_pending_bytes < 1:
            raise ValueError("대기 OCR 이미지 메모리 한도를 확인하세요.")
        self.processor = processor
        self._limit, self._budget = max_pending, max_pending_bytes
        self._pending, self._bytes = deque(), 0
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vision-ocr")
        self._cancel = threading.Event()
        self._closed = False
        self._submitted = self._completed = self._dropped = self._abandoned = self._peak = 0
        self._errors = []

    @property
    def dropped_crops(self):
        return self.processor.dropped_crops

    @property
    def dropped_tracks(self):
        return self.processor.dropped_tracks

    def prepare(self):
        self.processor.prepare()

    def submit_frame(self, frame, stamp, session):
        if self._closed:
            raise ValueError("종료된 OCR 처리기입니다.")
        # 1. 차량 추적·통과 판정은 메인 스레드에서 계속 실행합니다.
        jobs = self.processor.collect(frame, stamp, minimum_frame_index=session.clock.oldest_frame_index)
        for job in jobs:
            size = sum(entry["crop"].nbytes for entry in job["entries"])
            if len(self._pending) >= self._limit or self._bytes + size > self._budget:
                # 오래 기다린 차량을 무한히 쌓지 않습니다. 누락 건수는 결과에 명시합니다.
                self._dropped += 1
                continue
            indices = [stamp.frame_index] + [entry["frame_index"] for entry in job["entries"]]
            token = session.clock.retain(indices)
            try:
                future = self._executor.submit(self.processor.recognize, job, self._cancel.is_set)
            except Exception:
                session.clock.release_retained(token)
                raise
            self._pending.append((future, stamp, session.clock, token, size))
            self._bytes += size
            self._peak = max(self._peak, self._bytes)
            self._submitted += 1

    def completed(self):
        # 2. 제출 순서로만 결과를 꺼내 원래 통과 시각의 순서를 유지합니다.
        while self._pending and self._pending[0][0].done():
            future, stamp, clock, token, size = self._pending.popleft()
            try:
                try:
                    passage = future.result()
                except Exception as error:
                    self._errors.append(type(error).__name__)
                    raise
                self._completed += 1
                # consume이 원본 표본 시각을 검증할 때까지 보관을 유지합니다.
                yield passage, stamp
            finally:
                clock.release_retained(token)
                self._bytes -= size

    def statistics(self):
        return self.processor.statistics()

    def summary(self):
        return {"mode": "SINGLE_OCR_WORKER", "submitted_jobs": self._submitted,
                "completed_jobs": self._completed, "dropped_jobs": self._dropped,
                "abandoned_jobs": self._abandoned, "pending_jobs": len(self._pending),
                "peak_pending_bytes": self._peak, "worker_error_types": list(self._errors),
                "closed": self._closed}

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._cancel.set()
        # 3. 시작 전 작업을 취소하고 실행 중 요청이 돌아올 때까지 기다립니다.
        # 작업 스레드는 OCR만 수행하며 Boot 전송이나 세션 판정을 실행하지 않습니다.
        self._executor.shutdown(wait=True, cancel_futures=True)
        late_error = False
        while self._pending:
            future, _, clock, token, _ = self._pending.popleft()
            self._abandoned += 1
            if not future.cancelled():
                error = future.exception()
                if error is not None and not isinstance(error, CancelledError):
                    self._errors.append(type(error).__name__)
                    late_error = True
            clock.release_retained(token)
        self._bytes = 0
        self.processor.close()
        if late_error:
            raise RuntimeError("종료 대기 중 OCR 작업 오류가 확인됐습니다.")

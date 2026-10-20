# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/run_live_gate.py

"""카메라 세션의 추적·OCR 루프. 실행 도구에서는 실제 HTTP를 활성화하지 않습니다."""

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.live_gate_clock import LiveGateClock
from ai_vision.recognition.live_gate_processor import LiveGateProcessor
from ai_vision.recognition.live_gate_session import LiveGateSession
from ai_vision.recognition.live_gate_lifecycle import close_resources
from ai_vision.recognition.live_gate_storage import save_failure
from ai_vision.recognition.live_gate_metrics import LiveGateMetrics
from ai_vision.recognition.live_gate_context import build_run_context
from ai_vision.recognition.live_gate_deadline import LiveGateDeadline
from ai_vision.recognition.local_io import read_json, write_json_atomic
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.tracking_config import validate_config


def execute(capture, processor, session, seconds=20, max_frames=100000, monotonic_reader=None, performance_reader=None,
            allow_source_end=False, deadline_reader=None):
    reader = time.monotonic if monotonic_reader is None else monotonic_reader
    metrics = LiveGateMetrics(performance_reader)
    stop_reason, status, results, cleanup_errors, error_type = "FRAME_LIMIT", "STOPPED", [], 0, None
    capture_failure = None
    deadline = None
    try:
        if (isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 < seconds <= 300 or
                type(max_frames) is not int or not 1 <= max_frames <= 100000 or type(allow_source_end) is not bool):
            raise ValueError("실행 제한을 확인해 주세요.")
        deadline = LiveGateDeadline(seconds, deadline_reader)
        capture_failure = "CAMERA_OPEN_FAILED"
        if not capture.isOpened():
            raise ValueError("카메라를 열 수 없습니다.")
        capture_failure = None
        for index in range(max_frames):
            # OCR 처리 중 제한을 넘겼다면 다음 카메라 read를 시작하지 않습니다.
            if deadline.before_read():
                stop_reason = "TIME_LIMIT"
                break
            capture_failure = "CAMERA_READ_FAILED"
            with metrics.measure("read"):
                ok, frame = capture.read()
            if not ok:
                # 물리 카메라에는 파일 EOF가 없으므로 읽기 종료를 정상 완료로 숨기지 않습니다.
                if not allow_source_end:
                    capture_failure = "CAMERA_READ_FAILED"
                    raise ValueError("카메라 프레임을 읽을 수 없습니다.")
                stop_reason = "CAMERA_READ_ENDED"
                break
            capture_failure = None
            # 1. 파일 FPS가 아니라 카메라 read 직후의 세션 시각을 고정합니다.
            stamp = session.capture(index, reader())
            metrics.record_frame(stamp.elapsed_seconds)
            if stamp.elapsed_seconds >= seconds:
                stop_reason = "TIME_LIMIT"
                break
            with metrics.measure("process"):
                # 시각 보관 한도가 OCR의 2초 창보다 먼저 줄어들어도 오래된 표본을 쓰지 않습니다.
                if isinstance(processor, LiveGateProcessor):
                    passages = processor.process(frame, stamp, minimum_frame_index=session.clock.oldest_frame_index)
                else:
                    passages = processor.process(frame, stamp)
                for passage in passages:
                    if len(results) >= 10000:
                        raise ValueError("결과 보관 한도에 도달했습니다.")
                    decision = session.consume(passage, stamp)
                    results.append({**decision, "captured_at": stamp.captured_at.isoformat(),
                                    "crossing_elapsed_seconds": stamp.elapsed_seconds,
                                    "plate_consensus": passage["plate_consensus"], "sample_count": len(passage["samples"])})
    except KeyboardInterrupt:
        stop_reason = "USER_INTERRUPTED"
    except Exception as error:
        status, stop_reason = "FAILED", capture_failure or "CAPTURE_OR_PROCESSING_FAILED"
        error_type = type(error).__name__
    finally:
        # 2. 카메라 읽기·OCR·후보 처리 중 실패해도 모든 자원을 정리합니다.
        cleanup_errors = close_resources(capture, processor, session)
        if cleanup_errors:
            status = "FAILED"
    return {**session.summary(), "status": status, "stop_reason": stop_reason, "error_type": error_type, "cleanup_errors": cleanup_errors,
            "dropped_crops": getattr(processor, "dropped_crops", 0), "dropped_tracks": getattr(processor, "dropped_tracks", 0),
            "performance": metrics.summary(), "source_end_expected": allow_source_end,
            "deadline": deadline.summary() if deadline is not None else None,
            "processor_statistics": processor.statistics() if isinstance(processor, LiveGateProcessor) else None,
            "results": results}


def _demo():
    class Capture:
        index = 0

        def isOpened(self):
            return True

        def read(self):
            self.index += 1
            return (True, object()) if self.index <= 3 else (False, None)

        def release(self):
            pass

    class Processor:
        def process(self, frame, stamp):
            if stamp.frame_index != 2:
                return []
            samples = [{"frame_index": index, "video_seconds": seconds, "plate_number": "91소6408",
                        "plate_type": "KOREAN_VALID", "plate_detection_confidence": .8} for index, seconds in ((0, 0), (1, .3))]
            return [{"record_type": "LIVE_TRACKED_PASSAGE", "http_enabled": False, "track_id": 1,
                     "screen_direction": "DOWN", "crossing_video_seconds": stamp.elapsed_seconds,
                     "samples": samples, "plate_consensus": summarize_plate_samples(samples)}]

        def close(self):
            pass

    clock = LiveGateClock(datetime(2020, 1, 1, tzinfo=timezone.utc), 0)
    session = LiveGateSession("SIMULATION_ONLY", "ENTRY", clock=clock)
    report = execute(Capture(), Processor(), session, monotonic_reader=iter((0, .3, .6)).__next__, allow_source_end=True)
    return {**report, "uses_synthetic_source": True,
            "run_context": build_run_context(None, None, synthetic=True)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--camera-id")
    parser.add_argument("--down-direction", choices=["ENTRY", "EXIT"])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    if output.is_relative_to((RESULT_DIR / "recognition").resolve()):
        parser.error("영상 분석 원본 폴더 밖에 새 세션 폴더를 지정해 주세요.")
    if not 0 < args.seconds <= 300 or not 0 <= args.camera_index <= 32:
        parser.error("실행 길이는 최대 300초, 카메라 번호는 0~32로 지정합니다.")
    session, processor, capture, output_created = None, None, None, False
    report, phase, execution_finished = None, "INITIALIZATION", False
    try:
        if not args.demo:
            if args.config is None or args.camera_id is None or args.down_direction is None:
                raise ValueError("카메라 ID·방향·해당 구도의 설정이 필요합니다.")
            config = validate_config(read_json(args.config))
            context = build_run_context(config, args.camera_index, args.seconds)
            session = LiveGateSession(args.camera_id, args.down_direction)
            processor = LiveGateProcessor(config)
        else:
            context = build_run_context(None, None, synthetic=True)
        output.mkdir(parents=True, exist_ok=False)
        output_created = True
        write_json_atomic(output / "summary.json", {"record_type": "LIVE_GATE_SESSION", "status": "RUNNING",
                          "http_enabled": False, "run_context": context})
        phase = "EXECUTION"
        if args.demo:
            report = _demo()
        else:
            # 파일 경로·URL을 받지 않고 물리 카메라 정수 인덱스만 엽니다.
            import cv2
            capture = cv2.VideoCapture(args.camera_index)
            report = {**execute(capture, processor, session, seconds=args.seconds), "uses_synthetic_source": False}
        report = {**report, "run_context": context}
        execution_finished = True
        phase = "FINAL_SAVE"
        write_json_atomic(output / "summary.json", report)
    except (Exception, KeyboardInterrupt) as error:
        # 3. execute가 정리한 자원은 다시 닫지 않고, 초기화 도중의 자원만 정리합니다.
        cleanup_errors = 0 if execution_finished else close_resources(capture, processor, session)
        saved = []
        if output_created:
            saved = save_failure(output, phase, error, cleanup_errors, report)
        evidence = ", ".join(saved) if saved else "별도 실패 기록 저장 불가"
        parser.exit(1, f"카메라 세션 실행 실패 ({phase}): {evidence}. 기존 summary.json을 확인해 주세요.\n")
    print(f"세션 종료: {report['status']} / 프레임 {report['captured_frames']} / 통과 자료 {report['processed_passages']} / HTTP 비활성")
    if report["status"] == "FAILED":
        parser.exit(1)


if __name__ == "__main__":
    main()

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/run_live_gate.py

"""카메라 세션의 추적·OCR 루프. 명시적으로 설정한 경우에만 Boot로 전송합니다."""

import argparse
import itertools
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from ai_vision.paths import BASE_DIR, RESULT_DIR
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
from ai_vision.recognition.plate_review import sample_review_reasons
from ai_vision.recognition.tracking_config import validate_config
from ai_vision.recognition.vehicle_http import VehicleHTTPClient
from ai_vision.recognition.vehicle_delivery_flow import VehicleDeliveryFlow
from ai_vision.recognition.vehicle_contract import validate_camera_id
from ai_vision.recognition.latest_frame_capture import LatestFrameCapture
from ai_vision.recognition.async_gate_processor import AsyncGateProcessor


def _create_http_client(enabled, context_url=None, env_file=None):
    # 1. 기본 실행에서는 설정 파일·키를 읽지 않고 비활성 클라이언트를 반환합니다.
    if not enabled:
        return VehicleHTTPClient()
    from dotenv import dotenv_values
    settings = dotenv_values(BASE_DIR.parent / ".env" if env_file is None else env_file,
                             encoding="utf-8-sig", interpolate=False)
    # 2. 명령의 주소 > 운영체제 환경변수 > 프로젝트 .env 순서로 선택합니다.
    # 빈 환경변수도 명시적인 설정으로 취급하여 다른 키로 조용히 바꾸지 않습니다.
    url = context_url if context_url is not None else os.environ.get("VISION_BOOT_CONTEXT_URL", settings.get("VISION_BOOT_CONTEXT_URL"))
    key = os.environ.get("AI_OCCUPANCY_API_KEY", settings.get("AI_OCCUPANCY_API_KEY"))
    return VehicleHTTPClient(context_url=url, api_key=key, enabled=True)


def execute(capture, processor, session, seconds=20, max_frames=100000, monotonic_reader=None, performance_reader=None,
            allow_source_end=False, deadline_reader=None, preview=None, start_cancelled=False, stop_event=None, runtime_mode=False, on_frame=None, on_raw_frame=None):
    reader = time.monotonic if monotonic_reader is None else monotonic_reader
    metrics = LiveGateMetrics(performance_reader)
    stop_reason, status, results, cleanup_errors, error_type = "FRAME_LIMIT", "STOPPED", [], 0, None
    capture_failure = None
    deadline = None

    def record_result(passage, origin_stamp):
        # 비동기 결과도 완료 시각이 아니라 실제 통과 프레임 시각으로 검증·기록합니다.
        if len(results) >= 10000:
            raise ValueError("결과 보관 한도에 도달했습니다.")
        decision = session.consume(passage, origin_stamp)
        results.append({**decision, "captured_at": origin_stamp.captured_at.isoformat(),
                        "crossing_elapsed_seconds": origin_stamp.elapsed_seconds,
                        "plate_consensus": passage["plate_consensus"], "sample_count": len(passage["samples"]),
                        "review_reasons": sample_review_reasons(passage["samples"])})
        # 운영 중 전송 실패·처리 불명확 상태는 카메라만 정상처럼 계속 돌리지 않습니다.
        if runtime_mode and decision.get("receipt_state") in ("DELIVERY_UNKNOWN", "AUTH_REQUIRED", "REJECTED"):
            raise RuntimeError("입출차 전송 결과를 확인해야 합니다.")
        if preview is not None:
            summary = passage['plate_consensus']
            print(f"통과 차량 {passage['track_id']} / 화면 방향 {passage['screen_direction']} / 번호판 {summary['plate_number'] or '미확정'} / 합의 {summary['status']} / 전송 판단 {decision['decision']}", flush=True)
    try:
        if (isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 < seconds <= 300 or
                type(max_frames) is not int or not 1 <= max_frames <= 100000 or type(allow_source_end) is not bool or
                type(start_cancelled) is not bool):
            raise ValueError("실행 제한을 확인해 주세요.")
        deadline = None if runtime_mode else LiveGateDeadline(seconds, deadline_reader)
        capture_failure = "CAMERA_OPEN_FAILED"
        if not capture.isOpened():
            raise ValueError("카메라를 열 수 없습니다.")
        capture_failure = None
        if start_cancelled:
            stop_reason = "USER_INTERRUPTED"
        for index in (() if start_cancelled else (itertools.count() if runtime_mode else range(max_frames))):
            # 운영은 서버 종료 요청을 프레임 읽기 전에 확인합니다.
            if stop_event is not None and stop_event.is_set():
                stop_reason = "SERVER_SHUTDOWN"
                break
            # 처리 중 제한을 넘겼다면 다음 프레임 수신을 시작하지 않습니다.
            # 별도 수집 모드의 물리 카메라는 finally에서 정리할 때까지 읽을 수 있습니다.
            if deadline is not None and deadline.before_read():
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
            # 별도 수집 모드에서는 처리 시작 시각 대신 실제 카메라 읽기 직후 시각을 사용합니다.
            captured_time = capture.captured_monotonic if isinstance(capture, LatestFrameCapture) else reader()
            if on_raw_frame is not None:
                on_raw_frame(frame, captured_time)
            stamp = session.capture(index, captured_time)
            metrics.record_frame(stamp.elapsed_seconds)
            if not runtime_mode and stamp.elapsed_seconds >= seconds:
                stop_reason = "TIME_LIMIT"
                break
            if preview is not None and not preview(frame):
                stop_reason = "USER_INTERRUPTED"
                break
            with metrics.measure("process"):
                # 시각 보관 한도가 OCR의 2초 창보다 먼저 줄어들어도 오래된 표본을 쓰지 않습니다.
                if isinstance(processor, AsyncGateProcessor):
                    # 제출 전 완료 작업을 비워 제한된 대기 공간을 재사용합니다.
                    for passage, origin_stamp in processor.completed():
                        record_result(passage, origin_stamp)
                    processor.submit_frame(frame, stamp, session)
                    for passage, origin_stamp in processor.completed():
                        record_result(passage, origin_stamp)
                elif isinstance(processor, LiveGateProcessor):
                    passages = processor.process(frame, stamp, minimum_frame_index=session.clock.oldest_frame_index)
                else:
                    passages = processor.process(frame, stamp)
                if not isinstance(processor, AsyncGateProcessor):
                    for passage in passages:
                        record_result(passage, stamp)
            if on_frame is not None:
                on_frame()
    except KeyboardInterrupt:
        stop_reason = "USER_INTERRUPTED"
    except Exception as error:
        status, stop_reason = "FAILED", capture_failure or "CAPTURE_OR_PROCESSING_FAILED"
        error_type = type(error).__name__
    finally:
        # 2. 카메라 읽기·OCR·후보 처리 중 실패해도 모든 자원을 정리합니다.
        # OCR 종료 대기가 길어져도 미리보기 창은 먼저 닫습니다.
        if preview is not None:
            try:
                preview.close()
            except Exception:
                cleanup_errors += 1
        cleanup_errors += close_resources(capture, processor, session)
        if cleanup_errors:
            status = "FAILED"
    return {**session.summary(), "status": status, "stop_reason": stop_reason, "error_type": error_type, "cleanup_errors": cleanup_errors,
            "dropped_crops": getattr(processor, "dropped_crops", 0), "dropped_tracks": getattr(processor, "dropped_tracks", 0),
            "performance": metrics.summary(), "source_end_expected": allow_source_end,
            "deadline": deadline.summary() if deadline is not None else None,
            "processor_statistics": processor.statistics() if isinstance(processor, (LiveGateProcessor, AsyncGateProcessor)) else None,
            "async_ocr": processor.summary() if isinstance(processor, AsyncGateProcessor) else None,
            "capture_buffer": capture.summary() if isinstance(capture, LatestFrameCapture) else None,
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


def main(argv=None, *, stop_event=None, runtime_mode=False, camera_backend="default", on_frame=None, on_raw_frame=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--enable-http", action="store_true", help="실제 카메라의 확정 후보를 Boot로 전송")
    parser.add_argument('--single-vehicle-handoff', action='store_true', help='한 대 시연용 신원 파일을 새 세션 폴더에 기록')
    parser.add_argument("--boot-context-url", help="관리자 Boot context URL. 키는 AI_OCCUPANCY_API_KEY 환경변수 사용")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--tracking-target", choices=("vehicle", "plate"), default="vehicle",
                        help="기준선 통과 추적 대상. 종이 시연에서는 plate를 명시")
    parser.add_argument("--tracking-imgsz", type=int, choices=(640, 960, 1280),
                        help="번호판 추론 크기. 미지정 시 plate 1280, vehicle 640 유지")
    parser.add_argument("--vision-api-url", help="지정하면 차량 추적은 현장 PC, 번호판 인식은 해당 Vision API에서 수행")
    parser.add_argument("--buffered-capture", action="store_true", help="별도 스레드에서 최신 프레임 한 장만 유지. OCR 중 추적은 계속 멈춥니다")
    parser.add_argument("--async-ocr", action="store_true", help="원격 OCR을 별도 작업으로 처리하고 차량 추적을 계속 수행")
    parser.add_argument("--preview", action="store_true", help="ROI·통과선을 실시간 표시. 창에서 Q로 종료")
    parser.add_argument("--camera-id")
    parser.add_argument("--down-direction", choices=["ENTRY", "EXIT"])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.tracking_imgsz is not None and (args.tracking_target != "plate" or args.demo):
        parser.error("추론 크기는 실제 번호판 추적 모드에서만 지정합니다.")
    if args.tracking_target == "plate" and args.vision_api_url is not None:
        parser.error("번호판 직접 추적은 현재 로컬 OCR에서만 지원합니다.")
    if args.demo and args.tracking_target != "vehicle":
        parser.error("합성 데모에서는 추적 대상을 변경하지 않습니다.")
    if args.single_vehicle_handoff and (args.demo or not args.enable_http):
        parser.error('한 대 시연 신원 전달은 실제 입출차 HTTP 모드에서만 사용합니다.')
    if args.demo and (args.enable_http or args.boot_context_url is not None or args.vision_api_url is not None or args.buffered_capture or args.async_ocr or args.preview):
        parser.error("합성 데모에서는 실제 전송 옵션을 사용할 수 없습니다.")
    if args.async_ocr and args.vision_api_url is None:
        parser.error("비동기 OCR은 --vision-api-url을 지정한 원격 모드에서 사용합니다.")
    if args.boot_context_url is not None and not args.enable_http:
        parser.error("관리자 서버 주소를 사용하려면 --enable-http를 명시합니다.")
    output = args.output_dir.resolve()
    if output.is_relative_to((RESULT_DIR / "recognition").resolve()):
        parser.error("영상 분석 원본 폴더 밖에 새 세션 폴더를 지정해 주세요.")
    if not 0 < args.seconds <= 300 or not 0 <= args.camera_index <= 32:
        parser.error("실행 길이는 최대 300초, 카메라 번호는 0~32로 지정합니다.")
    session, processor, capture, preview, output_created = None, None, None, None, False
    report, phase, execution_finished = None, "INITIALIZATION", False
    try:
        if not args.demo:
            if args.config is None or args.camera_id is None or args.down_direction is None:
                raise ValueError("카메라 ID·방향·해당 구도의 설정이 필요합니다.")
            config = validate_config(read_json(args.config))
            context = build_run_context(config, args.camera_index, args.seconds)
            # 1. 전송을 명시한 실행만 키를 읽습니다. 키·주소는 요약 파일에 저장하지 않습니다.
            client = _create_http_client(args.enable_http, args.boot_context_url)
            remote_reader = None
            if args.vision_api_url is not None:
                from ai_vision.recognition.remote_plate_reader import RemotePlateReader
                remote_reader = RemotePlateReader(args.vision_api_url)
            validate_camera_id(args.camera_id)
            # 저장할 수 없는 실행은 무거운 모델 준비 전에 중단합니다.
            output.mkdir(parents=True, exist_ok=False)
            output_created = True
            if args.preview:
                from ai_vision.recognition.preview_gate_config import LiveGatePreview
                preview = LiveGatePreview(config, args.down_direction)
            processor_options = {"plate_reader": remote_reader.read} if remote_reader else {}
            if args.tracking_target != "vehicle":
                processor_options["tracking_target"] = args.tracking_target
            if args.tracking_imgsz is not None:
                processor_options["tracking_imgsz"] = args.tracking_imgsz
            processor = LiveGateProcessor(config, **processor_options)
            if args.async_ocr:
                processor = AsyncGateProcessor(processor)
            print("차량 추적 모델 준비 중입니다. 번호판 인식은 원격 API를 사용합니다." if remote_reader else
                  "차량·번호판·OCR 모델 준비 중입니다. 아직 카메라 수집은 시작하지 않았습니다.", flush=True)
            processor.prepare()
        else:
            context = build_run_context(None, None, synthetic=True)
            output.mkdir(parents=True, exist_ok=False)
            output_created = True
        write_json_atomic(output / "summary.json", {"record_type": "LIVE_GATE_SESSION", "status": "RUNNING",
                          "http_enabled": client.enabled if not args.demo else False, "run_context": context,
                          "recognition_mode": "REMOTE_API" if args.vision_api_url else "LOCAL"})
        phase = "EXECUTION"
        if args.demo:
            report = _demo()
        else:
            # 파일 경로·URL을 받지 않고 물리 카메라 정수 인덱스만 엽니다.
            import cv2
            from ai_vision.camera_runtime import open_camera
            capture = open_camera(args.camera_index, camera_backend) if runtime_mode else cv2.VideoCapture(args.camera_index)
            # 준비 화면은 별도 수집 스레드와 세션 시계보다 먼저 사용합니다.
            # 준비 프레임이 측정 세션에 섞이거나 오래된 시각으로 전달되지 않게 합니다.
            ready = preview.wait_until_ready(capture) if preview is not None and not runtime_mode else True
            if args.buffered_capture:
                capture = LatestFrameCapture(capture)
            # 카메라 생성에 걸린 시간도 촬영 시간과 프레임 시각에서 제외합니다.
            session = LiveGateSession(args.camera_id, args.down_direction, flow=VehicleDeliveryFlow(client),
                                      handoff_path=output/'single_vehicle_handoff.json' if args.single_vehicle_handoff else None)
            options = {"preview": preview} if preview is not None else {}
            if not ready:
                options["start_cancelled"] = True
            report = {**execute(capture, processor, session, seconds=args.seconds, stop_event=stop_event, runtime_mode=runtime_mode, on_frame=on_frame, on_raw_frame=on_raw_frame, **options), "uses_synthetic_source": False}
        # 서버 주소·키는 결과에 남기지 않고 인식 위치만 구분합니다.
        report = {**report, "runtime_mode": runtime_mode, "run_context": context, "recognition_mode": "REMOTE_API" if args.vision_api_url else "LOCAL",
                  "tracking_target": args.tracking_target,
                  "tracking_imgsz": args.tracking_imgsz if args.tracking_imgsz is not None else (1280 if args.tracking_target == "plate" else 640)}
        execution_finished = True
        phase = "FINAL_SAVE"
        write_json_atomic(output / "summary.json", report)
    except (Exception, KeyboardInterrupt) as error:
        # 3. execute가 정리한 자원은 다시 닫지 않고, 초기화 도중의 자원만 정리합니다.
        cleanup_errors = 0
        if not execution_finished:
            if preview is not None:
                try:
                    preview.close()
                except Exception:
                    cleanup_errors += 1
            cleanup_errors += close_resources(capture, processor, session)
        saved = []
        if output_created:
            saved = save_failure(output, phase, error, cleanup_errors, report)
        evidence = ", ".join(saved) if saved else "별도 실패 기록 저장 불가"
        parser.exit(1, f"카메라 세션 실행 실패 ({phase}): {evidence}. 기존 summary.json을 확인해 주세요.\n")
    http_state = "활성" if report["http_enabled"] else "비활성"
    print(f"세션 종료: {report['status']} / 프레임 {report['captured_frames']} / 통과 자료 {report['processed_passages']} / HTTP {http_state} / 요청 시도 {report['request_attempts']}회")
    if report.get("async_ocr"):
        jobs = report["async_ocr"]
        print(f"OCR 작업: 제출 {jobs['submitted_jobs']} / 완료 {jobs['completed_jobs']} / 한도 초과 {jobs['dropped_jobs']} / 종료 시 미반영 {jobs['abandoned_jobs']}")
    if report["status"] == "FAILED":
        parser.exit(1)


if __name__ == "__main__":
    main()

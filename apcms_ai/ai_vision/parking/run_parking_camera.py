# D:/finalProjectB/back/apcms_ai/ai_vision/parking/run_parking_camera.py
"""USB 웹캠 점유 검사와 명시적으로 허용한 구획의 Boot 전송을 실행합니다."""

import argparse
import math
import time
import os
from datetime import datetime, timezone, timedelta
from ai_vision.recognition.vehicle_delivery_flow import SpaceMatchDeliveryFlow
from ai_vision.recognition.vehicle_live_candidate import create_space_match_candidate
from pathlib import Path
import cv2
from ai_vision.camera_runtime import open_camera, CAMERA_BACKENDS, validate_camera_backend
from ai_vision.parking.parking_preview import ParkingPreview
from ai_vision.parking.parking_processor import ParkingOccupancyProcessor
from ai_vision.parking.parking_realtime import detect_spaces
from ai_vision.recognition.local_io import read_json, write_json_atomic
from ai_vision.parking.parking_delivery import ParkingDelivery, ParkingDeliveryWorker, delivery_settings, check_previous_report
from ai_vision.parking.inspect_parking_camera import checkpoint, deliver_changes
from ai_vision.parking.parking_calibration import load_reference, configure_resolution
from ai_vision.recognition.latest_frame_capture import LatestFrameCapture


def run_camera(reference_path, config_path, output_dir, camera_index=0, seconds=60, preview=True,
               enable_http=False, allowed_codes=(), environment=None, previous_report=None,
               publish_results=False, camera_backend='default', track_vehicles=False,
               vehicle_tracker=None, plate_reader=None, enable_space_http=False, camera_id=None, enable_space_release_http=False, tracking_target='vehicle', ocr_execution='auto', tracking_imgsz=None, handoff_path=None):
    # 1. 저장 경로와 입력을 먼저 확인하여 기존 운영 결과를 보호합니다.
    if type(camera_index) is not int or not 0 <= camera_index <= 99:
        raise ValueError('카메라 번호는 0~99 정수여야 합니다.')
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 < seconds <= 300:
        raise ValueError('측정 시간은 0초 초과 300초 이하여야 합니다.')
    if (type(track_vehicles) is not bool or
            (not track_vehicles and (vehicle_tracker is not None or plate_reader is not None))):
        raise ValueError('차량 관찰 옵션을 확인하세요.')
    if type(enable_space_http) is not bool or (enable_space_http and (not track_vehicles or not enable_http or not camera_id)):
        raise ValueError('구획 연결 전송에는 차량 관찰·점유 전송·카메라 ID가 필요합니다.')
    if type(enable_space_release_http) is not bool or (enable_space_release_http and not enable_space_http):
        raise ValueError('구획 해제는 구획 연결 전송과 함께 활성화하세요.')
    if handoff_path is not None and (not track_vehicles or plate_reader is not None or enable_space_release_http):
        raise ValueError('한 대 시연 신원 전달에는 추적이 필요하며 독립 OCR·중간 자동 해제는 함께 사용하지 않습니다.')
    from ai_vision.parking.vehicle_space_tracker import validate_tracking_target, tracking_image_size
    validate_tracking_target(tracking_target)
    tracking_imgsz = tracking_image_size(tracking_target, tracking_imgsz)
    if ocr_execution not in ('auto', 'thread', 'process') or not isinstance(ocr_execution, str):
        raise ValueError('OCR 실행 방식을 확인하세요.')
    if ocr_execution == 'process' and plate_reader is not None:
        raise ValueError('주입한 OCR 함수는 thread 실행을 사용하세요.')
    if tracking_target != 'vehicle' and not track_vehicles:
        raise ValueError('번호판 위치 추적에는 --track-vehicles가 필요합니다.')
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError('결과 폴더는 새 경로를 지정하세요.')
    check_previous_report(previous_report, enable_http)
    validate_camera_backend(camera_backend)
    config = read_json(config_path)
    reference = load_reference(reference_path, config)
    processor = ParkingOccupancyProcessor(reference, config, detect_spaces)
    settings = delivery_settings(config, enable_http, allowed_codes, os.environ if environment is None else environment)
    match_flow = None
    if track_vehicles:
        from ai_vision.recognition.vehicle_http import SpaceMatchHTTPClient, SpaceReleaseHTTPClient
        from ai_vision.recognition.vehicle_contract import validate_camera_id
        camera_id = camera_id or f'PARKING_CAMERA_{camera_index}'
        validate_camera_id(camera_id)
        env = os.environ if environment is None else environment
        match_flow = SpaceMatchDeliveryFlow(SpaceMatchHTTPClient(
            context_url=env.get('PARKING_AI_BASE_URL', 'http://127.0.0.1:81/alpharking/admin') if enable_space_http else None,
            api_key=settings['key'] if enable_space_http else None, enabled=enable_space_http),
            release_client=SpaceReleaseHTTPClient(
                context_url=env.get('PARKING_AI_BASE_URL', 'http://127.0.0.1:81/alpharking/admin') if enable_space_release_http else None,
                api_key=settings['key'] if enable_space_release_http else None, enabled=enable_space_release_http))
    pending_matches = {}
    handoff = None
    if handoff_path is not None:
        from ai_vision.recognition.single_vehicle_handoff import SingleVehicleHandoffReader
        handoff = SingleVehicleHandoffReader(handoff_path)
    view = ParkingPreview(config, enable_http=enable_http,
                          source_label=f'Camera {camera_index} / {camera_backend}') if preview else None
    if view is not None:
        view.reference = reference
    delivery = ParkingDelivery(settings) if settings else None
    capture = None
    worker = None
    vehicle_observer = None
    frame_capture = None
    created_output = False
    report = {'status': 'RUNNING', 'dry_run': not enable_http, 'http_requests': 0,
              'record_type': 'PARKING_CAMERA_SESSION',
              'publish_results': publish_results, 'tracking_target': tracking_target, 'tracking_imgsz': tracking_imgsz,
              'camera_backend': camera_backend,
              'deliveries': [], 'allowed_space_codes': sorted(allowed_codes),
              'camera_index': camera_index, 'read_frames': 0, 'events': [], 'error_type': None}
    if track_vehicles:
        report['vehicle_space'] = {'deliveries': match_flow.records, 'http_enabled': enable_space_http, 'release_http_enabled': enable_space_release_http, 'reservation_checked': False,
                                   'current_matches': [], 'events': [], 'completed_samples': [],
                                   'last_video_seconds': None}
    if enable_http:
        print('실제 점유 전송 모드 / 허용 구획: ' + ', '.join(sorted(settings['allowed_codes'])))
    try:
        if track_vehicles:
            # 1-1. 모델 준비는 측정 시계·카메라 시작 전에 끝냅니다. 기존 점유 전송과는 분리합니다.
            from ai_vision.parking.vehicle_space_tracker import VehicleSpaceObserver
            observer_options = {'handoff_reader': handoff.read} if handoff is not None else {}
            vehicle_observer = VehicleSpaceObserver(config, tracker=vehicle_tracker, plate_reader=plate_reader,
                                                    tracking_target=tracking_target, ocr_execution=ocr_execution, tracking_imgsz=tracking_imgsz,
                                                    **observer_options)
            vehicle_observer.prepare()
        worker = ParkingDeliveryWorker(delivery) if delivery is not None else None
        capture = open_camera(camera_index, backend=camera_backend)
        if not capture.isOpened():
            raise OSError('웹캠을 연결할 수 없습니다.')
        configure_resolution(capture, config['image_width'], config['image_height'])
        output_dir.mkdir(parents=True, exist_ok=False)
        created_output = True
        write_json_atomic(output_dir / 'parking_camera_check.json', report)
        # 2. 수동 시작을 기다린 뒤에만 측정 시계를 시작합니다.
        if view is not None and view.wait_until_ready(capture) is None:
            report['status'] = 'CANCELLED'
        else:
            wall_started = datetime.now(timezone.utc)
            started = time.monotonic()
            if track_vehicles:
                # 차량 추론 중에도 카메라를 읽고 최신 한 장과 실제 수집 시각만 유지합니다.
                frame_capture = LatestFrameCapture(capture)
            last_checkpoint = started
            last_publish = started
            while True:
                now = time.monotonic()
                if now - started >= seconds:
                    report['status'] = 'COMPLETED' if processor.occupancy() is not None else 'INCOMPLETE'
                    break
                if worker is not None and not worker.poll(lambda: checkpoint(output_dir, report, processor, delivery)):
                    report['status'] = 'DELIVERY_STOPPED'
                    break
                ok, frame = (frame_capture or capture).read()
                if not ok:
                    raise OSError('웹캠 프레임을 읽을 수 없습니다.')
                report['read_frames'] += 1
                observed_seconds = ((frame_capture.captured_monotonic if frame_capture is not None
                                     else time.monotonic()) - started)
                if frame_capture is not None and observed_seconds >= seconds:
                    report['status'] = 'COMPLETED' if processor.occupancy() is not None else 'INCOMPLETE'
                    break
                outcome = processor.process(frame, observed_seconds)
                if vehicle_observer is not None:
                    # 2-1. OCR 대기 중에도 다음 카메라 프레임과 차량 추적을 계속 처리합니다.
                    tracking = vehicle_observer.process(report['read_frames'] - 1, observed_seconds, frame,
                                                        eligible_spaces=processor.matching_spaces(observed_seconds))
                    vehicle = report['vehicle_space']
                    if len(vehicle['events']) + len(tracking['events']) > 10000:
                        raise ValueError('차량 관찰 이벤트 기록 한도를 초과했습니다.')
                    if len(vehicle['completed_samples']) + len(tracking['completed_samples']) > 10000:
                        raise ValueError('번호판 관찰 표본 기록 한도를 초과했습니다.')
                    vehicle['events'].extend(tracking['events'])
                    vehicle['completed_samples'].extend(tracking['completed_samples'])
                    vehicle['last_video_seconds'] = observed_seconds
                    vehicle['current_matches'] = vehicle_observer.current_matches(processor, observed_seconds)
                    # 2-2. 현재 연결이 철회되면 보내지 않은 과거 후보도 즉시 버립니다.
                    active = {(m['track_id'], m['space_id'], m['plate_number']) for m in vehicle['current_matches']}
                    pending_matches = {key: value for key, value in pending_matches.items() if key in active}
                    for event in tracking['events']:
                        if event.get('kind') == 'LOCAL_SPACE_MATCH':
                            key = (event['track_id'], event['space_id'], event['plate_number'])
                            pending_matches[key] = dict(event)
                    persist_match = lambda: checkpoint(output_dir, report, processor, delivery)
                    match_flow.poll(persist_match)
                    if handoff is not None and handoff.last_exit is not None:
                        exited = handoff.last_exit
                        match_flow.acknowledge_gate_exit(exited['plate_number'], exited['parking_usage_id'])
                    if match_flow.blocked:
                        report['status'] = 'DELIVERY_STOPPED'
                        break
                    if (enable_space_release_http and not worker.pending and not worker.blocked and not outcome['events']
                            and time.monotonic() - started - observed_seconds <= 2):
                        from ai_vision.parking.parking_event_sender import convert_space_code
                        empty_codes = {convert_space_code(code) for code in processor.empty_spaces(observed_seconds)}
                        match_flow.release_empty(empty_codes & settings['allowed_codes'], camera_id,
                            (wall_started + timedelta(seconds=observed_seconds)).isoformat(), persist_match)
                    for key, event in list(pending_matches.items()):
                        # 실제 수집 후 2초를 넘은 후보나 점유 전송이 진행 중인 후보는 보내지 않습니다.
                        if time.monotonic() - started - observed_seconds > 2:
                            continue
                        if enable_space_http:
                            from ai_vision.parking.parking_event_sender import convert_space_code
                            if (convert_space_code(event['space_id']) not in settings['allowed_codes'] or
                                    worker.pending or worker.blocked or outcome['events']):
                                continue
                        candidate = create_space_match_candidate(
                            {**event, 'kind': 'LIVE_SPACE_MATCH'}, vehicle['current_matches'], camera_id,
                            (wall_started + timedelta(seconds=observed_seconds)).isoformat())
                        decision = match_flow.submit(candidate, (key, event['frame_index']), persist_match)
                        if decision != 'BUSY':
                            del pending_matches[key]
                    vehicle['statistics'] = vehicle_observer.summary()
                    vehicle['observations'] = tracking.get('progress', [])
                    if handoff is not None:
                        vehicle['entry_handoff_status'] = handoff.status
                        vehicle['entry_handoff'] = handoff.snapshot()
                    if view is not None:
                        view.vehicle_progress = vehicle['observations']
                        view.source_label = (f'{tracking_target.upper()} tracking={len(tracking["observations"])} / '
                                             f'matched={len(vehicle["current_matches"])} / '
                                             f'OCR pending={int(vehicle["statistics"]["pending_ocr"])}')
                # 3. 시험 모드는 기록만 하고 운영 모드는 허용 구획의 이벤트만 한 번 전송합니다.
                if len(report['events']) + len(outcome['events']) > 10000:
                    raise ValueError('이벤트 기록 한도를 초과했습니다.')
                report['events'].extend(outcome['events'])
                if outcome['changes']:
                    for row in outcome['changes']:
                        print(f"[상태 확정] {row['space_id']}: {row['status']}")
                    report['statistics'] = processor.statistics()
                    write_json_atomic(output_dir / 'parking_camera_check.json', report)
                    # 기존 조회 API에 결과를 제공하는 기능도 명시적으로 선택한 경우에만 사용합니다.
                    confirmed = processor.confirmed_results()
                    if publish_results and confirmed is not None:
                        from ai_vision.parking.parking_realtime import save_results
                        save_results(frame, processor.spaces, confirmed)
                        last_publish = now
                    if delivery is not None and not deliver_changes(output_dir, report, processor, delivery, outcome['events'], worker=worker):
                        report['status'] = 'DELIVERY_STOPPED'
                        break
                # 3-1. 실제 분석 중에만 5초마다 JSON을 갱신합니다. 새 이벤트는 만들지 않습니다.
                if publish_results and outcome['sampled'] and now - last_publish >= 5:
                    confirmed = processor.confirmed_results()
                    if confirmed is not None:
                        from ai_vision.parking.parking_realtime import save_snapshot
                        save_snapshot(confirmed)
                        last_publish = now
                # 상태가 바뀌지 않아도 진행 상황을 남겨 강제 종료 시 확인할 수 있게 합니다.
                if now - last_checkpoint >= 5:
                    checkpoint(output_dir, report, processor, delivery)
                    last_checkpoint = now
                if view is not None and view.show(frame, pending_http=worker.pending if worker is not None else 0) == ord('q'):
                    report['status'] = 'STOPPED'
                    break
    except KeyboardInterrupt:
        report['status'] = 'STOPPED'
    except Exception as error:
        report['status'], report['error_type'] = 'FAILED', type(error).__name__
    finally:
        # 4. 중간 실패에도 카메라와 준비 화면을 모두 정리합니다.
        for resource, method in ((frame_capture or capture, 'release'), (view, 'close'), (vehicle_observer, 'close'),
                                 (worker, 'close'), (delivery, 'close')):
            if resource is not None:
                try:
                    if resource is worker and worker.future is not None and not worker.future.done():
                        print('카메라는 종료했습니다. 이미 시작한 전송 결과를 확인하고 있습니다.')
                    getattr(resource, method)()
                except Exception as error:
                    report['status'] = 'FAILED'
                    report['error_type'] = report['error_type'] or type(error).__name__
        if match_flow is not None:
            try:
                match_flow.close(lambda: checkpoint(output_dir, report, processor, delivery) if created_output else None)
            except Exception as error:
                report['status'], report['error_type'] = 'FAILED', type(error).__name__
            if match_flow.blocked or any(row['status'] in ('IN_FLIGHT', 'DELIVERY_UNKNOWN') for row in match_flow.records):
                if report['status'] != 'FAILED':
                    report['status'] = 'DELIVERY_STOPPED'
        report['statistics'], report['occupancy'] = processor.statistics(), processor.occupancy()
        if frame_capture is not None:
            report['capture_statistics'] = frame_capture.summary()
        if vehicle_observer is not None:
            # 관찰 종료 뒤에는 과거 후보를 현재 위치로 제공하지 않습니다.
            vehicle = report['vehicle_space']
            vehicle['last_observed_matches'] = (vehicle['current_matches'] if report['status'] in ('COMPLETED', 'STOPPED') else [])
            vehicle['current_matches'] = []
            vehicle['observations'] = []
            vehicle['statistics'] = vehicle_observer.summary()
        if worker is not None and worker.blocked and report['status'] != 'FAILED':
            report['status'] = 'DELIVERY_STOPPED'
        # 전송 중 Ctrl+C로 끝났어도 서버 반영 여부가 불명확하면 정상 종료로 표시하지 않습니다.
        if report['status'] == 'STOPPED' and any(
                row['status'] in ('IN_FLIGHT', 'DELIVERY_UNKNOWN') for row in report['deliveries']):
            report['status'] = 'DELIVERY_STOPPED'
        if created_output:
            checkpoint(output_dir, report, processor, delivery)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--camera-index', type=int, default=0)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--no-preview', action='store_true')
    parser.add_argument('--enable-http', action='store_true', help='허용 구획의 점유 상태를 실제 Boot로 전송')
    parser.add_argument('--allow-space-code', action='append', default=[], help='변경을 허용한 DB 구획 코드, 반복 지정 가능')
    parser.add_argument('--previous-report', type=Path, help='직전 실행 보고서를 시작 전에 점검')
    parser.add_argument('--publish-results', action='store_true', help='기존 점유 조회 API의 결과 파일도 갱신')
    parser.add_argument('--camera-backend', choices=CAMERA_BACKENDS, default='default', help='카메라 연결 방식')
    parser.add_argument('--enable-space-http', action='store_true', help='점유 전송과 함께 허용 구획의 차량 연결도 전송')
    parser.add_argument('--enable-space-release-http', action='store_true', help='확정 EMPTY와 서버 연결 버전으로 기존 연결 해제')
    parser.add_argument('--ocr-execution', choices=('auto', 'thread', 'process'), default='auto', help='plate의 기본 로컬 OCR은 별도 프로세스로 실행')
    parser.add_argument('--tracking-imgsz', type=int, choices=(640,960,1280), help='기본 plate=1280, vehicle=640')
    parser.add_argument('--tracking-target', choices=('vehicle', 'plate'), default='vehicle', help='차체 또는 번호판 위치 추적')
    parser.add_argument('--single-vehicle-handoff', type=Path, help='A카메라의 현재 실행 신원 파일. 한 대 시연에서만 사용')
    parser.add_argument('--camera-id', help='Boot에서 구분할 주차 카메라 ID')
    parser.add_argument('--track-vehicles', action='store_true', help='차량·번호판·구획 관찰. 연결 전송은 별도 활성화 필요')
    args = parser.parse_args(argv)
    try:
        report = run_camera(args.reference, args.config, args.output_dir, args.camera_index, args.seconds,
                            not args.no_preview, args.enable_http, args.allow_space_code,
                            previous_report=args.previous_report, publish_results=args.publish_results,
                            camera_backend=args.camera_backend, track_vehicles=args.track_vehicles,
                            enable_space_http=args.enable_space_http, camera_id=args.camera_id,
                            enable_space_release_http=args.enable_space_release_http, tracking_target=args.tracking_target, ocr_execution=args.ocr_execution, tracking_imgsz=args.tracking_imgsz,
                            handoff_path=args.single_vehicle_handoff)
    except (ValueError, OSError, RuntimeError) as error:
        print(f'실행 실패: {error}')
        return 1
    print(f"주차면 검사: {report['status']} / 프레임 {report['read_frames']} / 이벤트 {len(report['events'])} / HTTP {report['http_requests']}회")
    if report['error_type']:
        print(f"오류 종류: {report['error_type']}")
    return 0 if report['status'] in ('COMPLETED', 'STOPPED', 'CANCELLED') else 1


if __name__ == '__main__':
    raise SystemExit(main())

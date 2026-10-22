# D:/finalProjectB/back/apcms_ai/ai_vision/parking/run_parking_camera.py
"""USB 웹캠 점유 검사와 명시적으로 허용한 구획의 Boot 전송을 실행합니다."""

import argparse
import math
import time
import os
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


def run_camera(reference_path, config_path, output_dir, camera_index=0, seconds=60, preview=True,
               enable_http=False, allowed_codes=(), environment=None, previous_report=None,
               publish_results=False, camera_backend='default'):
    # 1. 저장 경로와 입력을 먼저 확인하여 기존 운영 결과를 보호합니다.
    if type(camera_index) is not int or not 0 <= camera_index <= 99:
        raise ValueError('카메라 번호는 0~99 정수여야 합니다.')
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 < seconds <= 300:
        raise ValueError('측정 시간은 0초 초과 300초 이하여야 합니다.')
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError('결과 폴더는 새 경로를 지정하세요.')
    check_previous_report(previous_report, enable_http)
    validate_camera_backend(camera_backend)
    config = read_json(config_path)
    reference = load_reference(reference_path, config)
    processor = ParkingOccupancyProcessor(reference, config, detect_spaces)
    settings = delivery_settings(config, enable_http, allowed_codes, os.environ if environment is None else environment)
    view = ParkingPreview(config, enable_http=enable_http,
                          source_label=f'Camera {camera_index} / {camera_backend}') if preview else None
    delivery = ParkingDelivery(settings) if settings else None
    capture = None
    worker = None
    created_output = False
    report = {'status': 'RUNNING', 'dry_run': not enable_http, 'http_requests': 0,
              'record_type': 'PARKING_CAMERA_SESSION',
              'publish_results': publish_results,
              'camera_backend': camera_backend,
              'deliveries': [], 'allowed_space_codes': sorted(allowed_codes),
              'camera_index': camera_index, 'read_frames': 0, 'events': [], 'error_type': None}
    if enable_http:
        print('실제 점유 전송 모드 / 허용 구획: ' + ', '.join(sorted(settings['allowed_codes'])))
    try:
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
            started = time.monotonic()
            last_checkpoint = started
            while True:
                now = time.monotonic()
                if now - started >= seconds:
                    report['status'] = 'COMPLETED' if processor.occupancy() is not None else 'INCOMPLETE'
                    break
                if worker is not None and not worker.poll(lambda: checkpoint(output_dir, report, processor, delivery)):
                    report['status'] = 'DELIVERY_STOPPED'
                    break
                ok, frame = capture.read()
                if not ok:
                    raise OSError('웹캠 프레임을 읽을 수 없습니다.')
                report['read_frames'] += 1
                outcome = processor.process(frame, time.monotonic() - started)
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
                    if delivery is not None and not deliver_changes(output_dir, report, processor, delivery, outcome['events'], worker=worker):
                        report['status'] = 'DELIVERY_STOPPED'
                        break
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
        for resource, method in ((capture, 'release'), (view, 'close'), (worker, 'close'), (delivery, 'close')):
            if resource is not None:
                try:
                    if resource is worker and worker.future is not None and not worker.future.done():
                        print('카메라는 종료했습니다. 이미 시작한 전송 결과를 확인하고 있습니다.')
                    getattr(resource, method)()
                except Exception as error:
                    report['status'] = 'FAILED'
                    report['error_type'] = report['error_type'] or type(error).__name__
        report['statistics'], report['occupancy'] = processor.statistics(), processor.occupancy()
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
    args = parser.parse_args(argv)
    try:
        report = run_camera(args.reference, args.config, args.output_dir, args.camera_index, args.seconds,
                            not args.no_preview, args.enable_http, args.allow_space_code,
                            previous_report=args.previous_report, publish_results=args.publish_results,
                            camera_backend=args.camera_backend)
    except (ValueError, OSError, RuntimeError) as error:
        print(f'실행 실패: {error}')
        return 1
    print(f"주차면 검사: {report['status']} / 프레임 {report['read_frames']} / 이벤트 {len(report['events'])} / HTTP {report['http_requests']}회")
    if report['error_type']:
        print(f"오류 종류: {report['error_type']}")
    return 0 if report['status'] in ('COMPLETED', 'STOPPED', 'CANCELLED') else 1


if __name__ == '__main__':
    raise SystemExit(main())

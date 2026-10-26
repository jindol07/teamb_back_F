# D:/finalProjectB/back/apcms_ai/ai_vision/parking/run_vehicle_space_tracking.py
"""저장 영상에서 차량과 구획의 연결 근거를 검사합니다. Boot 전송·예약 판정은 하지 않습니다."""

import argparse
import json
import math
import hashlib
from datetime import datetime
from pathlib import Path

import cv2

from ai_vision.parking.vehicle_space_tracker import VehicleSpaceTracker, review_match_context, create_vehicle_tracker, validate_tracking_target, read_tracked_plate, plate_tracking_confidence, tracking_image_size
from ai_vision.recognition.local_io import read_json, write_json_atomic
from ai_vision.parking.inspect_parking_camera import summarize_connection_reviews


def run(source, config_path, output_dir, max_seconds=60, tracker=None, plate_reader=None,
        boot_context=None, recording_started_at=None, vision_api_url=None, capture_report=None,
        reference_path=None, occupancy_detector=None, tracking_target='vehicle', tracking_imgsz=None):
    # 1. 설정·출력 경로를 먼저 검사하며 기존 시험 결과를 덮어쓰지 않습니다.
    validate_tracking_target(tracking_target)
    tracking_imgsz = tracking_image_size(tracking_target, tracking_imgsz)
    if tracking_target == 'plate' and vision_api_url is not None:
        raise ValueError('번호판 위치 추적은 로컬 번호판 OCR을 사용하세요.')
    source, output_dir = Path(source), Path(output_dir)
    if not source.is_file() or output_dir.exists():
        raise ValueError('실제 입력 영상과 새 출력 폴더를 지정하세요.')
    if type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 0 < max_seconds <= 300:
        raise ValueError('검사 길이는 0초 초과 300초 이하입니다.')
    config = read_json(config_path)
    context = read_json(boot_context) if boot_context is not None else None
    frame_times = None
    if capture_report is not None:
        # 녹화 파일과 실제 수집 시각을 묶습니다. 다른 영상의 촬영 정보를 재사용하지 않습니다.
        metadata = read_json(capture_report)
        frame_times = metadata.get('frame_times_seconds')
        if (metadata.get('status') not in ('COMPLETED', 'STOPPED') or metadata.get('http_enabled') is not False
                or not isinstance(frame_times, list) or not 1 <= len(frame_times) <= 36000
                or any(type(t) not in (int, float) or not math.isfinite(t) or not 0 <= t <= 300 for t in frame_times)
                or any(b < a for a, b in zip(frame_times, frame_times[1:]))
                or metadata.get('captured_frames') != len(frame_times)):
            raise ValueError('완료된 촬영 정보와 증가하는 프레임 시각이 필요합니다.')
        started_at = metadata.get('recording_started_at')
        if not isinstance(started_at, str) or datetime.fromisoformat(started_at).utcoffset() is None:
            raise ValueError('촬영 정보에 타임존이 포함된 시작 시각이 필요합니다.')
        if recording_started_at is not None and recording_started_at != started_at:
            raise ValueError('명시한 시각과 촬영 정보의 시작 시각이 다릅니다.')
        recording_started_at = started_at
        with source.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != metadata.get('video_sha256'):
                raise ValueError('촬영 정보와 영상 파일이 일치하지 않습니다.')
    if vision_api_url is not None:
        if plate_reader is not None:
            raise ValueError('원격 API와 주입한 인식기를 동시에 지정할 수 없습니다.')
        # 기존 원격 인식기의 주소 검사·제한 시간·응답 검증을 그대로 사용합니다.
        from ai_vision.recognition.remote_plate_reader import RemotePlateReader
        plate_reader = RemotePlateReader(vision_api_url).read
    processor = VehicleSpaceTracker(config, motion_window_seconds=.1 if tracking_target == 'plate' else 0,
                                    recover_plate_conflicts=tracking_target == 'plate')
    occupancy = None
    if reference_path is not None:
        # 1-1. 같은 구도의 빈 기준 사진과 기존 점유 처리기를 재사용합니다. 영상 시각만 사용합니다.
        from ai_vision.parking.parking_calibration import load_reference
        from ai_vision.parking.parking_processor import ParkingOccupancyProcessor
        from ai_vision.parking.parking_realtime import detect_spaces
        reference = load_reference(reference_path, config)
        occupancy = ParkingOccupancyProcessor(reference, config,
                                             occupancy_detector if occupancy_detector is not None else detect_spaces,
                                             emit_events=False)
    elif occupancy_detector is not None:
        raise ValueError('점유 분석에는 같은 구도의 빈 기준 사진이 필요합니다.')
    capture = cv2.VideoCapture(str(source))
    report = {'status': 'RUNNING', 'record_type': 'LOCAL_VEHICLE_SPACE_TRACKING',
              'source': str(source.resolve()), 'tracking_target': tracking_target, 'tracking_imgsz': tracking_imgsz, 'http_enabled': False,
              'reservation_checked': False, 'entry_checked': False, 'physical_occupancy_checked': False,
              'frames': 0, 'event_count': 0, 'error_type': None, 'current_matches': [],
              'skipped_duplicate_time_frames': 0, 'vehicle_observation_frames': 0, 'ocr_requests': 0}
    report.update(local_occupancy_enabled=occupancy is not None, local_occupancy_checked=False,
                  held_matches=[])
    report['connection_withdrawal_counts'] = {}
    report['recognition_mode'] = 'REMOTE_API' if vision_api_url is not None else ('INJECTED' if plate_reader is not None else 'LOCAL')
    report['remote_recognition_enabled'] = vision_api_url is not None
    report['time_basis'] = 'CAPTURE_MONOTONIC' if frame_times is not None else 'ENCODED_FPS'
    report['recording_started_at'] = recording_started_at
    created = False
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        declared_frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if not capture.isOpened() or not math.isfinite(fps) or not 0 < fps <= 240:
            raise ValueError('영상과 FPS를 확인하세요.')
        if frame_times is not None and (not math.isfinite(declared_frames) or declared_frames != len(frame_times)):
            raise ValueError('영상 프레임 수와 촬영 시각 수가 다릅니다.')
        output_dir.mkdir(parents=True, exist_ok=False)
        created = True
        write_json_atomic(output_dir / 'config.json', config)
        write_json_atomic(output_dir / 'summary.json', report)
        if tracker is None:
            # 2. 입출차와 같은 차량 모델을 사용하되 별도 추적 세션을 만듭니다.
            _, tracker = (create_vehicle_tracker() if tracking_target == 'vehicle' and tracking_imgsz == 640
                          else create_vehicle_tracker(tracking_target, tracking_imgsz))
        if plate_reader is None:
            from ai_vision.recognition.live_gate_processor import LiveGateProcessor
            plate_reader = read_tracked_plate if tracking_target == 'plate' else LiveGateProcessor._read_plate
        last_ocr = {}
        with (output_dir / 'events.jsonl').open('x', encoding='utf-8') as events_file, \
             (output_dir / 'observations.jsonl').open('x', encoding='utf-8') as observations_file:
            frame_index = 0
            while True:
                next_seconds = (frame_times[frame_index] if frame_times is not None and frame_index < len(frame_times)
                                else frame_index / fps)
                if next_seconds >= max_seconds and (frame_times is None or frame_index < len(frame_times)):
                    report['status'] = 'LIMIT_REACHED'
                    break
                ok, frame = capture.read()
                if not ok:
                    if not report['frames']:
                        raise ValueError('영상에 읽을 수 있는 프레임이 없습니다.')
                    if math.isfinite(declared_frames) and declared_frames > report['frames']:
                        raise OSError('영상 끝 이전에 프레임 읽기가 중단됐습니다.')
                    report['status'] = 'COMPLETED'
                    break
                if frame_times is not None and frame_index >= len(frame_times):
                    raise ValueError('촬영 정보에 없는 추가 영상 프레임입니다.')
                if frame.shape != (config['image_height'], config['image_width'], 3):
                    raise ValueError('영상과 구획 좌표의 해상도가 다릅니다. 영상을 임의 확대하지 않습니다.')
                seconds = next_seconds
                # Windows의 낮은 시계 정밀도로 같은 시각이 생겨도 시간을 지어내지 않습니다.
                # 파일 프레임 수는 세되 추적·OCR·체류 표본은 중복 추가하지 않습니다.
                if processor.last_time is not None and seconds == processor.last_time:
                    report['frames'] += 1
                    report['skipped_duplicate_time_frames'] += 1
                    frame_index += 1
                    continue
                rows = tracker(frame)
                # 3. 모델의 화면 경계 상자는 억지로 구획에 연결하지 않고 제외합니다.
                if not isinstance(rows, list) or len(rows) > processor.limit:
                    raise ValueError('차량 관찰 한도를 초과했습니다.')
                valid = []
                for row in rows:
                    box = row['box']
                    if not (len(box) == 4 and 0 <= box[0] < box[2] < frame.shape[1]
                            and 0 <= box[1] < box[3] < frame.shape[0]):
                        continue
                    item = dict(row)
                    track = item['track_id']
                    if seconds - last_ocr.get(track, -1) >= .5 and processor._space(box) is not None:
                        x1, y1, x2, y2 = box
                        confidence = plate_tracking_confidence(item) if tracking_target == 'plate' else None
                        report['ocr_requests'] += 1
                        result = plate_reader(frame[y1:y2, x1:x2])
                        if not isinstance(result, dict):
                            raise ValueError('번호판 인식 결과 객체가 필요합니다.')
                        if tracking_target == 'plate':
                            result = result | {'plate_detection_confidence': confidence}
                        item['plate_sample'] = {**result, 'frame_index': frame_index, 'video_seconds': seconds}
                        last_ocr[track] = seconds
                    valid.append(item)
                # 같은 프레임 점유를 먼저 계산하고 연결 상태·OCR 근거 누적에도 적용한다.
                local_occupancy, eligible = None, None
                if occupancy is not None:
                    sample = occupancy.process(frame, seconds)
                    eligible = occupancy.matching_spaces(seconds)
                    local_occupancy = {'sampled': sample['sampled'], 'matching_space_ids': sorted(eligible)}
                events = processor.process(frame_index, seconds, valid, eligible_spaces=eligible)
                if occupancy is not None:
                    for event in events:
                        if event['kind'] == 'LOCAL_SPACE_MATCH':
                            event['local_occupancy_confirmed'] = event['space_id'] in eligible
                report['vehicle_observation_frames'] += bool(valid)
                # 4. 원래 영상 시각과 관찰·판정 근거를 함께 남깁니다. 현재 날짜를 입차 시각으로 만들지 않습니다.
                observation = {'frame_index': frame_index, 'video_seconds': seconds, 'observations': valid}
                if local_occupancy is not None:
                    observation['local_occupancy'] = local_occupancy
                observations_file.write(json.dumps(observation, ensure_ascii=False, allow_nan=False) + '\n')
                for reason, count in summarize_connection_reviews(events).items():
                    counts = report['connection_withdrawal_counts']
                    counts[reason] = counts.get(reason, 0) + count
                for event in events:
                    events_file.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')
                report['frames'] += 1
                report['event_count'] += len(events)
                frame_index += 1
                # 사라진 ID의 OCR 간격 기록도 유한하게 유지합니다.
                last_ocr = {key: value for key, value in last_ocr.items() if seconds - value <= processor.gap}
    except Exception as error:
        report.update(status='FAILED', error_type=type(error).__name__)
        raise
    finally:
        capture.release()
        if created:
            # 5. 과거 연결 이벤트만 세지 않고 철회·가림을 반영한 마지막 관찰 상태도 남깁니다.
            report['current_matches'] = [
                {'track_id': key, 'space_id': value['matched'], 'plate_number': value['number']}
                for key, value in processor.states.items()
                if (value['matched'] is not None and value['seen'] == processor.last_time
                    and report['status'] in ('COMPLETED', 'LIMIT_REACHED'))]
            report['last_video_seconds'] = processor.last_time
            if occupancy is not None:
                # 5-1. 마지막 차량 후보와 같은 영상 시각의 연속 점유가 모두 있어야 남깁니다.
                eligible = occupancy.matching_spaces(processor.last_time) if processor.last_time is not None else set()
                report['held_matches'] = [
                    {**match, 'reason': 'LOCAL_OCCUPANCY_NOT_CONFIRMED'}
                    for match in report['current_matches'] if match['space_id'] not in eligible]
                report['current_matches'] = [m for m in report['current_matches'] if m['space_id'] in eligible]
                report['local_occupancy_checked'] = occupancy.statistics()['analyzed_frames'] > 0
                report['local_occupancy'] = {
                    'reference': str(Path(reference_path).resolve()),
                    'source': 'SAME_VIDEO_REFERENCE_DIFFERENCE', 'occupancy': occupancy.occupancy(),
                    'matching_space_ids': sorted(eligible), 'statistics': occupancy.statistics()}
            # 실행 완료와 차량 연결 성공을 구분해 빈 분석 결과를 성공으로 오해하지 않게 합니다.
            report['analysis_outcome'] = (
                'FAILED' if report['status'] == 'FAILED' else
                'LOCAL_MATCH_WITH_OCCUPANCY' if report['current_matches'] and occupancy is not None else
                'LOCAL_MATCH_PRESENT' if report['current_matches'] else
                'NO_VEHICLE_OBSERVATIONS' if not report['vehicle_observation_frames'] else 'NO_CURRENT_MATCH')
            if boot_context is not None:
                report['context_review'] = review_match_context(report, context, recording_started_at)
            write_json_atomic(output_dir / 'summary.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--max-seconds', type=float, default=60)
    parser.add_argument('--boot-context', type=Path, help='관리자 조회 응답의 로컬 JSON 사본. 네트워크 요청은 하지 않음')
    parser.add_argument('--recording-started-at', help='실제 촬영 시작 ISO 시각. 타임존 필수')
    parser.add_argument('--vision-api-url', help='차량 영역을 업로드할 Vision API 주소. 생략하면 로컬 인식')
    parser.add_argument('--capture-report', type=Path, help='영상과 함께 생성된 실제 촬영 시각 JSON')
    parser.add_argument('--tracking-imgsz',type=int,choices=(640,960,1280))
    parser.add_argument('--tracking-target', choices=('vehicle', 'plate'), default='vehicle')
    parser.add_argument('--reference', type=Path, help='같은 구도의 빈 기준 사진. 차량 후보와 연속 점유를 함께 검사')
    args = parser.parse_args(argv)
    try:
        report = run(args.source, args.config, args.output_dir, args.max_seconds,
                     boot_context=args.boot_context, recording_started_at=args.recording_started_at,
                     vision_api_url=args.vision_api_url, capture_report=args.capture_report,
                     reference_path=args.reference, tracking_target=args.tracking_target, tracking_imgsz=args.tracking_imgsz)
    except (ValueError, OSError, RuntimeError) as error:
        print(f'차량·구획 검사 실패: {type(error).__name__}')
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

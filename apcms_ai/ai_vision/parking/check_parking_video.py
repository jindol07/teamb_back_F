# D:/finalProjectB/back/apcms_ai/ai_vision/parking/check_parking_video.py

"""영상 파일의 점유 확정과 Boot 이벤트 생성을 확인합니다. 실제 전송은 하지 않습니다."""

import argparse
import math
from pathlib import Path

import cv2

from ai_vision.parking.parking_processor import ParkingOccupancyProcessor
from ai_vision.parking.parking_validation import validate_spaces
from ai_vision.parking.parking_realtime import detect_spaces
from ai_vision.recognition.local_io import read_json, write_json_atomic
from ai_vision.parking.parking_calibration import load_reference


def run_check(reference_path, config_path, video_path, output_dir, max_frames=9000, max_seconds=300):
    # 1. 원본·실시간 결과를 덮어쓰지 않고 새 검사 폴더만 사용합니다.
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError("새 출력 폴더를 지정하세요.")
    if (type(max_frames) is not int or not 1 <= max_frames <= 100000 or
            type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 0 < max_seconds <= 300):
        raise ValueError("프레임·영상 시간 한도를 확인하세요.")
    video = Path(video_path)
    if not video.is_file():
        raise ValueError("로컬 영상 파일이 필요합니다.")
    config = validate_spaces(read_json(config_path))
    reference = load_reference(reference_path, config)
    processor = ParkingOccupancyProcessor(reference, config, detect_spaces)
    capture = cv2.VideoCapture(str(video.resolve()))
    report = {'record_type': 'PARKING_SEQUENCE_CHECK', 'status': 'RUNNING', 'source_type': 'VIDEO_FILE',
              'validation_scope': 'PIXEL_CHANGE_STATE_AND_EVENT_GENERATION_ONLY',
              'dry_run': True, 'http_requests': 0, 'read_frames': 0, 'processed_frames': 0,
              'events': [], 'changes': [], 'error_type': None, 'stop_reason': None}
    created = False
    try:
        if not capture.isOpened():
            raise ValueError("영상 파일을 열 수 없습니다.")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or not 0 < fps <= 240:
            raise ValueError("영상 FPS가 유효하지 않아 프레임 시각을 계산할 수 없습니다.")
        output_dir.mkdir(parents=True, exist_ok=False)
        created = True
        report['fps'] = fps
        write_json_atomic(output_dir / 'parking_check.json', report)
        for index in range(max_frames):
            seconds = index / fps
            if seconds > max_seconds:
                report['stop_reason'] = 'VIDEO_TIME_LIMIT'
                break
            ok, frame = capture.read()
            if not ok:
                report['stop_reason'] = 'SOURCE_ENDED'
                break
            report['read_frames'] += 1
            outcome = processor.process(frame, seconds)
            report['processed_frames'] += 1
            if len(report['events']) + len(outcome['events']) > 10000:
                raise ValueError("검사 이벤트 보관 한도를 초과했습니다.")
            report['events'].extend(outcome['events'])
            report['changes'].extend({**change, 'frame_index': index, 'video_seconds': seconds}
                                     for change in outcome['changes'])
            if outcome['changes']:
                write_json_atomic(output_dir / 'parking_check.json', report)
        else:
            report['stop_reason'] = 'FRAME_LIMIT'
        report['status'] = 'COMPLETED' if processor.occupancy() is not None else 'INCOMPLETE'
    except KeyboardInterrupt:
        if not created:
            raise
        report.update(status='STOPPED', stop_reason='USER_INTERRUPTED')
    except Exception as error:
        report.update(status='FAILED', stop_reason='INPUT_OR_PROCESSING_FAILED', error_type=type(error).__name__)
        if not created:
            raise
    finally:
        try:
            capture.release()
        except Exception as error:
            report.update(status='FAILED', stop_reason='CLEANUP_FAILED', error_type=type(error).__name__)
    # 2. 실시간 결과 API 파일과 대기 이벤트 파일에는 쓰지 않습니다.
    report['statistics'] = processor.statistics()
    report['occupancy'] = processor.occupancy()
    write_json_atomic(output_dir / 'parking_check.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--max-frames', type=int, default=9000)
    parser.add_argument('--max-seconds', type=float, default=300)
    args = parser.parse_args(argv)
    try:
        report = run_check(args.reference, args.config, args.video, args.output_dir, args.max_frames, args.max_seconds)
    except (OSError, ValueError, cv2.error):
        parser.exit(1, '점유 검사 실패: 기준 사진·좌표·영상·새 출력 폴더를 확인하세요.\n')
    except KeyboardInterrupt:
        parser.exit(130, '점유 검사를 취소했습니다.\n')
    print(f"점유 검사: {report['status']} / 프레임 {report['processed_frames']} / 생성 이벤트 {len(report['events'])} / HTTP 0회")
    return 0 if report['status'] == 'COMPLETED' else 1


if __name__ == '__main__':
    raise SystemExit(main())

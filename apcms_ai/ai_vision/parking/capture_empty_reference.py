# D:/finalProjectB/back/apcms_ai/ai_vision/parking/capture_empty_reference.py
"""구도를 확인한 뒤 빈 주차면 기준 사진을 새 파일로 저장합니다."""

import argparse
from pathlib import Path
import cv2
from ai_vision.camera_runtime import open_camera, CAMERA_BACKENDS, validate_camera_backend
from ai_vision.parking.parking_preview import ParkingPreview
from ai_vision.paths import DATA_DIR
from ai_vision.parking.parking_calibration import configure_resolution, validate_resolution, validate_frame_resolution
from ai_vision.recognition.local_io import read_json
from ai_vision.parking.parking_validation import validate_spaces

SAVE_PATH = DATA_DIR / "parking_spaces" / "empty_reference.jpg"


def capture_empty_reference(camera_index=0, output_path=None, width=None, height=None, camera_backend='default',
                            config_path=None):
    # 1. 기존 기준 사진을 실수로 덮어쓰지 않도록 새 경로만 허용합니다.
    output_path = Path(output_path) if output_path is not None else SAVE_PATH
    if type(camera_index) is not int or not 0 <= camera_index <= 99:
        raise ValueError('카메라 번호는 0~99 정수여야 합니다.')
    if output_path.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
        raise ValueError('저장 형식은 jpg 또는 png로 지정하세요.')
    if output_path.exists():
        raise ValueError('기준 사진이 이미 있습니다. 새 저장 경로를 지정하세요.')
    if (width is None) != (height is None):
        raise ValueError('너비와 높이는 함께 지정하세요.')
    config = validate_spaces(read_json(config_path)) if config_path is not None else None
    if config is not None:
        expected = (config['image_width'], config['image_height'])
        if width is not None and (width, height) != expected:
            raise ValueError('촬영 해상도와 기존 구획 설정이 다릅니다.')
        width, height = expected
    if width is not None:
        validate_resolution(width, height)
    validate_camera_backend(camera_backend)
    preview = (ParkingPreview(config, source_label=f'Camera {camera_index} / {camera_backend}')
               if config is not None else ParkingPreview(source_label=f'Camera {camera_index} / {camera_backend}'))
    capture = None
    try:
        capture = open_camera(camera_index, backend=camera_backend)
        if not capture.isOpened():
            raise OSError('웹캠을 연결할 수 없습니다.')
        if width is not None:
            configure_resolution(capture, width, height)
        # 2. 빈 장면과 구도를 사용자가 확인한 뒤 스페이스바로 촬영합니다.
        print('모든 구획이 비어 있고 경계선이 화면의 구획과 맞는지 확인한 뒤 촬영하세요.')
        if width is not None:
            frame = preview.wait_until_ready(capture,
                check_ready=lambda frame: validate_frame_resolution(frame, width, height))
        else:
            frame = preview.wait_until_ready(capture)
        if frame is None:
            print('기준 사진 촬영을 취소했습니다.')
            return False
        if width is not None:
            validate_frame_resolution(frame, width, height)
        else:
            validate_resolution(frame.shape[1], frame.shape[0])
        ok, encoded = cv2.imencode(output_path.suffix, frame)
        if not ok:
            raise OSError('사진을 인코딩하지 못했습니다.')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # 3. 촬영 중 다른 프로그램이 같은 파일을 만들었어도 덮어쓰지 않습니다.
        with output_path.open('xb') as handle:
            handle.write(encoded.tobytes())
        print(f'기준 사진 저장: {output_path} / {frame.shape[1]} x {frame.shape[0]}')
        return True
    finally:
        try:
            if capture is not None:
                capture.release()
        finally:
            preview.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera-index', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--width', type=int, help='촬영 너비, 높이와 함께 지정')
    parser.add_argument('--height', type=int, help='촬영 높이, 너비와 함께 지정')
    parser.add_argument('--config', type=Path, help='기존 구획 좌표를 표시하고 해당 해상도로 빈 기준 사진 촬영')
    parser.add_argument('--camera-backend', choices=CAMERA_BACKENDS, default='default', help='카메라 연결 방식')
    args = parser.parse_args(argv)
    try:
        options = {'config_path': args.config} if args.config is not None else {}
        capture_empty_reference(args.camera_index, args.output, args.width, args.height, args.camera_backend, **options)
    except (ValueError, OSError, RuntimeError) as error:
        print(f'촬영 실패: {error}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

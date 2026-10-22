# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_camera_recognition.py

"""실제 카메라를 열지 않고 수동 촬영의 로컬·원격 경로와 자원 해제를 확인합니다."""

import contextlib
import io
import unittest
from unittest.mock import Mock, patch

import numpy as np

from ai_vision.recognition import camera_recognition as camera


class CameraRecognitionTests(unittest.TestCase):
    def run_preview(self, remote=False, failure=None, keys=(ord('r'), ord('q'))):
        # 1. 표시·촬영·키 입력을 대체하여 HTTP 요청이나 하드웨어 접근을 막습니다.
        frame = np.zeros((32, 64, 3), dtype=np.uint8)
        capture = Mock()
        capture.read.return_value = (True, frame)
        capture.isOpened.return_value = True
        sample = {'plate_number': '91소6408', 'plate_type': 'KOREAN_VALID', 'review_reasons': []}
        with patch.object(camera, 'require_display'), patch.object(camera, 'open_camera', return_value=capture), \
                patch.object(camera.cv2, 'imshow'), patch.object(camera.cv2, 'waitKey', side_effect=keys), \
                patch.object(camera.cv2, 'destroyAllWindows') as close, \
                patch.object(camera, 'RemotePlateReader') as reader, \
                patch.object(camera, 'recognize_image', return_value={'success': False, 'message': '차량 없음'}) as local, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            reader.return_value.read.return_value = sample
            reader.return_value.read.side_effect = failure
            camera.run_camera_recognition(0, 'http://127.0.0.1:18000' if remote else None)
        capture.release.assert_called_once()
        close.assert_called_once()
        return reader, local, output.getvalue()

    def test_remote_reads_only_when_requested_and_skips_local_models(self):
        reader, local, output = self.run_preview(remote=True)
        reader.return_value.read.assert_called_once()
        local.assert_not_called()
        self.assertIn('91소6408', output)

    def test_default_local_route_is_preserved(self):
        reader, local, _ = self.run_preview()
        reader.assert_not_called()
        local.assert_called_once()

    def test_quit_does_not_send_frame(self):
        reader, local, _ = self.run_preview(remote=True, keys=(ord('q'),))
        reader.return_value.read.assert_not_called()
        local.assert_not_called()

    def test_remote_failure_keeps_preview_and_releases_without_error_details(self):
        _, local, output = self.run_preview(remote=True, failure=RuntimeError('private-server-address'))
        local.assert_not_called()
        self.assertIn('RuntimeError', output)
        self.assertNotIn('private-server-address', output)

    def test_invalid_remote_url_is_rejected_before_camera_opens(self):
        with patch.object(camera, 'open_camera') as capture:
            with self.assertRaises(ValueError):
                camera.run_camera_recognition(0, 'http://user:secret@example.com')
        capture.assert_not_called()

    def test_cli_rejects_negative_camera_before_execution(self):
        with patch.object(camera, 'run_camera_recognition') as run, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                camera.main(['--camera-index', '-1'])
        run.assert_not_called()

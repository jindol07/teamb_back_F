# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_remote_plate_reader.py

"""원격 번호판 표본의 차량 연결·통신 실패·자원 정리를 확인합니다."""

import json
import unittest
from unittest.mock import Mock

import cv2
import numpy as np
import requests

from ai_vision.recognition.remote_plate_reader import RemotePlateReader, RemotePlateError


def make_session(vehicles):
    session = Mock()
    response = session.post.return_value
    response.status_code = 200
    response.iter_content.return_value = [json.dumps({'success': bool(vehicles), 'vehicle_count': len(vehicles),
                                                     'vehicles': vehicles}).encode('utf-8')]
    return session


class RemotePlateReaderTests(unittest.TestCase):
    def test_png_request_and_korean_confidence_mapping(self):
        crop = np.full((20, 30, 3), 100, dtype=np.uint8)
        session = make_session([{'plate_number': '91소6408', 'plate_type': 'KOREAN_VALID', 'plate_confidence': .9}])
        result = RemotePlateReader('http://vision:8000', session_factory=lambda: session).read(crop)
        self.assertEqual(result['plate_detection_confidence'], .9)
        self.assertEqual(result['plate_number'], '91소6408')
        request = session.post.call_args
        self.assertEqual(request.args[0], 'http://vision:8000/recognize')
        self.assertNotIn('headers', request.kwargs)
        self.assertFalse(request.kwargs['allow_redirects'])
        self.assertFalse(session.trust_env)
        payload = request.kwargs['files']['file']
        self.assertEqual(payload[0], 'vehicle.png')
        np.testing.assert_array_equal(cv2.imdecode(np.frombuffer(payload[1], dtype=np.uint8), cv2.IMREAD_COLOR), crop)
        session.post.assert_called_once()
        session.post.return_value.close.assert_called_once()
        session.close.assert_called_once()

    def test_no_vehicle_and_review_remain_unconfirmed(self):
        crop = np.zeros((20, 20, 3), dtype=np.uint8)
        for vehicles, expected in (([], 'NOT_DETECTED'),
                                   ([{'plate_number': '10-1557', 'plate_type': 'REVIEW'}], 'REVIEW'),
                                   ([{'plate_number': 'ABC123', 'plate_type': 'FOREIGN_OR_OTHER'}], 'FOREIGN_OR_OTHER')):
            with self.subTest(expected=expected):
                result = RemotePlateReader('http://vision', session_factory=lambda: make_session(vehicles)).read(crop)
                self.assertEqual(result['plate_type'], expected)
                self.assertNotIn('plate_detection_confidence', result)

    def test_multiple_vehicles_are_not_assigned_to_one_track(self):
        session = make_session([{}, {}])
        with self.assertRaisesRegex(RemotePlateError, '^REMOTE_AMBIGUOUS_VEHICLES$'):
            RemotePlateReader('http://vision', session_factory=lambda: session).read(np.zeros((20, 20, 3), dtype=np.uint8))

    def test_valid_shaped_review_from_api_cannot_become_confirmed(self):
        # 서버가 색상·전체 번호 문제로 보류한 값은 원격 클라이언트도 보류해야 합니다.
        from ai_vision.recognition.plate_consensus import summarize_plate_samples
        vehicle = {'plate_number': '59바3151', 'plate_type': 'REVIEW', 'plate_confidence': .95}
        reader = RemotePlateReader('http://vision', session_factory=lambda: make_session([vehicle]))
        samples = []
        for index in (0, 10):
            sample = reader.read(np.zeros((20, 20, 3), dtype=np.uint8))
            self.assertEqual(sample['plate_type'], 'REVIEW')
            self.assertNotIn('plate_detection_confidence', sample)
            samples.append(dict(sample, frame_index=index, video_seconds=index / 30))
        self.assertEqual(summarize_plate_samples(samples)['status'], 'NO_VALID_KOREAN_PLATE')

    def test_invalid_confidence_or_plate_is_rejected(self):
        for text, confidence in (('10-1557', .9), ('91소6408', None), ('91소6408', True), ('91소6408', 2)):
            session = make_session([{'plate_number': text, 'plate_type': 'KOREAN_VALID', 'plate_confidence': confidence}])
            with self.subTest(text=text, confidence=confidence), self.assertRaisesRegex(RemotePlateError, '^REMOTE_INVALID_RESPONSE$'):
                RemotePlateReader('http://vision', session_factory=lambda: session).read(np.zeros((20, 20, 3), dtype=np.uint8))

    def test_timeout_is_sanitized_and_not_retried(self):
        session = Mock()
        session.post.side_effect = requests.Timeout('private address')
        with self.assertRaisesRegex(RemotePlateError, '^REMOTE_TIMEOUT$'):
            RemotePlateReader('http://vision', session_factory=lambda: session).read(np.zeros((20, 20, 3), dtype=np.uint8))
        session.post.assert_called_once()
        session.close.assert_called_once()

    def test_http_failure_and_oversized_response_stop_processing(self):
        for status, chunks in ((503, []), (302, []), (200, [b' ' * (1024 * 1024 + 1)]), (200, [b'not json'])):
            session = Mock()
            session.post.return_value.status_code = status
            session.post.return_value.iter_content.return_value = chunks
            with self.subTest(status=status), self.assertRaises(RemotePlateError):
                RemotePlateReader('http://vision', session_factory=lambda: session).read(np.zeros((20, 20, 3), dtype=np.uint8))
            session.post.return_value.close.assert_called_once()

    def test_invalid_url_timeout_and_image_fail_before_request(self):
        for url in ('http://user:password@host', 'http://host?secret=1', 'file:///tmp/image', 'http://host:wrong'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                RemotePlateReader(url)
        for timeout in (True, 0, float('nan'), 301):
            with self.assertRaises(ValueError):
                RemotePlateReader('http://vision', timeout)
        factory = Mock()
        with self.assertRaises(ValueError):
            RemotePlateReader('http://vision', session_factory=factory).read(np.zeros((2, 2), dtype=np.uint8))
        factory.assert_not_called()

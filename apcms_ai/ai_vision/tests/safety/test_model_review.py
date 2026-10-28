"""모델 비교에서 미탐·예상 외 클래스·미완료 영상을 구분합니다."""
import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from ai_vision.safety.model_review import compare_expected, review_model
from ai_vision.safety.model_review_manifest import file_sha256
from ai_vision.tests.safety.test_live_fire_smoke import FakeModel


class ModelReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.model_path = self.root / 'model.pt'
        self.model_path.write_bytes(b'fake-model')
        image = self.root / 'image.png'
        cv2.imwrite(str(image), np.zeros((32, 40, 3), dtype=np.uint8))
        self.case = dict(case_id='fire', source_group='scene1', path=image, media_type='image',
                         sha256=file_sha256(image), expected=['FIRE'])

    def test_missing_and_unexpected_are_separate(self):
        result = compare_expected(['FIRE', 'SMOKE'], ['FIRE'])
        self.assertEqual(result['missing_classes'], ['SMOKE'])
        self.assertEqual(compare_expected([], ['SMOKE'])['unexpected_classes'], ['SMOKE'])

    def test_real_extraction_and_expected_label_comparison(self):
        result = review_model(FakeModel(), [self.case], self.root / 'out', model_path=self.model_path)
        self.assertEqual(result['cases'][0]['missing_classes'], [])
        self.assertEqual(result['cases'][0]['observed_classes'], ['FIRE'])
        self.assertTrue((self.root / 'out/fire/annotated.jpg').is_file())
        self.assertEqual(result['model_sha256'], file_sha256(self.model_path))
        self.assertEqual(result['status'], 'COMPLETED')

    def test_class_specific_review_records_both_model_hashes(self):
        sources={'FIRE':self.model_path,'SMOKE':self.model_path}
        result=review_model(FakeModel(),[self.case],self.root/'out',model_path=self.model_path,model_sources=sources)
        self.assertEqual(result['inference_mode'],'ACTUAL_CLASS_SPECIFIC_INFERENCE')
        self.assertEqual(set(result['model_sources']),{'FIRE','SMOKE'})
        for source in result['model_sources'].values():
            self.assertEqual(source['sha256'],file_sha256(self.model_path))

    def test_no_detection_is_reported_as_missing(self):
        result = review_model(FakeModel([]), [self.case], self.root / 'out', model_path=self.model_path)
        self.assertEqual(result['cases'][0]['missing_classes'], ['FIRE'])

    def test_existing_output_not_overwritten(self):
        output = self.root / 'existing'
        output.mkdir()
        with self.assertRaises(FileExistsError):
            review_model(FakeModel(), [self.case], output, model_path=self.model_path)

    def test_wrong_model_classes_rejected_before_results(self):
        model = FakeModel()
        model.names = {0: 'person'}
        with self.assertRaises(ValueError):
            review_model(model, [self.case], self.root / 'out', model_path=self.model_path)
        self.assertFalse((self.root / 'out').exists())

    def test_failed_video_cannot_be_reported_as_no_event(self):
        video = self.root / 'video.mp4'
        video.write_bytes(b'fake-video')
        case = dict(self.case, path=video, sha256=file_sha256(video), media_type='video')
        with patch('ai_vision.safety.model_review.run_live', return_value={'status': 'VIDEO_READ_FAILED'}):
            with self.assertRaisesRegex(RuntimeError, '정상 완료'):
                review_model(FakeModel(), [case], self.root / 'out', model_path=self.model_path)

    def test_partial_result_is_not_completed(self):
        video = self.root / 'video.mp4'
        video.write_bytes(b'fake-video')
        case = dict(self.case, case_id='unfinished_video', path=video,
                    sha256=file_sha256(video), media_type='video')
        with patch('ai_vision.safety.model_review.run_live', return_value={'status': 'ERROR'}):
            with self.assertRaises(RuntimeError):
                review_model(FakeModel(), [self.case, case], self.root / 'out', model_path=self.model_path)
        result = json.loads((self.root / 'out/review.json').read_text())
        self.assertEqual(result['status'], 'RUNNING')
        self.assertEqual(len(result['cases']), 1)
        self.assertEqual(result['expected_case_count'], 2)

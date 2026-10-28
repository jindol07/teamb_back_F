"""평가 자료 변조·중복과 잘못된 정답 형식으로 인한 비교 오류를 막습니다."""
import json
import tempfile
import unittest
from pathlib import Path

from ai_vision.safety.model_review_manifest import file_sha256, load_review_manifest, verify_case


class ReviewManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / 'normal.jpg'
        self.image.write_bytes(b'fixture')
        self.case = dict(case_id='normal', source_group='capture_session_1', media_type='image',
                         path='normal.jpg', sha256=file_sha256(self.image), expected=[])

    def load(self, cases):
        path = self.root / 'manifest.json'
        path.write_text(json.dumps({'purpose': 'diagnostic_review', 'cases': cases}), encoding='utf-8')
        return load_review_manifest(path)

    def test_normal_and_mixed_labels_supported(self):
        self.assertEqual(self.load([self.case])[0]['path'], self.image.resolve())
        self.case['expected'] = ['FIRE', 'SMOKE']
        self.assertEqual(self.load([self.case])[0]['expected'], ['FIRE', 'SMOKE'])

    def test_changed_media_is_rejected(self):
        cases = self.load([self.case])
        self.image.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, '변경'):
            verify_case(cases[0])

    def test_duplicate_image_cannot_inflate_case_count(self):
        with self.assertRaises(ValueError):
            self.load([self.case, dict(self.case, case_id='copied_image')])

    def test_path_id_and_incorrect_expected_types_rejected(self):
        for patch in ({'case_id': '../escape'}, {'expected': 'SMOKE'}, {'expected': ['SMOKE', 'SMOKE']},
                      {'expected': ['NORMAL']}, {'source_group': ''}, {'sha256': 'unknown'},
                      {'media_type': 'camera'}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.load([dict(self.case, **patch)])

    def test_empty_manifest_is_not_success(self):
        with self.assertRaises(ValueError):
            self.load([])

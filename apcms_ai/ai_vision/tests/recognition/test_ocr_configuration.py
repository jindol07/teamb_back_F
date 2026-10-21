# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_ocr_configuration.py

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.ocr_configuration import local_ocr_options, OCRConfigurationError
from ai_vision.recognition.recognition_models import RecognitionModels


class OCRConfigurationTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        patcher = patch.dict(os.environ, {}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def prepare(self):
        for name in ("det", "rec"):
            folder = self.root / name
            folder.mkdir()
            for filename in ("inference.yml", "inference.json", "inference.pdiparams"):
                (folder / filename).write_bytes(b"test")
            (folder / "inference.yml").write_text(f"Global:\n  model_name: test_{name}\n", encoding="utf-8")
        os.environ.update(VISION_OCR_DETECTION_MODEL_DIR="det", VISION_OCR_RECOGNITION_MODEL_DIR="rec")

    def test_default_preserves_existing_cache_behavior(self):
        self.assertEqual(local_ocr_options(self.root), {})

    def test_local_inference_paths_are_forwarded_to_factory(self):
        self.prepare()
        factory = Mock(return_value=object())
        RecognitionModels(self.root, ocr_factory=factory).ocr()
        self.assertEqual(factory.call_args.kwargs["text_detection_model_dir"], str((self.root / "det").resolve()))
        self.assertEqual(factory.call_args.kwargs["text_recognition_model_dir"], str((self.root / "rec").resolve()))
        self.assertEqual(factory.call_args.kwargs["text_detection_model_name"], "test_det")
        self.assertEqual(factory.call_args.kwargs["text_recognition_model_name"], "test_rec")
        self.assertNotIn("lang", factory.call_args.kwargs)

    def test_missing_or_unsafe_model_name_is_rejected(self):
        self.prepare()
        for content in ("{}", "Global: []", "Global:\n  model_name: '../other'", "!!python/object:builtins.object {}"):
            (self.root / "det" / "inference.yml").write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(OCRConfigurationError):
                local_ocr_options(self.root)

    def test_missing_or_empty_model_fails_before_factory(self):
        self.prepare()
        (self.root / "rec" / "inference.pdiparams").write_bytes(b"")
        factory = Mock()
        with self.assertRaises(OCRConfigurationError):
            RecognitionModels(self.root, ocr_factory=factory).ocr()
        factory.assert_not_called()

    def test_one_directory_or_empty_directory_setting_is_rejected(self):
        for values in ({"VISION_OCR_DETECTION_MODEL_DIR": "det"},
                       {"VISION_OCR_DETECTION_MODEL_DIR": "", "VISION_OCR_RECOGNITION_MODEL_DIR": "rec"}):
            with patch.dict(os.environ, values), self.assertRaises(OCRConfigurationError):
                local_ocr_options(self.root)

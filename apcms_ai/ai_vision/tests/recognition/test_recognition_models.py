# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_recognition_models.py

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.recognition_models import RecognitionModels


class RecognitionModelsTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        for name in ("yolo11n.pt", "license_plate_yolov8n.pt"):
            (self.root / name).write_bytes(b"mock weights")

    def test_only_requested_role_created_once(self):
        yolo, ocr = Mock(side_effect=lambda path: object()), Mock(return_value=object())
        models = RecognitionModels(self.root, yolo, ocr)
        self.assertEqual(yolo.call_count, 0)
        plate = models.plate()
        self.assertIs(models.plate(), plate)
        yolo.assert_called_once_with(self.root / "license_plate_yolov8n.pt")
        ocr.assert_not_called()
        vehicle = models.vehicle()
        self.assertIsNot(vehicle, plate)
        self.assertIs(models.vehicle(), vehicle)
        self.assertEqual(yolo.call_count, 2)

    def test_concurrent_first_calls_create_one_instance(self):
        factory = Mock(return_value=object())
        models = RecognitionModels(self.root, ocr_factory=factory)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: models.ocr(), range(16)))
        self.assertTrue(all(value is results[0] for value in results))
        factory.assert_called_once_with(lang="korean", use_doc_orientation_classify=False,
                                       use_doc_unwarping=False, use_textline_orientation=False, enable_mkldnn=False)

    def test_missing_unneeded_model_does_not_block_plate(self):
        (self.root / "yolo11n.pt").unlink()
        factory = Mock(return_value=object())
        models = RecognitionModels(self.root, yolo_factory=factory)
        models.plate()
        with self.assertRaises(FileNotFoundError):
            models.vehicle()
        self.assertEqual(factory.call_count, 1)

    def test_failed_initialization_is_not_cached(self):
        model = object()
        factory = Mock(side_effect=[RuntimeError("initialization failed"), model])
        models = RecognitionModels(self.root, ocr_factory=factory)
        with self.assertRaises(RuntimeError):
            models.ocr()
        self.assertIs(models.ocr(), model)
        self.assertIs(models.ocr(), model)
        self.assertEqual(factory.call_count, 2)

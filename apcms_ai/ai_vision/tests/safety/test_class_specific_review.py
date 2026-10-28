import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai_vision.safety.run_class_specific_review import main


class ClassSpecificReviewTests(unittest.TestCase):
    def test_missing_local_model_does_not_load_yolo(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch('ai_vision.safety.run_class_specific_review.load_review_manifest',return_value=[]):
                with self.assertRaises(FileNotFoundError):
                    main(['--manifest',str(root/'manifest.json'),'--fire-model',str(root/'missing.pt'),
                          '--smoke-model',str(root/'missing2.pt'),'--output',str(root/'out')])
            self.assertFalse((root/'out').exists())

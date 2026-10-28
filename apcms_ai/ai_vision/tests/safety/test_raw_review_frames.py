import tempfile
import unittest
from pathlib import Path
import numpy as np
import cv2
from ai_vision.safety.raw_review_frames import RawReviewFrames


class RawReviewFramesTests(unittest.TestCase):
    def test_original_pixels_and_limit_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            writer=RawReviewFrames(Path(folder)/'raw',limit=1)
            frame=np.full((20,30,3),91,np.uint8)
            writer(frame);writer(frame)
            self.assertEqual(writer.count,1)
            np.testing.assert_array_equal(cv2.imread(str(writer.directory/'frame_00001.png')),frame)
            self.assertFalse((writer.directory/'frame_00002.png').exists())

    def test_existing_directory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileExistsError):RawReviewFrames(folder)

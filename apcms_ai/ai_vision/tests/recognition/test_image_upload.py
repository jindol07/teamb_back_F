# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_image_upload.py

import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from ai_vision.recognition.image_upload import decode_uploaded_image, ImageUploadError, process_uploaded_image


class ImageUploadTests(unittest.TestCase):
    def test_combined_processing_validates_before_inference_and_preserves_result(self):
        expected = {"success": True}
        inference = Mock(return_value=expected)
        with self.assertRaises(ImageUploadError):
            process_uploaded_image(b"broken", inference)
        inference.assert_not_called()
        self.assertIs(process_uploaded_image(self.data, inference), expected)
        self.assertEqual(inference.call_args.args[0].shape, (20, 30, 3))

    def setUp(self):
        self.data = cv2.imencode(".png", np.full((20, 30, 3), 7, dtype=np.uint8))[1].tobytes()

    def test_valid_image_returns_original_bgr_pixels(self):
        frame = decode_uploaded_image(self.data)
        self.assertEqual(frame.shape, (20, 30, 3))
        self.assertTrue((frame == 7).all())

    def test_jpeg_and_grayscale_inputs_still_return_bgr_images(self):
        data = cv2.imencode(".jpg", np.full((20, 30), 80, dtype=np.uint8))[1].tobytes()
        frame = decode_uploaded_image(data)
        self.assertEqual(frame.shape, (20, 30, 3))
        self.assertEqual(frame.dtype, np.uint8)

    def test_file_and_pixel_limits_reject_before_opencv_decode(self):
        for setting, value in (("MAX_UPLOAD_BYTES", 1), ("MAX_IMAGE_PIXELS", 10)):
            with patch("ai_vision.recognition.image_upload." + setting, value), \
                    patch("ai_vision.recognition.image_upload.cv2.imdecode", side_effect=AssertionError("decode forbidden")):
                with self.assertRaises(ImageUploadError) as caught:
                    decode_uploaded_image(self.data)
                self.assertEqual(caught.exception.status_code, 413)

    def test_empty_and_invalid_headers_are_client_errors(self):
        for value in (b"", b"broken", None):
            with self.assertRaises(ImageUploadError) as caught:
                decode_uploaded_image(value)
            self.assertEqual(caught.exception.status_code, 400)

    def test_bad_decoder_output_and_decoder_error_are_client_errors(self):
        for output in (None, np.zeros((0, 0, 3), dtype=np.uint8)):
            with patch("ai_vision.recognition.image_upload.cv2.imdecode", return_value=output):
                with self.assertRaises(ImageUploadError) as caught:
                    decode_uploaded_image(self.data)
                self.assertEqual(caught.exception.status_code, 400)
        with patch("ai_vision.recognition.image_upload.cv2.imdecode", side_effect=cv2.error("private decode error")):
            with self.assertRaises(ImageUploadError) as caught:
                decode_uploaded_image(self.data)
            self.assertNotIn("private", str(caught.exception))

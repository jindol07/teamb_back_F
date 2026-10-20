# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_ocr_image_policy.py

import unittest

from ai_vision.recognition.ocr_image_policy import retry_image_size, RETRY_MAX_SIDE, RETRY_MAX_PIXELS


class OCRImagePolicyTests(unittest.TestCase):
    def test_small_plate_keeps_existing_four_times_scale(self):
        self.assertEqual(retry_image_size(200, 50), (800, 200))

    def test_large_and_extreme_shapes_stay_inside_both_limits(self):
        for width, height in ((1500, 1500), (10000, 300), (1, 20000000), (20000000, 1), (10**100, 10**100)):
            with self.subTest(shape=(width, height)):
                result = retry_image_size(width, height)
                self.assertTrue(all(1 <= side <= RETRY_MAX_SIDE for side in result))
                self.assertLessEqual(result[0] * result[1], RETRY_MAX_PIXELS)
        self.assertEqual(retry_image_size(1500, 1500), (2000, 2000))

    def test_aspect_ratio_preserved_with_pixel_rounding(self):
        width, height = retry_image_size(3000, 500)
        self.assertLessEqual(abs(width / height - 6), .01)

    def test_invalid_shape_rejected(self):
        for width, height in ((0, 10), (10, -1), (True, 10), (10, 2.5)):
            with self.assertRaises(ValueError):
                retry_image_size(width, height)

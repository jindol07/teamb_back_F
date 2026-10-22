# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_recognizer_lazy_loading.py

import builtins
import importlib.util
import unittest
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, MagicMock, patch

import numpy as np

from ai_vision.paths import BASE_DIR
from ai_vision.recognition.live_gate_processor import LiveGateProcessor
from ai_vision.recognition.recognition_models import RecognitionModels


class RecognizerLazyLoadingTests(unittest.TestCase):
    def test_complete_plate_with_separator_is_cleaned_before_retry(self):
        module = self.load_module()
        image = np.full((40, 150, 3), 230, dtype=np.uint8)
        # 1. 구분자 제거만 필요한 번호를 다른 재시도 번호로 덮어쓰지 않습니다.
        for separator in ("·", "•", "ㆍ", ":", ".", "-", "_"):
            with self.subTest(separator=separator), \
                    patch.object(module, "run_paddleocr", return_value=f"91소{separator}6408"), \
                    patch.object(module, "retry_ocr", return_value=("92소6408", "KOREAN_VALID")) as retry:
                result = module.recognize_plate(image)
                self.assertEqual(result["first_ocr"], f"91소{separator}6408")
                self.assertEqual(result["first_type"], "REVIEW")
                self.assertEqual((result["plate_number"], result["plate_type"]),
                                 ("91소6408", "KOREAN_VALID"))
                self.assertEqual(result["retry_ocr"], "")
                retry.assert_not_called()

    def test_missing_korean_character_still_retries_without_guessing(self):
        module = self.load_module()
        image = np.full((40, 150, 3), 230, dtype=np.uint8)
        # 2. 실제 시험의 ± 오독은 구분자 제거로 복구할 수 없습니다.
        with patch.object(module, "run_paddleocr", return_value="91±6408"), \
                patch.object(module, "retry_ocr", return_value=("9116408", "REVIEW")) as retry:
            result = module.recognize_plate(image)
            self.assertEqual((result["plate_number"], result["plate_type"]), ("91±6408", "REVIEW"))
            self.assertEqual(result["retry_ocr"], "9116408")
            retry.assert_called_once_with(image)

    def test_plate_detection_rejects_flat_vent_before_selecting_best_candidate(self):
        module = self.load_module()
        def detection(coords, confidence):
            box = Mock()
            box.xyxy = np.array([coords], dtype=float)
            box.conf = np.array([confidence])
            return box
        vent = detection([1, 1, 101, 9], .98)
        plate = detection([5, 15, 85, 55], .4)
        models = MagicMock()
        with patch.object(module, '_models', models):
            models.plate.return_value.return_value = [Mock(boxes=[vent, plate])]
            result = module.detect_best_plate(np.zeros((80, 120, 3), dtype=np.uint8))
            self.assertEqual(result['box'], (5, 15, 85, 55))
            models.plate.return_value.return_value = [Mock(boxes=[vent])]
            self.assertIsNone(module.detect_best_plate(np.zeros((80, 120, 3), dtype=np.uint8)))

    def test_two_line_regions_use_geometry_without_guessing_characters(self):
        module = self.load_module()
        upper = [[14, 8], [65, 7], [66, 18], [15, 20]]
        lower = [[6, 16], [70, 16], [70, 40], [6, 40]]
        self.assertEqual(module._join_plate_ocr(["8631", "37어"], [lower, upper]), "37어8631")
        # 실제 오독 01을 한글 어로 임의 복원하지 않습니다.
        self.assertEqual(module._join_plate_ocr(["8631", "3701"], [lower, upper]), "37018631")
        self.assertEqual(module._join_plate_ocr(["8631", "37어"], []), "863137어")
        self.assertEqual(module._join_plate_ocr(["8631", "37어"], [lower, lower]), "863137어")
        self.assertEqual(module._join_plate_ocr(["8631", "37어", "서울"], [lower, upper, upper]), "863137어서울")

    def test_yellow_background_keeps_ocr_but_blocks_valid_classification(self):
        module = self.load_module()
        from ai_vision.recognition.plate_consensus import summarize_plate_samples
        samples = []
        yellow = np.full((40, 150, 3), (0, 210, 230), dtype=np.uint8)
        with patch.object(module, "run_paddleocr", return_value="59바3151"):
            for index in (0, 10):
                result = module.recognize_plate(yellow)
                self.assertEqual(result["plate_number"], "59바3151")
                self.assertEqual(result["first_type"], "KOREAN_VALID")
                self.assertEqual(result["plate_type"], "REVIEW")
                self.assertTrue(result["review_reasons"])
                samples.append(dict(result, frame_index=index, video_seconds=index / 30))
            self.assertEqual(module.recognize_plate(np.full_like(yellow, 230))["plate_type"], "KOREAN_VALID")
        self.assertEqual(summarize_plate_samples(samples)["status"], "NO_VALID_KOREAN_PLATE")

    def test_small_yellow_patch_does_not_block_white_plate(self):
        module = self.load_module()
        image = np.full((40, 150, 3), 230, dtype=np.uint8)
        image[:5] = (0, 210, 230)
        self.assertFalse(module._has_yellow_plate_background(image))
        self.assertFalse(module._has_yellow_plate_background(np.zeros((0, 0, 3), dtype=np.uint8)))

    def test_small_lower_decoration_requires_complete_plate_and_geometry(self):
        # 1. 실제 영상에서 번호 두 조각 아래에 영문 장식이 함께 검출된 상황입니다.
        module = self.load_module()
        def box(top, bottom):
            return [[0, top], [100, top], [100, bottom], [0, bottom]]
        main = [box(10, 70), box(20, 80)]
        self.assertEqual(module._join_plate_ocr(
            ["30저", "9516", "FOMYUNDRI"], main + [box(90, 100)]), "30저9516")
        # 2. 충돌하는 숫자·한글, 큰 영문, 좌표 누락은 임의로 제거하지 않습니다.
        for texts, polygons in [
            (["30저", "9516", "AB123"], main + [box(90, 100)]),
            (["30저", "9516", "서울"], main + [box(90, 100)]),
            (["30저", "9516", "HYUNDAI"], main + [box(10, 70)]),
            (["30저", "9516", "HYUNDAI"], main + [box(50, 60)]),
            (["30저", "9516", "HYUNDAI"], []),
            (["30", "9516", "HYUNDAI"], main + [box(90, 100)]),
            (["30저9516", "31라0567", "HYUNDAI"], main + [box(90, 100)]),
            (["30저", "9516", "HYUNDAI"], main + [box(float("nan"), 100)]),
        ]:
            with self.subTest(texts=texts, polygons=polygons):
                self.assertEqual(module._join_plate_ocr(texts, polygons), "".join(texts))

    def test_ocr_uses_text_regions_to_exclude_lower_decoration(self):
        # 3. 좌표 처리 규칙이 실제 OCR 호출 경로에도 적용되는지 검사합니다.
        module = self.load_module()
        models = MagicMock()
        models.ocr.return_value.predict.return_value = [{
            "rec_texts": ["30저", "9516", "FOMYUNDRI"],
            "rec_polys": [np.array(p) for p in [
                [[89, 13], [226, 22], [221, 79], [85, 69]],
                [[246, 20], [429, 33], [424, 94], [241, 81]],
                [[232, 88], [290, 93], [289, 103], [231, 98]]]]}]
        with patch.object(module, "_models", models), \
                patch.object(module.cv2, "imwrite", return_value=True), \
                patch.object(module.tempfile, "TemporaryDirectory") as temporary:
            temporary.return_value.__enter__.return_value = "unused-test-path"
            result = module.recognize_plate(np.zeros((120, 500, 3), dtype=np.uint8))
        self.assertEqual((result["plate_number"], result["plate_type"]), ("30저9516", "KOREAN_VALID"))

    def load_module(self):
        spec = importlib.util.spec_from_file_location("ai_vision._recognizer_lazy_test", BASE_DIR / "recognition/recognizer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_import_and_text_processing_do_not_import_model_backends(self):
        original_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.split(".")[0] in {"ultralytics", "paddleocr", "paddle"}:
                raise AssertionError("model backend imported before use")
            return original_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=guarded):
            module = self.load_module()
            self.assertEqual(module.classify_plate_format(module.cleanup_plate_text("91소·6408")), "KOREAN_VALID")
            self.assertEqual(module.recognize_image(None)["vehicle_count"], 0)

    def test_plate_detection_does_not_request_vehicle_or_ocr(self):
        module = self.load_module()
        models = MagicMock()
        models.plate.return_value = Mock(return_value=[])
        with patch.object(module, "_models", models):
            self.assertIsNone(module.detect_best_plate(np.zeros((20, 20, 3), dtype=np.uint8)))
        models.plate.assert_called_once()
        models.vehicle.assert_not_called()
        models.ocr.assert_not_called()

    def test_full_image_detection_still_uses_vehicle_fallback_and_response_shape(self):
        module = self.load_module()
        model = Mock(return_value=[])
        models = MagicMock()
        models.vehicle.return_value = model
        with patch.object(module, "_models", models):
            result = module.recognize_image(np.zeros((20, 20, 3), dtype=np.uint8))
        self.assertEqual((result["success"], result["vehicle_count"], result["vehicle_fallback_used"]), (False, 0, True))
        self.assertEqual(model.call_count, 2)
        models.plate.assert_not_called()
        models.ocr.assert_not_called()

    def test_ocr_only_requests_ocr_model_and_preserves_output(self):
        module = self.load_module()
        models = MagicMock()
        models.ocr.return_value.predict.return_value = [{"rec_texts": ["91소", "6408"]}]
        with patch.object(module, "_models", models), \
                patch.object(module.cv2, "imwrite", return_value=True), \
                patch.object(module.tempfile, "TemporaryDirectory") as temporary:
            temporary.return_value.__enter__.return_value = "unused-test-path"
            result = module.recognize_plate(np.zeros((20, 20, 3), dtype=np.uint8))
        self.assertEqual((result["plate_number"], result["plate_type"]), ("91소6408", "KOREAN_VALID"))
        models.ocr.assert_called_once()
        models.vehicle.assert_not_called()
        models.plate.assert_not_called()

    def test_live_crop_path_does_not_request_another_vehicle_model(self):
        from ai_vision.recognition import recognizer
        models = MagicMock()
        models.plate.return_value = Mock(return_value=[])
        with patch.object(recognizer, "_models", models):
            result = LiveGateProcessor._read_plate(np.zeros((20, 20, 3), dtype=np.uint8))
        self.assertEqual(result["plate_type"], "NOT_DETECTED")
        models.vehicle.assert_not_called()
        models.plate.assert_called_once()
        models.ocr.assert_not_called()

    def test_ocr_generator_iteration_remains_inside_inference_lock(self):
        module = self.load_module()
        active, peak = 0, 0
        guard = threading.Lock()
        class Reader:
            def predict(self, path):
                nonlocal active, peak
                with guard:
                    active += 1
                    peak = max(peak, active)
                try:
                    time.sleep(.01)
                    yield {"rec_texts": ["91소6408"]}
                finally:
                    with guard:
                        active -= 1
        models = RecognitionModels(ocr_factory=lambda **kwargs: Reader())
        with patch.object(module, "_models", models), patch.object(module.cv2, "imwrite", return_value=True), \
                patch.object(module.tempfile, "TemporaryDirectory") as temporary:
            temporary.return_value.__enter__.return_value = "unused-test-path"
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(module.run_paddleocr, [np.zeros((20, 20, 3), dtype=np.uint8)] * 2))
        self.assertEqual(results, ["91소6408", "91소6408"])
        self.assertEqual(peak, 1)

    def test_retry_resize_uses_bounded_dimensions_before_allocation(self):
        module = self.load_module()
        with patch.object(module.cv2, "resize", return_value=np.zeros((10, 10, 3), dtype=np.uint8)) as resize, \
                patch.object(module, "run_paddleocr", return_value="91소6408"):
            result = module.retry_ocr(np.zeros((1500, 1500, 3), dtype=np.uint8))
        self.assertEqual(resize.call_args.args[1], (2000, 2000))
        self.assertEqual(result, ("91소6408", "KOREAN_VALID"))

    def test_ocr_temporary_png_preserves_pixels_and_is_removed(self):
        module = self.load_module()
        import cv2
        from pathlib import Path
        original = np.arange(20 * 30 * 3, dtype=np.uint8).reshape((20, 30, 3))
        paths = []
        class Reader:
            def predict(self, path):
                paths.append(Path(path))
                self_image = cv2.imdecode(np.frombuffer(Path(path).read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
                np.testing.assert_array_equal(self_image, original)
                return [{"rec_texts": ["91소6408"]}]
        models = RecognitionModels(ocr_factory=lambda **kwargs: Reader())
        with patch.object(module, "_models", models):
            self.assertEqual(module.run_paddleocr(original), "91소6408")
        self.assertEqual(paths[0].suffix, ".png")
        self.assertFalse(paths[0].exists())

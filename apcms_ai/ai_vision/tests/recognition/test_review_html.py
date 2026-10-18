# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_review_html.py

import unittest
from html.parser import HTMLParser
from ai_vision.recognition.review_html import render_review


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class ReviewHTMLTests(unittest.TestCase):
    def setUp(self):
        self.item = {"track_id": 7, "screen_direction": "DOWN", "video_seconds": 1,
                     "plate_status": "NO_VALID_KOREAN_PLATE", "plate_number": ""}
        self.snapshot = {"run_id": "demo", "snapshot_sha256": "a" * 64, "items": [self.item]}

    def test_ocr_html_is_escaped_and_external_resources_are_absent(self):
        evidence = {7: [{"frame_index": 5, "video_seconds": 1,
                         "ocr_text": '<script>alert("x")</script>', "image": None}]}
        html = render_review(self.snapshot, evidence, [self.item])
        parser = Tags()
        parser.feed(html)
        self.assertNotIn("script", [tag for tag, _ in parser.tags])
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("저장된 번호판 이미지 없음", html)
        self.assertIn("Content-Security-Policy", html)
        self.assertFalse(any(tag in {"link", "iframe", "form"} for tag, _ in parser.tags))

    def test_inline_image_and_page_scope_are_shown(self):
        evidence = {7: [{"frame_index": 5, "video_seconds": 1, "ocr_text": "foreign",
                         "image": {"base64": "abc=", "sha256": "b" * 64}}]}
        html = render_review(self.snapshot, evidence, [self.item], offset=20)
        parser = Tags()
        parser.feed(html)
        images = [attrs for tag, attrs in parser.tags if tag == "img"]
        self.assertEqual(images[0]["src"], "data:image/jpeg;base64,abc=")
        self.assertIn("offset 20", html)
        self.assertIn("읽기 전용", html)

    def test_empty_page_and_track_without_samples_are_explicit(self):
        self.assertIn("표시할 차량이 없습니다", render_review(self.snapshot, {}, []))
        self.assertIn("저장된 OCR 표본이 없습니다", render_review(self.snapshot, {7: []}, [self.item]))

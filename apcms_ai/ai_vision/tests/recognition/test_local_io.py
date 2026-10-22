# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_local_io.py

import tempfile
import unittest
import os
import io
from pathlib import Path
from unittest.mock import patch

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import decode_object, iter_jsonl, read_json, write_json_atomic


class LocalIOTests(unittest.TestCase):
    def test_excessive_json_nesting_is_validation_error(self):
        with self.assertRaises(ValueError):
            decode_object('{"nested":' * 2000 + '{}' + '}' * 2000)

    def test_json_read_is_bounded_even_when_file_metadata_is_unreliable(self):
        # 파일이 자라는 상황에서도 read()가 무제한 호출되지 않는지 확인합니다.
        class Stream(io.BytesIO):
            def read(inner, size=-1):
                self.assertEqual(size, 9)
                return super().read(size)
        with patch("pathlib.Path.open", return_value=Stream(b"{}" + b" " * 100)):
            with self.assertRaises(ValueError):
                read_json(self.root / "growing.json", max_bytes=8)

    def test_exact_byte_limit_bom_and_invalid_limits(self):
        path = self.root / "bounded.json"
        path.write_bytes(b"\xef\xbb\xbf{}")
        self.assertEqual(read_json(path, max_bytes=5), {})
        with self.assertRaises(ValueError):
            read_json(path, max_bytes=4)
        for limit in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                read_json(path, max_bytes=limit)

    def test_transient_windows_lock_retried(self):
        path = self.root / "locked.json"
        replace = os.replace
        attempts = []
        def delayed(source, target):
            attempts.append(1)
            if len(attempts) == 1:
                raise PermissionError("temporary lock")
            return replace(source, target)
        with patch("ai_vision.recognition.local_io.os.replace", side_effect=delayed):
            write_json_atomic(path, {"ok": True})
        self.assertEqual(read_json(path), {"ok": True})
        self.assertEqual(len(attempts), 2)

    def setUp(self):
        # 1. 테스트 자료는 쓰기 가능한 프로젝트 결과 폴더 아래에서만 생성·정리
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)

    def test_invalid_json_not_silently_accepted(self):
        for text in ['{"n":NaN}', '{"n":1e999}', '{"n":1,"n":2}', '[]']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                decode_object(text)

    def test_atomic_failure_preserves_original(self):
        path = self.root / "result.json"
        write_json_atomic(path, {"old": True})
        with patch("ai_vision.recognition.local_io.os.replace", side_effect=OSError("busy")):
            with self.assertRaises(OSError):
                write_json_atomic(path, {"new": True})
        self.assertEqual(read_json(path), {"old": True})
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_jsonl_reports_corrupt_line_and_limits(self):
        path = self.root / "rows.jsonl"
        path.write_text('{}\nnot-json\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "2번째"):
            list(iter_jsonl(path))
        path.write_text('{}\n{}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "기록 수"):
            list(iter_jsonl(path, max_rows=1))


if __name__ == "__main__":
    unittest.main()

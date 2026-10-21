# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_run_checks.py

import contextlib
import ast
import io
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from ai_vision.tests.run_checks import MODULES, build_suite, main


class RunChecksTests(unittest.TestCase):
    def test_registered_modules_have_source_files(self):
        # 목록만 남고 실제 테스트 파일이 누락되는 경우를 바로 발견합니다.
        root = Path(__file__).resolve().parents[3]
        for module in MODULES:
            self.assertTrue(root.joinpath(*module.split('.')).with_suffix('.py').is_file(), module)

    def test_local_import_targets_exist_without_loading_models(self):
        # 직접·상대 import를 정적으로 검사하므로 카메라·모델을 생성하지 않습니다.
        root = Path(__file__).resolve().parents[3]
        for source in (root / "ai_vision").rglob("*.py"):
            package = list(source.relative_to(root).parts[:-1])
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8-sig"))):
                names = []
                if isinstance(node, ast.Import):
                    names = [item.name for item in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        names = ['.'.join(package[:len(package) - node.level + 1] +
                                          (node.module.split('.') if node.module else []))]
                    elif node.module:
                        names = [node.module]
                for name in names:
                    if name == "ai_vision" or name.startswith("ai_vision."):
                        target = root.joinpath(*name.split('.'))
                        self.assertTrue(target.with_suffix('.py').is_file() or target.is_dir(),
                                        f"{source.name}: {name}")

    def test_manifest_unique_and_excludes_heavy_experiments(self):
        self.assertEqual(len(MODULES), len(set(MODULES)))
        for name in ("test_yolo", "test_pipeline", "test_paddleocr", "test_trocr"):
            self.assertNotIn("ai_vision.tests.recognition." + name, MODULES)
        self.assertIn("ai_vision.tests.recognition.test_recognize_upload_api", MODULES)

    def test_list_does_not_load_or_run_tests(self):
        with patch("ai_vision.tests.run_checks.build_suite") as build, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--list"]), 0)
        build.assert_not_called()
        self.assertEqual(tuple(output.getvalue().splitlines()), MODULES)

    def test_loader_uses_explicit_module_manifest(self):
        loader = Mock()
        self.assertIs(build_suite(loader), loader.loadTestsFromNames.return_value)
        loader.loadTestsFromNames.assert_called_once_with(MODULES)

    def test_failure_is_nonzero_and_options_forwarded(self):
        for successful, expected in ((True, 0), (False, 1)):
            with patch("ai_vision.tests.run_checks.build_suite", return_value="suite"), \
                    patch("ai_vision.tests.run_checks.unittest.TextTestRunner") as runner:
                runner.return_value.run.return_value.wasSuccessful.return_value = successful
                self.assertEqual(main(["--failfast", "-v"]), expected)
                runner.assert_called_once_with(verbosity=2, failfast=True)
                runner.return_value.run.assert_called_once_with("suite")

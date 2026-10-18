# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_tracking_config.py

import argparse
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.recognition.tracking_config import parse_with_config, validate_config


class TrackingConfigTests(unittest.TestCase):
    def test_self_crossing_and_disconnected_line_rejected(self):
        config = self.config()
        config["roi"] = [0, 0, 1, .8, 0, 1, .8, 0]
        with self.assertRaisesRegex(ValueError, "교차"):
            validate_config(config)
        config = self.config()
        config["line_y"] = .8
        with self.assertRaisesRegex(ValueError, "겹치지"):
            validate_config(config)
    def config(self):
        return {"tracker": "botsort", "line_y": .36, "line_x": [0, .23],
                "roi": [0, .18, .35, .18, .23, .4, 0, .5]}

    def parser(self):
        # 1. 모델을 불러오지 않고 명령 옵션과 설정 파일의 우선순위만 시험
        parser = argparse.ArgumentParser()
        parser.add_argument("--tracker", choices=["bytetrack", "botsort"], default="bytetrack")
        parser.add_argument("--line-y", type=float, default=.6)
        parser.add_argument("--line-x", type=float, nargs=2, default=[.15, .9])
        parser.add_argument("--roi", type=float, nargs=8, default=[.1, 1, .365, .24, .64, .24, .92, 1])
        return parser

    def test_config_overrides_default_and_cli_overrides_config(self):
        with patch.object(Path, "read_text", return_value=json.dumps(self.config())):
            loaded = parse_with_config(self.parser(), ["--config", "sample.json"])
            overridden = parse_with_config(self.parser(), ["--config", "sample.json", "--line-y", ".4"])
        self.assertEqual(loaded.line_y, .36)
        self.assertEqual(loaded.tracker, "botsort")
        self.assertEqual(overridden.line_y, .4)

    def test_defaults_unchanged_without_config(self):
        args = parse_with_config(self.parser(), [])
        self.assertEqual(args.line_y, .6)
        self.assertEqual(args.tracker, "bytetrack")

    def test_unknown_field_rejected(self):
        config = self.config()
        config["line_yy"] = .5
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_invalid_coordinates_rejected(self):
        # 2. 형식상 숫자로 처리되기 쉬운 bool/NaN과 잘못된 범위를 차단
        for value in [True, float("nan"), float("inf"), -.1, 1.1]:
            with self.subTest(value=value):
                config = self.config()
                config["line_y"] = value
                with self.assertRaises(ValueError):
                    validate_config(config)

    def test_empty_region_rejected(self):
        config = self.config()
        config["roi"] = [0, 0, .2, 0, .4, 0, .6, 0]
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_saved_profiles_match_verified_pixel_coordinates(self):
        # 3. 저장한 설정이 기존 실제 실행의 기준선과 관심 영역을 그대로 재현하는지 확인
        folder = Path(__file__).resolve().parents[2] / "data" / "tracking_configs"
        expected = {"traffic_near": (432, [192, 1152], "botsort"),
                    "traffic_far": (259, [0, 294], "bytetrack")}
        for name, (y, xs, tracker) in expected.items():
            with self.subTest(profile=name):
                config = validate_config(json.loads((folder / f"{name}.json").read_text(encoding="utf-8")))
                self.assertEqual(int(config["line_y"] * 720), y)
                self.assertEqual([int(x * 1280) for x in config["line_x"]], xs)
                self.assertEqual(config["tracker"], tracker)


if __name__ == "__main__":
    unittest.main()

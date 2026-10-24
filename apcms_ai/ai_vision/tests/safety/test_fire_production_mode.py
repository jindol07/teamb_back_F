"""화재·연기 시험/운영 모드 경계: 실제 카메라·실제 서버 없이 검증합니다."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_vision.safety import fire_alert_live as live
from ai_vision.safety import fire_alert_sender as sender
from ai_vision.safety.live_fire_smoke import LiveConfig, run_live
from ai_vision.tests.safety.test_fire_alert_sender import SAMPLE_SUMMARY, transition
from ai_vision.tests.safety.test_live_fire_smoke import FakeCapture, FakeModel


class FireProductionModeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def write_results(self, record_type="FIRE_SMOKE_LIVE_PRODUCTION", source="CAMERA"):
        summary = dict(SAMPLE_SUMMARY, record_type=record_type, source=source, source_name="camera_0")
        (self.folder / "alert_session.json").write_text(json.dumps(summary), encoding="utf8")
        (self.folder / "summary.json").write_text(json.dumps(summary), encoding="utf8")
        (self.folder / "incident_history.json").write_text(
            json.dumps({"transitions": [transition()]}), encoding="utf8")
        return summary

    # 1. 탐지기에서 분류를 결정하고 동일한 모드를 sidecar/summary에 사용
    def test_01_default_camera_is_test(self):
        output = self.folder / "default"
        cfg = LiveConfig(output_dir=output, max_frames=1, max_seconds=0,
                         publish_alert_session=True)
        result = run_live(cfg, model=FakeModel(boxes=[]), capture=FakeCapture(frames=4))
        meta = json.loads((output / "alert_session.json").read_text(encoding="utf8"))
        self.assertEqual((result["record_type"], meta["record_type"]),
                         ("FIRE_SMOKE_LIVE_TEST", "FIRE_SMOKE_LIVE_TEST"))

    def test_02_production_camera_sidecar_matches_summary(self):
        output = self.folder / "production"
        cfg = LiveConfig(output_dir=output, max_frames=1, max_seconds=0,
                         publish_alert_session=True, production_camera=True)
        result = run_live(cfg, model=FakeModel(boxes=[]), capture=FakeCapture(frames=4))
        meta = json.loads((output / "alert_session.json").read_text(encoding="utf8"))
        self.assertEqual((result["record_type"], meta["record_type"]),
                         ("FIRE_SMOKE_LIVE_PRODUCTION", "FIRE_SMOKE_LIVE_PRODUCTION"))
        self.assertEqual(result["source"], "CAMERA")

    def test_03_video_cannot_claim_production(self):
        with self.assertRaisesRegex(ValueError, "CAMERA"):
            LiveConfig(video_path="replay.mp4", production_camera=True)

    def test_04_production_flag_must_be_boolean(self):
        with self.assertRaisesRegex(ValueError, "True/False"):
            LiveConfig(production_camera="true")

    # 2. JSON 분류가 누락·오염됐을 때 운영으로 오인하지 않음
    def test_05_production_camera_payload_has_is_test_false(self):
        summary = self.write_results()
        payload = sender._normalize_transition(transition(), summary)
        self.assertIs(payload["is_test"], False)
        self.assertEqual(payload["source"]["kind"], "CAMERA")

    def test_06_test_video_remains_test(self):
        summary = self.write_results("FIRE_SMOKE_LIVE_TEST", "VIDEO")
        self.assertIs(sender._normalize_transition(transition(), summary)["is_test"], True)

    def test_07_unknown_record_type_rejected(self):
        summary = self.write_results("FIRE_SMOKE_OLD_UNKNOWN")
        with self.assertRaisesRegex(ValueError, "record_type"):
            sender._normalize_transition(transition(), summary)

    def test_08_production_label_for_video_rejected(self):
        summary = self.write_results("FIRE_SMOKE_LIVE_PRODUCTION", "VIDEO")
        with self.assertRaisesRegex(ValueError, "record_type"):
            sender._normalize_transition(transition(), summary)

    # 3. 실제 송신은 별도 승인 + HTTPS + 인증키를 요구
    def test_09_production_send_needs_optin(self):
        self.write_results()
        payloads = sender.build_payloads(self.folder)
        with self.assertRaisesRegex(ValueError, "allow-production-records"):
            sender.validate_delivery_policy(payloads, "https://example.com/alert")

    def test_10_production_send_rejects_http_even_localhost(self):
        self.write_results()
        payloads = sender.build_payloads(self.folder)
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            sender.validate_delivery_policy(payloads, "http://127.0.0.1:8765/alert",
                                            allow_production_records=True)

    def test_11_production_with_test_allow_flag_rejected(self):
        self.write_results()
        payloads = sender.build_payloads(self.folder)
        with self.assertRaisesRegex(ValueError, "allow-test-records"):
            sender.validate_delivery_policy(payloads, "https://example.com/alert",
                                            allow_test_records=True,
                                            allow_production_records=True)

    def test_12_live_preflight_rejects_missing_optin_without_starting_camera(self):
        with self.assertRaisesRegex(ValueError, "allow-production-records"):
            live.run_launcher(self.folder / "new", ["--camera", "0", "--production-camera"],
                              send=True, url="https://example.com/alert", token="fake",
                              process_factory=lambda _: self.fail("감지기가 시작되면 안 됩니다"))
        self.assertFalse((self.folder / "new").exists())

    def test_13_live_preflight_rejects_video_production(self):
        with self.assertRaisesRegex(ValueError, "--video"):
            live.run_launcher(self.folder / "new", ["--video", "replay.mp4", "--production-camera"],
                              process_factory=lambda _: self.fail("감지기가 시작되면 안 됩니다"))

    def test_14_live_preflight_requires_token(self):
        with self.assertRaisesRegex(ValueError, "인증키"):
            live.run_launcher(self.folder / "new", ["--camera", "0", "--production-camera"],
                              send=True, url="https://example.com/alert",
                              allow_production_records=True,
                              process_factory=lambda _: self.fail("감지기가 시작되면 안 됩니다"))

    def test_15_live_production_no_optin_does_not_checkpoint(self):
        self.write_results()
        with self.assertRaisesRegex(ValueError, "allow-production-records"):
            live.delivery_cycle(self.folder, send=True, url="https://example.com/alert",
                                token="fake", post=lambda *a, **kw: self.fail("POST 금지"))
        self.assertFalse((self.folder / "fire_alert_sent_state.json").exists())

    def test_16_live_production_approved_mock_post(self):
        self.write_results()
        recorded = []
        def fake_post(payload, url, **kwargs):
            recorded.append((payload, url))
            return 200
        result = live.delivery_cycle(self.folder, send=True, url="https://example.com/alert",
                                     token="fake", allow_production_records=True, post=fake_post)
        self.assertEqual(result["new"], 1)
        self.assertIs(recorded[0][0]["is_test"], False)
        self.assertTrue((self.folder / "fire_alert_sent_state.json").exists())
        replay = live.delivery_cycle(self.folder, send=True, url="https://example.com/alert",
                                     token="fake", allow_production_records=True, post=fake_post)
        self.assertEqual(replay["new"], 0)
        self.assertEqual(len(recorded), 1)

    def test_17_sender_cli_production_no_token_rejected(self):
        self.write_results()
        with patch.dict("os.environ", {"FIRE_ALERT_TOKEN": ""}), contextlib.redirect_stdout(io.StringIO()) as log:
            code = sender.main(["--results", str(self.folder), "--send",
                                "--allow-production-records", "--url", "https://example.com/alert"])
        self.assertEqual(code, 1)
        self.assertIn("인증키", log.getvalue())
        self.assertFalse((self.folder / "fire_alert_sent_state.json").exists())

    def test_18_live_cli_default_remains_dry_run(self):
        with patch.object(live, "run_launcher", return_value=0) as mock_launcher:
            self.assertEqual(live.main(["--output", str(self.folder / "new"), "--",
                                        "--camera", "0", "--production-camera"]), 0)
        self.assertFalse(mock_launcher.call_args.kwargs["send"])
        self.assertIn("--production-camera", mock_launcher.call_args.args[1])


if __name__ == "__main__":
    unittest.main()

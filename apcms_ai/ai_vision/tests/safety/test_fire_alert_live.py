"""실시간 알림: 기존 감지기 호환성과 전이 ID/전송 보호를 검증합니다."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ai_vision.safety import fire_alert_live as live
from ai_vision.safety import fire_alert_sender as sender
from ai_vision.safety.live_fire_smoke import LiveConfig, main as detection_main, run_live
from ai_vision.tests.safety.test_fire_alert_sender import SAMPLE_SUMMARY, mock_server, transition
from ai_vision.tests.safety.test_live_fire_smoke import FakeCapture, FakeModel


class LiveAlertUnitTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "results"
        self.folder.mkdir()
        self.preview = set()
        self.rows = [transition("SUSPECTED", frame=17), transition("ONGOING", frame=30),
                     transition("CLEARED", frame=50), transition("REOPENED", frame=90)]

    def populate(self, rows=None, *, finalized=False):
        meta = dict(SAMPLE_SUMMARY)
        if finalized:
            meta["status"] = "VIDEO_END"
            name = "summary.json"
        else:
            meta["status"] = "RUNNING"
            name = "alert_session.json"
        (self.folder / name).write_text(json.dumps(meta), encoding="utf-8")
        (self.folder / "incident_history.json").write_text(json.dumps({"transitions": rows if rows is not None else self.rows}), encoding="utf-8")

    # 1. 사건 기록 -> 안정된 전송 데이터
    def test_01_no_files_is_empty(self):
        self.assertEqual(live.load_live_payloads(self.folder), [])

    def test_02_no_history_is_empty(self):
        (self.folder / "alert_session.json").write_text(json.dumps(SAMPLE_SUMMARY), encoding="utf-8")
        self.assertEqual(live.load_live_payloads(self.folder), [])

    def test_03_session_sidecar_creates_three_actionable_payloads(self):
        self.populate()
        rows = live.load_live_payloads(self.folder)
        self.assertEqual([x["status"] for x in rows], ["SUSPECTED", "CLEARED", "REOPENED"])
        self.assertTrue(all(x["is_test"] for x in rows))

    def test_04_same_ids_after_summary_created(self):
        self.populate()
        current = [x["transition_id"] for x in live.load_live_payloads(self.folder)]
        self.populate(finalized=True)
        completed = [x["transition_id"] for x in sender.build_payloads(self.folder)]
        self.assertEqual(current, completed)

    def test_05_duplicate_transition_removed(self):
        self.populate([self.rows[0], self.rows[0]])
        self.assertEqual(len(live.load_live_payloads(self.folder)), 1)

    def test_06_invalid_event_fails_closed(self):
        self.populate([{"event_id": "bad"}])
        with self.assertRaises(ValueError):
            live.load_live_payloads(self.folder)

    def test_07_invalid_json_fails_closed(self):
        self.populate()
        (self.folder / "incident_history.json").write_text('{ "transitions": [}', encoding="utf-8")
        with self.assertRaises(ValueError):
            live.load_live_payloads(self.folder)

    # 2. DRY-RUN / 전송 / 중복 방지
    def test_08_dry_run_writes_preview_and_no_checkpoint(self):
        self.populate()
        result = live.delivery_cycle(self.folder, preview_ids=self.preview)
        self.assertEqual(result["new"], 3)
        self.assertFalse((self.folder / "fire_alert_sent_state.json").exists())
        p = json.loads((self.folder / "fire_alert_live_preview.json").read_text(encoding="utf-8"))
        self.assertEqual(len(p["alerts"]), 3)

    def test_09_dry_run_repeated_no_duplicate(self):
        self.populate()
        live.delivery_cycle(self.folder, preview_ids=self.preview)
        self.assertEqual(live.delivery_cycle(self.folder, preview_ids=self.preview)["new"], 0)

    def test_10_new_transition_only_processed_once(self):
        self.populate(self.rows[:1])
        self.assertEqual(live.delivery_cycle(self.folder, preview_ids=self.preview)["new"], 1)
        self.populate(self.rows)
        self.assertEqual(live.delivery_cycle(self.folder, preview_ids=self.preview)["new"], 2)

    def test_11_send_requires_url(self):
        self.populate()
        with self.assertRaises(ValueError):
            live.delivery_cycle(self.folder, send=True, allow_test_records=True)

    def test_12_send_rejects_test_records_without_opt_in(self):
        self.populate()
        with self.assertRaises(ValueError):
            live.delivery_cycle(self.folder, send=True, url="http://127.0.0.1:8765/api/mock/fire-alerts")

    def test_13_send_then_replay_skips(self):
        self.populate()
        with mock_server() as (server, url):
            first = live.delivery_cycle(self.folder, send=True, url=url, allow_test_records=True)
            again = live.delivery_cycle(self.folder, send=True, url=url, allow_test_records=True)
            self.assertEqual((first["new"], again["new"], again["already"]), (3, 0, 3))
            self.assertEqual(len(server.requests), 3)
            self.assertTrue(all(x[2]["X-Idempotency-Key"] == x[1]["transition_id"] for x in server.requests))

    def test_14_retry_transient_failure(self):
        self.populate([self.rows[0]])
        with mock_server([503, 201]) as (server, url):
            result = live.delivery_cycle(self.folder, send=True, url=url, allow_test_records=True)
            self.assertEqual(result["new"], 1)
            self.assertEqual(len(server.requests), 2)

    def test_15_failed_send_does_not_checkpoint(self):
        self.populate([self.rows[0]])
        with mock_server([400]) as (server, url):
            with self.assertRaises(RuntimeError):
                live.delivery_cycle(self.folder, send=True, url=url, allow_test_records=True)
            self.assertFalse((self.folder / "fire_alert_sent_state.json").exists())

    def test_16_external_plain_http_rejected(self):
        with self.assertRaises(ValueError):
            live.run_launcher(self.folder, ["--camera", "0"], send=True,
                              url="http://example.com/api/fire", allow_test_records=True)

    # 3. 새 폴더 정책과 안전한 실행 인자
    def test_17_old_results_not_overwritten(self):
        self.populate()
        with self.assertRaises(ValueError):
            live.validate_new_output_folder(self.folder)

    def test_18_empty_folder_allowed(self):
        live.validate_new_output_folder(self.folder)
        live.validate_new_output_folder(self.folder / "new")

    def test_19_no_source_arguments_rejected(self):
        with self.assertRaises(ValueError):
            live.build_detector_command(self.folder, [])

    def test_20_output_override_rejected(self):
        for bad in (["--camera", "0", "--output", "elsewhere"], ["--output=other"], ["--publish-alert-session"]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                live.build_detector_command(self.folder, bad)

    def test_21_command_uses_same_python_and_explicit_sidecar(self):
        cmd = live.build_detector_command(self.folder, ["--camera", "0", "--max-seconds", "10"])
        self.assertIn("--publish-alert-session", cmd)
        self.assertEqual(cmd[1:3], ["-m", "ai_vision.safety.live_fire_smoke"])
        self.assertEqual(cmd[-2:], [str(self.folder), "--publish-alert-session"])

    def test_22_default_mode_never_posts(self):
        with patch.object(live, "run_launcher", return_value=0) as mocked:
            exit_code = live.main(["--output", str(self.folder / "new"), "--", "--camera", "0"])
        self.assertEqual(exit_code, 0)
        self.assertFalse(mocked.call_args.kwargs["send"])

    def test_28_incremental_posts_before_detector_process_exits(self):
        """프로세스가 실행 중일 때 SUSPECTED가 먼저 송신되는지 확인합니다."""
        output = self.folder / "new"
        with mock_server() as (server, url):
            received_while_running = []
            test_self = self
            class FakeProcess:
                returncode = None
                def __init__(self, argv):
                    self.ticks = 0
                    output.mkdir(parents=True, exist_ok=True)
                    (output / "alert_session.json").write_text(json.dumps(SAMPLE_SUMMARY), encoding="utf-8")
                    (output / "incident_history.json").write_text(
                        json.dumps({"transitions": [test_self.rows[0]]}), encoding="utf-8")
                def poll(self):
                    self.ticks += 1
                    if self.ticks == 2:
                        received_while_running.append(len(server.requests))
                        (output / "incident_history.json").write_text(
                            json.dumps({"transitions": [test_self.rows[0], test_self.rows[2]]}), encoding="utf-8")
                    if self.ticks >= 3:
                        (output / "summary.json").write_text(
                            json.dumps(SAMPLE_SUMMARY), encoding="utf-8")
                        self.returncode = 0
                        return 0
                    return None
            result = live.run_launcher(output, ["--camera", "0"], send=True,
                                       url=url, allow_test_records=True,
                                       poll_seconds=0.05,
                                       process_factory=FakeProcess,
                                       sleep=lambda _: None)
            self.assertEqual(result, 0)
            self.assertEqual(received_while_running, [1])
            self.assertEqual(len(server.requests), 2)
            state = sender._read_json_object(output / "fire_alert_sent_state.json")
            self.assertEqual(len(state["acknowledged_transition_ids"]), 2)


class LiveDetectorSidecarTest(unittest.TestCase):
    # 4. 기존 감지기 변경 사항 확인
    def test_23_original_default_does_not_write_sidecar(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = LiveConfig(output_dir=Path(root), max_frames=1)
            run_live(cfg, model=FakeModel(), capture=FakeCapture(frames=3))
            self.assertFalse((Path(root) / "alert_session.json").exists())

    def test_24_sidecar_matches_final_summary_and_sender_ids(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            class InspectModel(FakeModel):
                def predict(self, **kwargs):
                    meta = json.loads((folder / "alert_session.json").read_text(encoding="utf-8"))
                    self_meta.append(meta)
                    self.assert_not_final = not (folder / "summary.json").exists()
                    return super().predict(**kwargs)
            self_meta = []
            model = InspectModel()
            cfg = LiveConfig(output_dir=folder, max_frames=5, max_seconds=0,
                             interval=0.1, window=2, min_hits=2,
                             publish_alert_session=True)
            run_live(cfg, model=model, capture=FakeCapture(frames=8), monotonic=lambda: len(model.calls)*0.2)
            self.assertTrue(self_meta)
            meta = self_meta[0]
            final = sender._read_json_object(folder / "summary.json")
            self.assertEqual(meta["started_at_utc"], final["started_at_utc"])
            self.assertEqual(meta["source"], final["source"])
            self.assertEqual([p["transition_id"] for p in live.load_live_payloads(folder)],
                             [p["transition_id"] for p in sender.build_payloads(folder)])

    def test_25_existing_folder_rejected_before_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            old = folder / "summary.json"
            old.write_text('{"important": true}', encoding="utf-8")
            with self.assertRaises(ValueError):
                run_live(LiveConfig(output_dir=folder, max_frames=1, publish_alert_session=True),
                         model=FakeModel(), capture=FakeCapture(frames=3))
            self.assertEqual(json.loads(old.read_text(encoding="utf-8")), {"important": True})

    def test_26_invalid_config_guard(self):
        with self.assertRaises(ValueError):
            LiveConfig(publish_alert_session="yes")

    def test_27_cli_parses_new_flag(self):
        with patch("ai_vision.safety.live_fire_smoke.run_live", return_value={
            "status": "TIME_LIMIT", "captured_frames": 0, "inference_samples": 0,
            "suspected_events": 0,
        }) as mocked:
            self.assertEqual(detection_main(["--publish-alert-session"]), 0)
            self.assertTrue(mocked.call_args.args[0].publish_alert_session)


if __name__ == "__main__":
    unittest.main()

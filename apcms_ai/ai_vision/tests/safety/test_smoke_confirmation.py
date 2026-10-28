"""약한 연기 관찰 보존과 새 사건 확정·재발생 조건을 검사합니다."""
import unittest
import tempfile
from pathlib import Path

from ai_vision.safety.fire_event_state import FireEventStateManager
from ai_vision.safety.live_fire_smoke import LiveConfig, run_live
from ai_vision.tests.safety.test_live_fire_smoke import FakeBox, FakeCapture, FakeModel


def detection(score, kind="SMOKE"):
    return {"class_name": kind, "confidence": score, "bbox": [1, 1, 30, 30]}


class SmokeConfirmationTests(unittest.TestCase):
    def test_live_runner_passes_option_without_removing_weak_detections(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / 'input.mp4'
            video.write_bytes(b'fake')
            config = LiveConfig(video_path=str(video), output_dir=Path(folder) / 'result',
                                interval=.1, max_seconds=0, smoke_conf=.3, smoke_confirm_conf=.55)
            result = run_live(config, model=FakeModel([FakeBox(0, .4)]), capture=FakeCapture())
            self.assertEqual(result['suspected_events'], 0)
            self.assertEqual(result['smoke_confirm_conf'], .55)
            self.assertGreater(result['inference_samples'], 0)

    def test_weak_observations_do_not_start_but_remain_tracked(self):
        state = FireEventStateManager(smoke_confirm_conf=.55)
        for index in range(12):
            self.assertEqual(state.update(index * .5, index, [detection(.4)]), [])
        self.assertEqual(len(state.regions), 1)
        self.assertEqual(state.regions[0].confidence, .4)

    def test_strong_start_then_weak_observations_keep_incident(self):
        state = FireEventStateManager(smoke_confirm_conf=.55, heartbeat_seconds=1)
        events = []
        for index, score in enumerate([.6, .6, .6, .35, .35, .35, .35]):
            events.extend(state.update(index * .5, index, [detection(score)]))
        self.assertEqual([event['status'] for event in events], ['SUSPECTED', 'ONGOING', 'ONGOING'])
        self.assertEqual(len({event['event_id'] for event in events}), 1)
        self.assertEqual(state.snapshot()['active'], 1)

    def test_reopen_needs_fresh_strong_evidence(self):
        state = FireEventStateManager(smoke_confirm_conf=.55)
        rows = [[detection(.7)]] * 3 + [[]] * 3 + [[detection(.4)]] * 5 + [[detection(.7)]] * 3
        events = []
        for index, row in enumerate(rows):
            current = state.update(index * .5, index, row)
            if 6 <= index < 13:
                self.assertFalse(current)
            events.extend(current)
        self.assertEqual([event['status'] for event in events], ['SUSPECTED', 'CLEARED', 'REOPENED'])
        self.assertEqual(len({event['event_id'] for event in events}), 1)

    def test_fire_is_unchanged(self):
        state = FireEventStateManager(smoke_confirm_conf=.9)
        events = []
        for index in range(3):
            events.extend(state.update(index, index, [detection(.31, 'FIRE')]))
        self.assertEqual(events[0]['status'], 'SUSPECTED')

    def test_default_preserves_weak_smoke_start(self):
        state = FireEventStateManager()
        for index in range(3):
            events = state.update(index, index, [detection(.31)])
        self.assertEqual(events[0]['status'], 'SUSPECTED')

    def test_invalid_configuration(self):
        for value in (True, float('nan'), float('inf'), -.1, 1.1, '0.55'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    FireEventStateManager(smoke_confirm_conf=value)
                with self.assertRaises(ValueError):
                    LiveConfig(smoke_confirm_conf=value)


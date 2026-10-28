"""저장 후보 재생의 필터 재평가와 시간 순서 검증."""
import json
import tempfile
import unittest
from pathlib import Path
from ai_vision.safety.replay_fire_candidates import replay
from ai_vision.tests.safety.test_smoke_confirmation import detection


class ReplayCandidateTests(unittest.TestCase):
    def test_replay_ignores_historical_accepted_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'candidates.jsonl'
            rows = [{'frame_index': i, 'source_seconds': i * .5,
                     'candidates': [{**detection(.4), 'accepted': False}]} for i in range(5)]
            path.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')
            self.assertEqual(replay(path)['counts']['SMOKE:SUSPECTED'], 1)
            self.assertEqual(replay(path, smoke_confirm_conf=.55)['counts'], {})

    def test_replay_rejects_backwards_time(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'invalid.jsonl'
            path.write_text('\n'.join(json.dumps({'frame_index': i, 'source_seconds': t,
                                                 'candidates': []}) for i, t in enumerate([1, 0])),
                            encoding='utf-8')
            with self.assertRaises(ValueError):
                replay(path)

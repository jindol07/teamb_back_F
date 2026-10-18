# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_review_tracking.py

import csv
import tempfile
import unittest
from pathlib import Path

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.review_tracking import event_fingerprint, validate_existing_review, review_window


class ReviewTrackingTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.events = [{"track_id": 1, "video_seconds": 1.2, "direction": "DOWN"}]

    def test_changed_events_do_not_overwrite_manual_review(self):
        write_json_atomic(self.root / "audit.json", {"event_fingerprint": event_fingerprint(self.events)})
        with self.assertRaisesRegex(ValueError, "통과 로그"):
            validate_existing_review(self.root, [dict(self.events[0], track_id=2)])

    def test_old_csv_identity_checked_and_notes_preserved(self):
        path = self.root / "event_review.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["event_index", "track_id", "video_seconds", "direction", "notes"])
            writer.writerow([1, 1, 1.2, "DOWN", "manual note"])
        before = path.read_bytes()
        validate_existing_review(self.root, self.events)
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(ValueError):
            validate_existing_review(self.root, [dict(self.events[0], video_seconds=2)])

    def test_source_window_keeps_absolute_start(self):
        summary = {"start_seconds": 30, "processed_frames": 360, "stride": 2, "source_fps": 60}
        self.assertEqual(review_window(summary, 60, 3600), (30, 12))
        with self.assertRaises(ValueError):
            review_window(summary, 30, 3600)
        with self.assertRaises(ValueError):
            review_window(dict(summary, start_seconds=60), 60, 3600)


if __name__ == "__main__":
    unittest.main()

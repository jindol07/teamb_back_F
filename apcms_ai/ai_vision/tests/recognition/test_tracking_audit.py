# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_tracking_audit.py

import json
import tempfile
import unittest
from pathlib import Path
from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.tracking_audit import audit_tracking


def save_tracking(root):
    # 실제 영상·모델 없이 프레임 연결만 검사하는 테스트 자료입니다.
    folder = root / "tracking"
    write_json_atomic(folder / "summary.json", {
        "http_enabled": False, "source": "D:/test/video.mp4", "source_fps": 10,
        "width": 100, "height": 100, "counts": {"DOWN": 1}, "observations_saved": True})
    event = {"track_id": 7, "frame_index": 10, "video_seconds": 1, "direction": "DOWN"}
    (folder / "crossings.jsonl").write_text(json.dumps(event), encoding="utf-8")
    rows = [{"track_id": 7, "frame_index": f, "video_seconds": f / 10, "box": [1, 2, 30, 40]} for f in (10, 12, 15)]
    (folder / "observations.jsonl").write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return folder, event, rows


class TrackingAuditTests(unittest.TestCase):
    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.catalog = ResultCatalog(self.root)
        self.folder, self.event, self.rows = save_tracking(self.root)

    def test_valid_tracking_links_crossing_to_observation(self):
        result = audit_tracking(self.catalog, self.folder)
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(len(result["observations"]), 3)
        self.assertTrue(result["observations_checked"])

    def test_invalid_event_time_ids_counts_and_duplicates_are_rejected(self):
        path = self.folder / "crossings.jsonl"
        for change in ({"track_id": True}, {"video_seconds": 1.5}, {"direction": "ENTRY"}):
            path.write_text(json.dumps({**self.event, **change}), encoding="utf-8")
            with self.subTest(change=change), self.assertRaises(ValueError):
                audit_tracking(self.catalog, self.folder)
        path.write_text(json.dumps(self.event) + "\n" + json.dumps(self.event), encoding="utf-8")
        with self.assertRaises(ValueError):
            audit_tracking(self.catalog, self.folder)
        path.write_text("", encoding="utf-8")
        with self.assertRaises(ValueError):
            audit_tracking(self.catalog, self.folder)

    def test_bad_boxes_missing_crossing_frames_and_reverse_frames_are_rejected(self):
        bad_rows = ([{**self.rows[0], "box": [-1, 2, 30, 40]}], self.rows[1:],
                    self.rows + [self.rows[0]], [{**self.rows[0], "video_seconds": float("nan")}])
        for rows in bad_rows:
            (self.folder / "observations.jsonl").write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                audit_tracking(self.catalog, self.folder)

    def test_legacy_missing_observations_are_only_optional_when_not_declared_saved(self):
        (self.folder / "observations.jsonl").unlink()
        with self.assertRaises(ValueError):
            audit_tracking(self.catalog, self.folder)
        summary = json.loads((self.folder / "summary.json").read_text(encoding="utf-8"))
        summary["observations_saved"] = False
        write_json_atomic(self.folder / "summary.json", summary)
        self.assertFalse(audit_tracking(self.catalog, self.folder)["observations_checked"])
        with self.assertRaises(ValueError):
            audit_tracking(self.catalog, self.folder, require_observations=True)

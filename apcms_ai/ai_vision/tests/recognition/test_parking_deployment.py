# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_parking_deployment.py

"""손상 파일·읽기 전용 볼륨에서 주차 도구의 실패 응답을 확인합니다."""

import io
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import HTTPException
from ai_vision.paths import RESULT_DIR
from ai_vision.parking.parking_api import get_parking_occupancy
from ai_vision.parking.space_editor import SpaceEditorHandler
from ai_vision.parking.parking_validation import validate_occupancy, validate_spaces


class ParkingDeploymentTests(unittest.TestCase):
    def test_invalid_counts_states_and_duplicate_ids_are_rejected(self):
        valid = {"total_spaces": 1, "occupied_count": 1, "empty_count": 0,
                 "spaces": [{"space_id": "A", "status": "OCCUPIED", "change_ratio": .5}]}
        self.assertIs(validate_occupancy(valid), valid)
        for change in ({"occupied_count": True}, {"empty_count": 1}, {"spaces": [None]},
                       {"spaces": [{"space_id": "A", "status": "UNKNOWN", "change_ratio": .5}]},
                       {"spaces": [{"space_id": "A", "status": "OCCUPIED", "change_ratio": float("nan")}]},
                       {"total_spaces": 2, "occupied_count": 2, "spaces": valid["spaces"] * 2}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_occupancy({**valid, **change})

    def test_invalid_coordinate_shapes_and_ids_are_rejected(self):
        valid = {"image_width": 10, "image_height": 10,
                 "spaces": [{"id": "A", "points": [[0, 0], [9, 0], [9, 9], [0, 9]]}]}
        self.assertIs(validate_spaces(valid), valid)
        variants = [{**valid, "image_width": True}, {**valid, "spaces": []},
                    {**valid, "spaces": valid["spaces"] * 2}, {**valid, "spaces": [None]}]
        for points in ([[0, 0]] * 4, [[0, 0], [1, 1], [2, 2], [3, 3]],
                       [[0, 0], [11, 0], [9, 9], [0, 9]], [[0, 0], [9.5, 0], [9, 9], [0, 9]]):
            row = copy.deepcopy(valid)
            row["spaces"][0]["points"] = points
            variants.append(row)
        for row in variants:
            with self.subTest(row=row), self.assertRaises(ValueError):
                validate_spaces(row)

    def test_structurally_invalid_json_result_is_service_unavailable(self):
        self.path.write_text('{"total_spaces":1,"occupied_count":0,"empty_count":0,"spaces":[]}', encoding="utf-8")
        with self.assertRaises(HTTPException) as caught:
            get_parking_occupancy()
        self.assertEqual(caught.exception.status_code, 503)

    def setUp(self):
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "result.json"
        patcher = patch("ai_vision.parking.parking_api.RESULT_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_valid_result_is_returned_without_changes(self):
        value = {"total_spaces": 0, "occupied_count": 0, "empty_count": 0, "spaces": []}
        self.path.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(get_parking_occupancy(), value)

    def test_missing_corrupt_and_nonfinite_results_are_service_unavailable(self):
        for content in (None, b"\xff", b'{"total": NaN}', b'{"total":1,"total":2}', b"[]", b"{"):
            if content is not None:
                self.path.write_bytes(content)
            with self.subTest(content=content), self.assertRaises(HTTPException) as caught:
                get_parking_occupancy()
            self.assertEqual(caught.exception.status_code, 503)

    def test_read_permission_failure_is_service_unavailable(self):
        with patch("ai_vision.parking.parking_api.read_json", side_effect=PermissionError("private-path")):
            with self.assertRaises(HTTPException) as caught:
                get_parking_occupancy()
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn("private-path", caught.exception.detail)

    def test_editor_write_permission_failure_returns_response(self):
        payload = json.dumps({"image_width": 10, "image_height": 10,
                              "spaces": [{"id": "A", "points": [[0, 0], [9, 0], [9, 9], [0, 9]]}]}).encode()
        handler = object.__new__(SpaceEditorHandler)
        handler.path, handler.headers = "/save", {"Content-Length": str(len(payload))}
        handler.rfile, handler.wfile = io.BytesIO(payload), io.BytesIO()
        handler.send_response, handler.send_header, handler.end_headers = Mock(), Mock(), Mock()
        with patch("ai_vision.parking.space_editor.write_json_atomic", side_effect=PermissionError):
            handler.do_POST()
        handler.send_response.assert_called_once_with(503)
        self.assertEqual(json.loads(handler.wfile.getvalue()), {"success": False})

# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_results_api.py

import json
import sys
import tempfile
import unittest
import types
import importlib.util
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_vision.paths import RESULT_DIR, BASE_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.results_api import create_router
from ai_vision.recognition.plate_consensus import summarize_plate_samples


class ResultsAPITests(unittest.TestCase):
    def test_existing_vision_router_includes_results_routes(self):
        # 기존 인식기를 대체해 실제 모델 없이 통합 라우터 등록만 검증
        fake = types.ModuleType("ai_vision.recognition.recognizer")
        fake.recognize_image = lambda image: {}
        with patch.dict(sys.modules, {"ai_vision.recognition.recognizer": fake}):
            spec = importlib.util.spec_from_file_location("ai_vision._results_wiring_test", BASE_DIR / "main.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        # 설치된 FastAPI의 지연 include_router도 해석된 공개 스키마에서 확인
        application = FastAPI()
        application.include_router(module.router)
        paths = set(application.openapi()["paths"])
        self.assertTrue({"/recognize", "/parking/occupancy", "/vision/runs", "/vision/runs/{run_id}/passages"} <= paths)

    def setUp(self):
        # TestClient는 실제 HTTP 서버나 네트워크 소켓을 열지 않습니다.
        base = RESULT_DIR / "test_tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        app = FastAPI()
        app.include_router(create_router(ResultCatalog(self.root)))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        write_json_atomic(self.root / "tracking/summary.json", {
            "http_enabled": False, "counts": {"DOWN": 1, "UP": 0}})

    def test_list_and_detail_without_model_loading_or_writes(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        loaded = "ai_vision.recognition.recognizer" in sys.modules
        self.assertEqual(self.client.get("/vision/runs").status_code, 200)
        detail = self.client.get("/vision/runs/tracking")
        self.assertEqual(detail.json()["total_crossings"], 1)
        self.assertEqual("ai_vision.recognition.recognizer" in sys.modules, loaded)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_missing_corrupt_and_invalid_parameters(self):
        self.assertEqual(self.client.get("/vision/runs/missing").status_code, 404)
        self.assertEqual(self.client.get("/vision/runs?limit=101").status_code, 422)
        self.assertEqual(self.client.get("/vision/runs?offset=-1").status_code, 422)
        self.assertEqual(self.client.get("/vision/runs/bad.name").status_code, 422)
        (self.root / "tracking/summary.json").write_text("{", encoding="utf-8")
        response = self.client.get("/vision/runs/tracking")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(str(self.root), response.text)

    def test_writing_methods_are_not_available(self):
        self.assertEqual(self.client.post("/vision/runs").status_code, 405)
        self.assertEqual(self.client.delete("/vision/runs/tracking").status_code, 405)

    def test_audit_returns_diagnostic_failure_without_private_paths(self):
        # 요약만 있고 필수 로그가 없는 결과는 200 응답 안의 FAILED로 구분합니다.
        before = (self.root / "tracking/summary.json").read_bytes()
        response = self.client.get("/vision/runs/tracking/audit")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "FAILED")
        self.assertNotIn(str(self.root), response.text)
        self.assertEqual(before, (self.root / "tracking/summary.json").read_bytes())
        self.assertEqual(self.client.get("/vision/runs/missing/audit").status_code, 404)
        self.assertEqual(self.client.get("/vision/runs/bad.name/audit").status_code, 422)
        self.assertEqual(self.client.post("/vision/runs/tracking/audit").status_code, 405)

    def test_passage_pagination_and_recomputed_consensus(self):
        folder = self.root / "ocr"
        write_json_atomic(folder / "summary.json", {
            "http_enabled": False, "crossings_in_run": 1, "processed_tracks": 1, "confirmed_plates": 1})
        samples = [{"frame_index": 1, "video_seconds": 1, "plate_number": "91소6408", "plate_type": "KOREAN_VALID"},
                   {"frame_index": 20, "video_seconds": 1.3, "plate_number": "91소6408", "plate_type": "KOREAN_VALID"}]
        row = {"http_enabled": False, "record_type": "LOCAL_TRACKED_PASSAGE", "track_id": 1,
               "screen_direction": "DOWN", "crossing_video_seconds": 1.2,
               "samples": samples, "plate_consensus": summarize_plate_samples(samples)}
        path = folder / "passages.jsonl"
        path.write_text(json.dumps(row), encoding="utf-8")
        response = self.client.get("/vision/runs/ocr/passages?limit=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["plate_number"], "91소6408")
        self.assertEqual(self.client.get("/vision/runs/ocr/passages?offset=1").json()["items"], [])
        # 필터 적용 후의 총 건수로 페이지를 계산합니다.
        self.assertEqual(self.client.get("/vision/runs/ocr/passages?direction=UP").json()["total"], 0)
        filtered = self.client.get("/vision/runs/ocr/passages?direction=DOWN&plate_status=CONFIRMED&start_seconds=1.2&end_seconds=1.2")
        self.assertEqual(filtered.json()["total"], 1)
        for suffix in ("direction=ENTRY", "plate_status=BAD", "start_seconds=2&end_seconds=1", "start_seconds=nan"):
            self.assertEqual(self.client.get("/vision/runs/ocr/passages?" + suffix).status_code, 422)
        row["plate_consensus"]["plate_number"] = "12가3456"
        path.write_text(json.dumps(row), encoding="utf-8")
        self.assertEqual(self.client.get("/vision/runs/ocr/passages").status_code, 503)
        # 필터 밖의 손상된 행도 검사해 검색 조건으로 오류가 숨겨지지 않는지 확인합니다.
        row["samples"] = [None]
        path.write_text(json.dumps(row), encoding="utf-8")
        self.assertEqual(self.client.get("/vision/runs/ocr/passages?direction=UP").status_code, 503)


if __name__ == "__main__":
    unittest.main()

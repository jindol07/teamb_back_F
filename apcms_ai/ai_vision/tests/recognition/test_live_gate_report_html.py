# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_live_gate_report_html.py

import unittest

from ai_vision.recognition.live_gate_report import validate_report
from ai_vision.recognition.live_gate_report_html import render_html
from ai_vision.recognition.run_live_gate import _demo
from ai_vision.recognition.live_gate_context import build_run_context


class LiveGateReportHtmlTests(unittest.TestCase):
    def test_camera_text_escaped_and_no_scripts_or_external_assets(self):
        source = _demo()
        source["camera_id"] = '<script>alert("x")</script>'
        html = render_html(validate_report(source))
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("src=", html)
        self.assertIn("default-src 'none'", html)
        self.assertIn("합성 예시", html)
        self.assertIn("91소6408", html)

    def test_empty_results_and_failed_status_remain_visible(self):
        source = _demo()
        source.update(results=[], processed_passages=0, decision_counts={}, status="FAILED",
                      stop_reason="CAPTURE_OR_PROCESSING_FAILED")
        html = render_html(validate_report(source))
        self.assertIn("통과 자료가 없습니다", html)
        self.assertIn("FAILED", html)

    def test_timings_and_missing_old_measurements_are_distinct(self):
        source = _demo()
        html = render_html(validate_report(source))
        self.assertIn("최대 수집 간격", html)
        self.assertIn("추적·OCR·후보 처리", html)
        self.assertIn("센서 지연이나 순수 모델 FPS가 아닙니다", html)
        del source["performance"]
        html = render_html(validate_report(source))
        self.assertIn("처리 시간 측정값이 없습니다", html)

    def test_real_camera_config_snapshot_visible(self):
        source = _demo()
        source["uses_synthetic_source"] = False
        config = {"tracker": "bytetrack", "line_y": .5, "line_x": [.1, .9], "roi": [0, 0, 1, 0, 1, 1, 0, 1]}
        source["run_context"] = build_run_context(config, 2)
        html = render_html(validate_report(source))
        self.assertIn("카메라 번호: 2", html)
        self.assertIn("line_y: 0.5", html)
        self.assertIn(source["run_context"]["tracking_config_sha256"], html)

    def test_old_missing_context_and_synthetic_are_distinct(self):
        source = _demo()
        self.assertIn("카메라 번호·ROI·기준선을 사용하지 않았습니다", render_html(validate_report(source)))
        del source["run_context"]
        self.assertIn("실행 설정 사본이 없습니다", render_html(validate_report(source)))

    def test_reset_counts_visible_only_when_recorded(self):
        source = _demo()
        source["processor_statistics"] = {"frames": 3, "observations": 3, "already_counted": 0,
            "outside_roi": 0, "eligible": 3, "gap_resets": 0, "crossings": 1, "ocr_calls": 2, "peak_buffer_bytes": 100}
        self.assertNotIn("ROI 이탈로 위치·crop 초기화", render_html(validate_report(source)))
        source["processor_statistics"].update(roi_resets=1, speed_resets=2)
        html = render_html(validate_report(source))
        self.assertIn("ROI 이탈로 위치·crop 초기화: 1", html)
        self.assertIn("위치 점프로 위치·crop 초기화: 2", html)

    def test_expired_history_crop_count_visible_only_if_available(self):
        source = _demo()
        source["processor_statistics"] = {"frames": 3, "observations": 3, "already_counted": 0,
            "outside_roi": 0, "eligible": 3, "gap_resets": 0, "crossings": 1, "ocr_calls": 2, "peak_buffer_bytes": 100}
        self.assertNotIn("시각 기록 만료로 제외한 crop", render_html(validate_report(source)))
        source["processor_statistics"]["expired_history_crops"] = 2
        self.assertIn("시각 기록 만료로 제외한 crop: 2", render_html(validate_report(source)))

    def test_camera_failure_reason_and_end_policy_visible(self):
        source = _demo()
        source.update(status="FAILED", stop_reason="CAMERA_READ_FAILED", error_type="ValueError", source_end_expected=False)
        html = render_html(validate_report(source))
        self.assertIn("CAMERA_READ_FAILED", html)
        self.assertIn("카메라 읽기 종료는 실패로 처리", html)

    def test_deadline_diagnostics_present_only_when_recorded(self):
        source = _demo()
        self.assertIn("읽기 전 시간 확인:", render_html(validate_report(source)))
        del source["deadline"]
        self.assertNotIn("읽기 전 시간 확인:", render_html(validate_report(source)))

    def test_consensus_vote_conditions_visible(self):
        html = render_html(validate_report(_demo()))
        self.assertIn("채택 표 수", html)
        self.assertIn("필요 표 수", html)
        self.assertIn("최소 표본 간격(초)", html)
        self.assertIn("<td>0.25</td>", html)

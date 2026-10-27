# D:/finalProjectB/back/apcms_ai/ai_vision/tests/run_checks.py

"""DB·실제 모델·카메라 없이 실행하는 Vision 회귀 테스트 묶음."""

import argparse
import unittest


# 1. 구형 모델 실험 스크립트를 수집하지 않도록 검사 대상을 명시합니다.
NAMES = """local_io plate_consensus tracking_config line_crossing tracked_passages video_pipeline
review_tracking results_catalog results_api evaluate_crossings passage_query result_validation export_passages
review_labels review_metrics review_workflow review_passages vehicle_contract preview_vehicle_events vehicle_response
simulate_vehicle_exchange vehicle_event_guard simulate_event_guard guarded_vehicle_flow run_guarded_vehicle_flow
vehicle_http vehicle_delivery_flow vehicle_live_candidate run_vehicle_delivery_check review_assets review_html
review_bundle tracking_audit passage_audit run_audit audit_results live_gate_clock live_gate_session
live_gate_processor run_live_gate preview_gate_config live_gate_report live_gate_report_html live_gate_report_csv
export_live_gate_report live_gate_environment live_gate_camera_probe live_gate_preflight check_live_gate
live_gate_lifecycle live_gate_storage inspect_live_gate live_gate_metrics asyncio_runtime_check live_gate_context
live_gate_deadline read_camera_frame recognition_models recognizer_lazy_loading recognize_api_threading image_upload
recognize_upload_api recognition_admission ocr_image_policy run_checks runtime_environment check_runtime_environment
probe_runtime_imports deployment_runtime parking_deployment deployment_config deployment_readiness ocr_configuration
aws_recognition_cases http_diagnostics upload_limits check_deployed_api check_deployed_api_cli check_deployed_cases
remote_plate_reader camera_recognition latest_frame_capture async_gate_processor parking_delivery_worker
vehicle_space_tracker parking_runtime parking_process_scope parking_server_trial frame_exchange""".split()
MODULES = tuple("ai_vision.tests.recognition.test_" + name for name in NAMES)


def build_suite(loader=None):
    loader = unittest.defaultTestLoader if loader is None else loader
    return loader.loadTestsFromNames(MODULES)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="테스트를 불러오지 않고 모듈 목록만 출력")
    parser.add_argument("--failfast", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(MODULES))
        return 0
    # 2. 누락된 의존성·실패·환경 오류도 성공이나 생략으로 바꾸지 않습니다.
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1, failfast=args.failfast).run(build_suite())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

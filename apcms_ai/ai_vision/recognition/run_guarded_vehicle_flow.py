# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/run_guarded_vehicle_flow.py

"""입출차 후보의 모의 처리 흐름을 실행하고 새 JSON 보고서를 저장합니다."""

import argparse
import json
from pathlib import Path

from ai_vision.recognition.guarded_vehicle_flow import build_flow_report
from ai_vision.recognition.local_io import read_json
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.review_workflow import write_new_file
from ai_vision.recognition.simulate_vehicle_exchange import SCENARIOS


def demo_preview():
    # 한국 번호판은 합성 예시입니다. 실제 영상 결과의 대체 정답이 아닙니다.
    event = {"event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479", "event_type": "VEHICLE_PASSAGE",
             "detected_at": "2020-01-01T00:00:00Z", "camera_id": "SIMULATION_ONLY", "direction": "ENTRY",
             "plate_number": "91소6408", "confidence": .8}
    return {"record_type": "LOCAL_VEHICLE_EVENT_PREVIEW", "run_id": "guarded_demo", "http_enabled": False,
            "sendable": False, "total": 1, "candidate_count": 1,
            "items": [{"track_id": 1, "status": "CANDIDATE_ONLY", "reasons": [], "payload": event}]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--preview", type=Path)
    source.add_argument("--demo", action="store_true")
    parser.add_argument("--scenario", choices=SCENARIOS, default="processed")
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = demo_preview() if args.demo else read_json(args.preview)
        report = build_flow_report(source, args.scenario, args.passes)
        report["uses_synthetic_event"] = args.demo
        write_new_file(ResultCatalog(), args.output, json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"), ".json")
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "모의 흐름 실행 실패: 초안·설정·새 출력 파일을 확인해 주세요.\n")
    print(f"모의 흐름 저장: 후보 {report['candidate_inputs_per_pass']}건 × {report['passes']}회 / 모의 응답 호출 {report['mock_call_count']}회 (실제 통신 없음)")


if __name__ == "__main__":
    main()

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/run_vehicle_delivery_check.py

"""HTTP 클라이언트까지 포함한 입출차 흐름 검사. 실제 네트워크 모드는 없습니다."""

import argparse
import json as jsonlib
from pathlib import Path

import requests

from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.review_workflow import write_new_file
from ai_vision.recognition.simulate_vehicle_exchange import SCENARIOS
from ai_vision.recognition.vehicle_delivery_flow import VehicleDeliveryFlow
from ai_vision.recognition.vehicle_http import VehicleHTTPClient
from ai_vision.recognition.vehicle_live_candidate import create_live_candidate


class _MockResponse:
    def __init__(self, status, body):
        self.status_code, self.body = status, body

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset:offset + chunk_size]

    def close(self):
        pass


class _MockSession:
    def __init__(self, scenario, calls):
        self.scenario, self.calls = scenario, calls

    def mount(self, prefix, adapter):
        pass

    def post(self, url, **kwargs):
        self.calls.append(1)
        if self.scenario == "timeout":
            raise requests.Timeout("MOCK_ONLY")
        if self.scenario == "connection_error":
            raise requests.ConnectionError("MOCK_ONLY")
        codes = {"bad_request": 400, "unauthorized": 401, "forbidden": 403, "conflict": 409,
                 "rate_limited": 429, "server_error": 500}
        if self.scenario in codes:
            return _MockResponse(codes[self.scenario], b"")
        event = kwargs["json"]
        body = {"eventId": event["event_id"], "eventType": "VEHICLE_PASSAGE", "plateNumber": event["plate_number"],
                "spaceCode": None, "parkingUsageId": 1,
                "outcome": {"processed": "PROCESSED", "unchanged": "UNCHANGED", "pending": "PENDING"}.get(self.scenario, "PROCESSED")}
        if self.scenario == "wrong_event":
            body["eventId"] = "00000000-0000-0000-0000-000000000000"
        if self.scenario == "unknown_outcome":
            body["outcome"] = "UNKNOWN"
        raw = b"{bad" if self.scenario == "invalid_json" else jsonlib.dumps(body).encode("utf-8")
        return _MockResponse(200, raw)

    def close(self):
        pass


def build_check_report(mode="disabled", scenario="processed", passes=3):
    if mode not in {"disabled", "mock-http"} or scenario not in SCENARIOS or type(passes) is not int or not 1 <= passes <= 10:
        raise ValueError("검사 모드·시나리오·반복 횟수를 확인해 주세요.")
    # 1. 실시간 형태의 합성 자료입니다. 실제 카메라에서 받은 결과가 아닙니다.
    samples = [{"frame_index": frame, "video_seconds": seconds, "plate_number": "91소6408",
                "plate_type": "KOREAN_VALID", "plate_detection_confidence": .8}
               for frame, seconds in ((10, 1), (13, 1.3))]
    passage = {"record_type": "LIVE_TRACKED_PASSAGE", "http_enabled": False, "track_id": 1, "screen_direction": "DOWN",
               "crossing_video_seconds": 1, "samples": samples, "plate_consensus": summarize_plate_samples(samples)}
    candidate = create_live_candidate(passage, "SIMULATION_ONLY", "ENTRY", "2020-01-01T00:00:01Z",
                                      "f47ac10b-58cc-4372-a567-0e02b2c3d479")
    calls = []
    client = VehicleHTTPClient() if mode == "disabled" else VehicleHTTPClient(
        "http://mock.invalid/alpharking/admin", "MOCK_ONLY", enabled=True,
        session_factory=lambda: _MockSession(scenario, calls))
    flow = VehicleDeliveryFlow(client)
    steps = [flow.process("delivery_demo", candidate) for _ in range(passes)]
    return {"record_type": "LOCAL_VEHICLE_DELIVERY_CHECK", "mode": mode, "scenario": scenario, "passes": passes,
            "uses_synthetic_event": True, "http_enabled": False, "real_http_used": False,
            "mock_post_calls": len(calls), "steps": steps,
            "note": "합성 자료와 모의 세션을 사용했습니다. 실제 Boot·DB·카메라 연결 결과가 아닙니다."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["disabled", "mock-http"], default="disabled")
    parser.add_argument("--scenario", choices=SCENARIOS, default="processed")
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_check_report(args.mode, args.scenario, args.passes)
        write_new_file(ResultCatalog(), args.output, jsonlib.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"), ".json")
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "전송 흐름 검사 실패: 검사 설정과 새 출력 파일을 확인해 주세요.\n")
    print(f"전송 흐름 검사 저장: {args.passes}회 입력 / 모의 POST {report['mock_post_calls']}회 / 실제 HTTP 0회")


if __name__ == "__main__":
    main()

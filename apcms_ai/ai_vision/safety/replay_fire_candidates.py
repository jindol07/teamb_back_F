"""저장 후보를 실제 사건 관리기로 재평가하는 오프라인 도구."""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.safety.fire_event_state import FireEventStateManager


def replay(path, fire_conf=.3, smoke_conf=.3, smoke_confirm_conf=None):
    # 1. 모델 재추론·카메라·통신 없이 후보 로그의 연속 관찰 조건을 비교합니다.
    for value in (fire_conf, smoke_conf):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("탐지 기준은 0~1이어야 합니다.")
    state = FireEventStateManager(smoke_confirm_conf=smoke_confirm_conf)
    transitions, samples = [], 0
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            detections = []
            for candidate in row["candidates"]:
                kind, score, _ = state._validate_detection(candidate)
                if score >= (fire_conf if kind == "FIRE" else smoke_conf):
                    detections.append(candidate)
            transitions.extend(state.update(row["source_seconds"], row["frame_index"], detections))
            samples += 1
    return {"source": str(Path(path).resolve()), "samples": samples,
            "fire_conf": fire_conf, "smoke_conf": smoke_conf,
            "smoke_confirm_conf": smoke_confirm_conf,
            "counts": dict(Counter(f"{item['type']}:{item['status']}" for item in transitions)),
            "transitions": transitions}


def main(argv=None):
    parser = argparse.ArgumentParser(description="저장 후보의 사건 판정 재생. 카메라·HTTP 없음")
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--fire-conf", type=float, default=.3)
    parser.add_argument("--smoke-conf", type=float, default=.3)
    parser.add_argument("--smoke-confirm-conf", type=float)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    reports = []
    for path in args.logs:
        reports.append({"baseline": replay(path, args.fire_conf, args.smoke_conf),
                        "candidate": replay(path, args.fire_conf, args.smoke_conf,
                                            args.smoke_confirm_conf)})
    write_json_atomic(args.output, {"mode": "OFFLINE_CANDIDATE_REPLAY", "reports": reports})
    for report in reports:
        print(report["candidate"]["source"], report["baseline"]["counts"],
              "->", report["candidate"]["counts"])


if __name__ == "__main__":
    main()

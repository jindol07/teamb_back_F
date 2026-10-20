# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/check_live_gate.py

"""모델·HTTP 실행 없이 실시간 세션의 준비 상태를 점검합니다."""

import argparse
import json
from pathlib import Path

from ai_vision.recognition.live_gate_preflight import run_preflight


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--down-direction", choices=["ENTRY", "EXIT"], required=True)
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--probe-camera", action="store_true", help="카메라 한 프레임 읽기와 해제를 추가로 확인")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        # 1. 기존 출력 파일을 지정했다면 카메라를 열기 전에 중단합니다.
        if args.output is not None and args.output.exists():
            raise FileExistsError("출력 파일이 이미 있습니다.")
        if args.output is not None and not args.output.parent.is_dir():
            raise ValueError("출력 부모 폴더를 먼저 만들어 주세요.")
        report = run_preflight(args.config, args.camera_id, args.down_direction,
                               args.camera_index, args.probe_camera)
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    except (OSError, ValueError, TypeError):
        parser.exit(1, "사전 점검 실패: 설정·카메라 ID·새 출력 경로를 확인해 주세요.\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "BLOCKED":
        parser.exit(1)


if __name__ == "__main__":
    main()

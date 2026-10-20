# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/check_runtime_environment.py

"""현재 버전 정보를 출력·저장하거나 다른 PC의 기록과 비교합니다."""

import argparse
import json
from pathlib import Path

from ai_vision.recognition.local_io import read_json
from ai_vision.recognition.runtime_environment import collect_snapshot, compare_snapshots


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--output", type=Path)
    action.add_argument("--compare", type=Path)
    args = parser.parse_args(argv)
    try:
        current = collect_snapshot()
        result = compare_snapshots(read_json(args.compare), current) if args.compare else current
        if args.output:
            # 1. 기존 버전 기록을 덮어쓰지 않습니다. 부모 폴더는 미리 준비합니다.
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    except (OSError, ValueError, TypeError):
        parser.exit(2, "환경 기록·새 출력 경로를 확인해 주세요.\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if args.compare and not result["matches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

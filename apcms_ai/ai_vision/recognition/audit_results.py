# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/audit_results.py

"""저장된 Vision 실행의 일관성을 진단하는 로컬 CLI."""

import argparse
import json
from pathlib import Path
from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.run_audit import audit_run
from ai_vision.recognition.review_workflow import write_new_file


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        catalog = ResultCatalog()
        result = audit_run(catalog, args.run_id)
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        # --output을 생략하면 콘솔만 출력하며 어떤 파일도 생성하지 않습니다.
        if args.output is not None:
            write_new_file(catalog, args.output, text.encode("utf-8"), ".json")
        print(text)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(2, "진단 대상을 읽거나 새 보고서를 저장할 수 없습니다.\n")
    return {"PASS": 0, "WARNING": 0, "FAILED": 1, "INCOMPLETE": 1}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())

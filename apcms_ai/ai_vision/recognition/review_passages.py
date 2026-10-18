# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/review_passages.py

"""저장된 OCR 결과의 수동 검토 양식 생성과 정답 비교 CLI."""

import argparse
from pathlib import Path

from ai_vision.recognition.results_catalog import ResultCatalog
from ai_vision.recognition.review_workflow import create_template, create_report
from ai_vision.recognition.review_bundle import create_bundle


def main(argv=None):
    # 1. 두 명령 모두 기존 결과만 읽으며 모델이나 송신기를 실행하지 않습니다.
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("template", "report", "bundle"):
        sub = commands.add_parser(command)
        sub.add_argument("--run-id", required=True)
        sub.add_argument("--output", type=Path, required=True)
        if command == "report":
            sub.add_argument("--labels", type=Path, required=True)
        if command == "bundle":
            sub.add_argument("--offset", type=int, default=0)
            sub.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        catalog = ResultCatalog()
        if args.command == "template":
            count = create_template(catalog, args.run_id, args.output)
            print(f"검토 양식 저장: {count}건 / 모든 행은 PENDING입니다.")
        elif args.command == "report":
            report = create_report(catalog, args.run_id, args.labels, args.output)
            print(f"검토 보고서 저장: 정답 입력 {report['verified_plate_rows']}건 / 미검토 {report['review_status_counts']['PENDING']}건")
        else:
            result = create_bundle(catalog, args.run_id, args.output, args.offset, args.limit)
            print(f"검토 HTML 저장: 전체 {result['total']}대 중 {result['shown']}대 / 이미지 {result['image_count']}장")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"번호판 검토 실패: {error}\n")


if __name__ == "__main__":
    main()

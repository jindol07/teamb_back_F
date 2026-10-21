# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/export_live_gate_report.py

"""종료된 실시간 세션 summary.json을 HTML·CSV 보고서로 내보냅니다."""

import argparse
from pathlib import Path

from ai_vision.recognition.live_gate_report import load_report
from ai_vision.recognition.live_gate_report_html import render_html
from ai_vision.recognition.live_gate_report_csv import render_csv
from ai_vision.recognition.local_io import write_json_atomic


def export_report(summary, output, include_review_reasons=False):
    # 1. 입력 검사와 렌더링을 마친 뒤 새 출력 폴더를 만듭니다.
    report = load_report(summary)
    html, csv = render_html(report), render_csv(report, include_review_reasons)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    # 2. 기존 폴더를 덮어쓰지 않으며 저장 실패 시 불완전 폴더는 사용자가 확인합니다.
    (output / "report.html").write_text(html, encoding="utf-8")
    (output / "passages.csv").write_text(csv, encoding="utf-8-sig", newline="")
    write_json_atomic(output / "review_summary.json", report["review_summary"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--include-review-reasons", action="store_true", help="CSV 뒤에 검토 사유 상태·코드 열 추가")
    args = parser.parse_args(argv)
    try:
        report = export_report(args.summary, args.output_dir, args.include_review_reasons)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        parser.exit(1, "보고서 생성 실패: 종료된 전체 summary.json과 새 출력 폴더를 확인해 주세요.\n")
    print(f"보고서 저장: 통과 {report['processed_passages']}건 / 상태 {report['status']} / {args.output_dir}")


if __name__ == "__main__":
    main()

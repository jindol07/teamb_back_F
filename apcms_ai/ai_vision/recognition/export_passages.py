# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/export_passages.py

"""검증된 차량 통과 결과를 Excel에서 읽을 수 있는 CSV로 내보냅니다."""

import argparse
import csv
import io
from pathlib import Path

from ai_vision.recognition.passage_query import PassageQuery
from ai_vision.recognition.results_catalog import ResultCatalog

COLUMNS = ("run_id", "track_id", "screen_direction", "video_seconds", "plate_status", "plate_number", "sample_count")


def export_csv(catalog, run_id, output, query=None):
    # 1. 조회·검증이 모두 끝나기 전에는 출력 파일을 만들지 않습니다.
    query = query if query is not None else PassageQuery()
    items = catalog.all_passages(run_id, query)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
    writer.writeheader()
    for item in items:
        writer.writerow({"run_id": run_id, **item})
    output = Path(output)
    # 2. 원본 결과 폴더를 출력 위치로 사용하지 않고 기존 파일도 덮어쓰지 않습니다.
    if output.suffix.lower() != ".csv" or output.resolve().is_relative_to(catalog.root):
        raise ValueError("원본 결과 폴더 밖의 새 .csv 파일을 지정해 주세요.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        # UTF-8 BOM으로 Excel에서 한글 번호판이 깨지는 현상을 줄입니다.
        handle.write(buffer.getvalue().encode("utf-8-sig"))
    return len(items)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--direction", choices=["UP", "DOWN"])
    parser.add_argument("--plate-status")
    parser.add_argument("--start-seconds", type=float)
    parser.add_argument("--end-seconds", type=float)
    args = parser.parse_args()
    try:
        query = PassageQuery(args.direction, args.plate_status, args.start_seconds, args.end_seconds)
        count = export_csv(ResultCatalog(), args.run_id, args.output, query)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"CSV 내보내기 실패: {error}\n")
    print(f"CSV 저장 완료: {count}건 / {args.output}")


if __name__ == "__main__":
    main()

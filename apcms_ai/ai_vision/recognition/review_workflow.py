# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/review_workflow.py

"""원본 결과를 보존하면서 검토 양식과 검토 보고서를 생성합니다."""

import csv
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path

from ai_vision.recognition.review_labels import COLUMNS, template_rows
from ai_vision.recognition.review_metrics import build_report


def write_new_file(catalog, output, data, suffix):
    output = Path(output)
    if output.suffix.lower() != suffix or output.resolve().is_relative_to(catalog.root):
        raise ValueError("원본 결과 폴더 밖의 새 검토 파일을 지정해 주세요.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # 1. 완성된 임시 파일을 같은 디스크에서 연결합니다.
        # os.link는 기존 출력이 있으면 실패하므로 덮어쓰기와 반쪽 파일 공개를 피합니다.
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".review-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def create_template(catalog, run_id, output):
    snapshot = catalog.review_snapshot(run_id)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
    writer.writeheader()
    rows = template_rows(snapshot)
    writer.writerows(rows)
    write_new_file(catalog, output, buffer.getvalue().encode("utf-8-sig"), ".csv")
    return len(rows)


def create_report(catalog, run_id, labels, output):
    # 2. 사람이 작성한 CSV도 크기·열 이름·중복 차량을 검사한 뒤 집계합니다.
    with Path(labels).open("rb") as handle:
        raw = handle.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("검토 CSV는 8MB 이하여야 합니다.")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        if reader.fieldnames != list(COLUMNS):
            raise ValueError("검토 CSV 열 이름과 순서를 유지해 주세요.")
        rows = list(reader)
    except (UnicodeError, csv.Error) as error:
        raise ValueError("검토 CSV는 올바른 UTF-8 형식이어야 합니다.") from error
    snapshot = catalog.review_snapshot(run_id)
    report = build_report(snapshot, rows)
    report["labels_sha256"] = hashlib.sha256(raw).hexdigest()
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    write_new_file(catalog, output, encoded, ".json")
    return report

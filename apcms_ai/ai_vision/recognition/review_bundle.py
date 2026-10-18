# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/review_bundle.py

"""검증된 OCR 표본과 번호판 이미지를 단일 오프라인 HTML로 묶습니다."""

from ai_vision.recognition.review_assets import load_evidence
from ai_vision.recognition.review_html import render_review
from ai_vision.recognition.review_workflow import write_new_file


def create_bundle(catalog, run_id, output, offset=0, limit=20):
    catalog.pagination(offset, limit)
    snapshot = catalog.review_snapshot(run_id)
    items = snapshot["items"][offset:offset + limit]
    evidence = load_evidence(catalog, run_id, snapshot, [row["track_id"] for row in items])
    # 1. 이미지 로딩 중 판정이 바뀐 경우 서로 다른 시점의 자료를 섞지 않습니다.
    if catalog.review_snapshot(run_id) != snapshot:
        raise ValueError("검토 자료 생성 중 결과가 바뀌었습니다. 완료된 결과로 다시 실행해 주세요.")
    html = render_review(snapshot, evidence, items, offset).encode("utf-8")
    if len(html) > 40 * 1024 * 1024:
        raise ValueError("HTML이 40MB를 초과했습니다. limit을 줄여 주세요.")
    # 2. 기존 검토 자료와 원본 OCR 결과는 덮어쓰지 않습니다.
    write_new_file(catalog, output, html, ".html")
    return {"run_id": run_id, "snapshot_sha256": snapshot["snapshot_sha256"], "total": len(snapshot["items"]),
            "offset": offset, "shown": len(items),
            "image_count": sum(sample["image"] is not None for samples in evidence.values() for sample in samples)}

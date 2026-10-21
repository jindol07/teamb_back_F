# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/review_html.py

"""번호판 표본을 외부 접속 없이 확인할 수 있는 정적 HTML 보고서."""

from html import escape


def _text(value):
    return escape(str(value), quote=True)


def render_review(snapshot, evidence, items, offset=0):
    # 1. OCR 문자열도 외부 입력으로 취급해 HTML 태그로 해석되지 않게 합니다.
    cards = []
    image_count = 0
    for item in items:
        track = item["track_id"]
        samples = []
        for sample in evidence[track]:
            picture = sample["image"]
            if picture is None:
                image = '<p class="missing">저장된 번호판 이미지 없음</p>'
            else:
                image_count += 1
                image = (f'<img alt="차량 {_text(track)} 번호판 표본" src="data:image/jpeg;base64,{_text(picture["base64"])}">'
                         f'<small>이미지 SHA-256: {_text(picture["sha256"])}</small>')
            samples.append(f'<figure>{image}<figcaption>프레임 {_text(sample["frame_index"])} · '
                           f'{_text(sample["video_seconds"])}초<br>표본 OCR: {_text(sample["ocr_text"])}'
                           f'<br>형식 검토 사유: {_text(", ".join(sample.get("review_reasons", [])) or "없음")}</figcaption></figure>')
        if not samples:
            samples.append('<p class="missing">이 차량에는 저장된 OCR 표본이 없습니다.</p>')
        cards.append(f'<section id="track-{_text(track)}"><h2>차량 ID {_text(track)}</h2>'
                     f'<p>화면 방향: {_text(item["screen_direction"])} · 통과 시각: {_text(item["video_seconds"])}초<br>'
                     f'AI 판정: {_text(item["plate_status"])} · 확정 번호: {_text(item["plate_number"] or "없음")}</p>'
                     f'<div class="samples">{"".join(samples)}</div></section>')
    # 2. 스크립트·외부 이미지·네트워크 요청 없이 단일 파일로 열 수 있습니다.
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>번호판 수동 검토 — {_text(snapshot["run_id"])}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:auto;padding:24px;background:#f5f7fa;color:#172334}}
section{{background:white;padding:20px;margin:20px 0;border:1px solid #ccd3dd;border-radius:8px}}
.samples{{display:flex;flex-wrap:wrap;gap:16px}}figure{{margin:0;width:300px}}img{{max-width:100%;max-height:180px;object-fit:contain}}
small{{display:block;overflow-wrap:anywhere;color:#536175}}.missing{{color:#714b00}}code{{overflow-wrap:anywhere}}</style></head>
<body><h1>번호판 수동 검토</h1><p>실행 ID: {_text(snapshot["run_id"])}</p>
<p>전체 OCR 차량 {len(snapshot["items"])}대 중 offset {offset}부터 {len(items)}대 · 표시 이미지 {image_count}장</p>
<p>검토 대상 식별값: <code>{_text(snapshot["snapshot_sha256"])}</code></p>
<p>AI 판정은 정답이 아닙니다. 영상을 함께 확인한 뒤 같은 실행·식별값의 CSV에서 정답을 입력하세요.
이 문서는 읽기 전용이며 검토 상태를 저장하지 않습니다. 외국 번호판은 OUT_OF_SCOPE로 구분합니다.</p>
{"".join(cards) or '<p>이 페이지에 표시할 차량이 없습니다.</p>'}</body></html>'''

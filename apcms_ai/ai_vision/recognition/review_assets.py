# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/review_assets.py

"""검토 대상 차량에 속한 번호판 이미지와 OCR 표본만 읽습니다."""

import base64
import hashlib
import io
import warnings

from PIL import Image

from ai_vision.recognition.local_io import iter_jsonl
from ai_vision.recognition.result_validation import public_passage

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 24 * 1024 * 1024


def read_plate_image(catalog, folder, track_id, frame_index):
    # 1. JSON의 임의 경로를 사용하지 않고 기존 저장 규칙으로 파일명을 만듭니다.
    if any(type(value) is not int or value < 0 for value in (track_id, frame_index)):
        raise ValueError("검토 이미지의 차량·프레임 번호가 유효하지 않습니다.")
    path = folder / f"id_{track_id}_frame_{frame_index}_plate.jpg"
    if not path.exists() and not path.is_symlink():
        return None
    resolved = catalog.safe_file(path)
    if resolved.parent != folder.resolve():
        raise ValueError("다른 폴더의 검토 이미지는 읽을 수 없습니다.")
    with resolved.open("rb") as handle:
        raw = handle.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("검토 이미지가 4MB를 초과했습니다.")
    try:
        # JPEG 검증으로 확장자만 이미지인 파일과 과도하게 큰 이미지를 거릅니다.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as picture:
                if picture.format != "JPEG" or picture.width * picture.height > 20_000_000:
                    raise ValueError("검토 이미지의 형식이나 크기를 확인해 주세요.")
                picture.verify()
            # JPEG의 verify만으로는 잘린 픽셀 데이터가 통과할 수 있어 디코딩도 확인합니다.
            with Image.open(io.BytesIO(raw)) as picture:
                picture.load()
    except (OSError, Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
        raise ValueError("검토 JPEG 파일이 손상됐습니다.") from error
    return {"base64": base64.b64encode(raw).decode("ascii"), "sha256": hashlib.sha256(raw).hexdigest(), "byte_size": len(raw)}


def load_evidence(catalog, run_id, snapshot, track_ids=None):
    folder, _ = catalog.review_source(run_id)
    expected = {item["track_id"]: item for item in snapshot["items"]}
    selected = set(expected) if track_ids is None else set(track_ids)
    if not selected <= set(expected):
        raise ValueError("원본에 없는 검토 차량입니다.")
    evidence, seen, total_bytes = {}, set(), 0
    for row in iter_jsonl(catalog.safe_file(folder / "passages.jsonl")):
        public = public_passage(row)
        track = public["track_id"]
        if track in seen or expected.get(track) != public:
            raise ValueError("검토 대상과 OCR 표본이 일치하지 않습니다.")
        seen.add(track)
        if track not in selected:
            continue
        samples = []
        for sample in row["samples"]:
            image = read_plate_image(catalog, folder, track, sample["frame_index"])
            total_bytes += image["byte_size"] if image else 0
            if total_bytes > MAX_TOTAL_IMAGE_BYTES:
                raise ValueError("검토 이미지 합계가 24MB를 초과했습니다.")
            # 2. OCR 문자열만 표시하고 로그의 경로·내부 오류는 가져오지 않습니다.
            text = sample.get("plate_number", "")
            samples.append({"frame_index": sample["frame_index"], "video_seconds": sample["video_seconds"],
                            "ocr_text": text[:200] if isinstance(text, str) else "", "image": image})
        evidence[track] = samples
    if seen != set(expected):
        raise ValueError("일부 검토 차량의 OCR 표본이 누락됐습니다.")
    return evidence

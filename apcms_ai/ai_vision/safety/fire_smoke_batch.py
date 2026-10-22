# D:/finalProjectB/back/apcms_ai/ai_vision/safety/fire_smoke_batch.py
"""여러 화재·연기·정상 이미지를 동일 YOLO 모델로 일괄 비교합니다.

실행 예시:
    python -m ai_vision.safety.fire_smoke_batch --save-annotated

이 도구는 테스트·모델 성능 비교용입니다. 화재 경보나 안전 판정에 직접 사용하지 않습니다.
"""

# 1. 필요한 라이브러리 및 경로
# 1-1. 프로젝트 기존 경로 정의를 재사용하므로 기존 소스는 수정하지 않습니다.
import argparse
import csv
import json
import math
import time
from pathlib import Path

import cv2

from ai_vision.paths import MODEL_DIR, RESULT_DIR, TEST_IMAGE_DIR
from ai_vision.recognition.model_files import require_model_file

MODEL_PATH = MODEL_DIR / "fire_smoke.pt"
DEFAULT_MANIFEST = TEST_IMAGE_DIR / "safety" / "fire_smoke_labels.json"
DEFAULT_OUTPUT_DIR = RESULT_DIR / "safety" / "batch_compare"
VALID_LABELS = {"FIRE", "SMOKE", "NORMAL"}


# 2. 설정값과 테스트 데이터 검증
# 2-1. 0~1 범위의 여러 수치를 쉼표로 받아 잘못된 설정을 즉시 차단합니다.
def parse_levels(raw, name):
    try:
        values = [float(part.strip()) for part in raw.split(",")]
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{name}: 쉼표로 구분한 숫자를 입력하세요.") from error
    if not values or len(values) > 12 or any(not math.isfinite(v) or not 0 < v < 1 for v in values):
        raise ValueError(f"{name}: 각 값은 0과 1 사이이고, 최대 12개까지 허용합니다.")
    if len(values) != len(set(values)):
        raise ValueError(f"{name}: 중복된 값을 제거하세요.")
    return values


# 2-2. 예상 정답은 파일명에서 추측하지 않고 사람이 지정한 manifest에서만 읽습니다.
def load_manifest(manifest_path):
    manifest_path = Path(manifest_path)
    root = manifest_path.parent
    with manifest_path.open("r", encoding="utf-8-sig") as stream:
        cases = json.load(stream)
    if not isinstance(cases, list) or not cases:
        raise ValueError("라벨 JSON은 항목이 하나 이상인 리스트여야 합니다.")

    verified = []
    seen = set()
    for index, case in enumerate(cases, 1):
        if not isinstance(case, dict) or set(case) != {"file", "expected"}:
            raise ValueError(f"{index}번: file / expected 두 속성이 필요합니다.")
        name, expected = case["file"], case["expected"]
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError(f"{index}번: 하위 경로가 아닌 단일 이미지 파일명을 지정하세요.")
        if Path(name).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError(f"{index}번: 지원하지 않는 이미지 확장자입니다.")
        if expected not in VALID_LABELS:
            raise ValueError(f"{index}번: expected는 FIRE / SMOKE / NORMAL 중 하나여야 합니다.")
        if name in seen:
            raise ValueError(f"{index}번: 중복된 파일명입니다: {name}")
        seen.add(name)
        image_path = root / name
        if not image_path.is_file():
            raise FileNotFoundError(f"테스트 이미지가 없습니다: {image_path}")
        verified.append({"file": name, "expected": expected, "path": image_path})
    return verified


# 3. 객체 탐지 및 박스 품질 분석
# 3-1. 서로 같은 클래스로 분류된 두 박스의 중복 정도(IoU)를 구합니다.
def calculate_iou(a, b):
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[2], b[2])
    bottom = min(a[3], b[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


# 3-2. 결과 객체를 JSON에 기록할 수 있는 데이터로 변환합니다.
def extract_detections(result, names, image_shape):
    height, width = image_shape[:2]
    image_area = max(1, height * width)
    detections = []
    for box in result.boxes:
        class_id = int(box.cls[0].item())
        class_name = str(names[class_id]).upper()
        confidence = float(box.conf[0].item())
        bbox = [round(float(v)) for v in box.xyxy[0].tolist()]
        area = max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])
        detections.append({
            "class_name": class_name,
            "confidence": round(confidence, 4),
            "bbox": bbox,
            "box_area_ratio": round(min(1.0, area / image_area), 4),
        })
    return detections


# 3-3. 기존 사진과 겹쳐 보이는 큰 박스를 수치로 확인합니다.
def analyze_detections(detections):
    overlap_pairs = 0
    for i, first in enumerate(detections):
        for second in detections[i + 1:]:
            if first["class_name"] == second["class_name"]:
                if calculate_iou(first["bbox"], second["bbox"]) >= 0.5:
                    overlap_pairs += 1
    return {
        "fire_count": sum(x["class_name"] == "FIRE" for x in detections),
        "smoke_count": sum(x["class_name"] == "SMOKE" for x in detections),
        "max_confidence": max((x["confidence"] for x in detections), default=0.0),
        "overlap_pairs_iou_05": overlap_pairs,
        "max_box_area_ratio": max((x["box_area_ratio"] for x in detections), default=0.0),
    }


# 3-4. 불꽃·연기·정상 사진의 예상 상태와 모델 결과를 비교합니다.
#      이 결과는 소규모 샘플용 확인값이지 실제 안전 시스템 정확도가 아닙니다.
def is_case_passed(expected, fire_count, smoke_count):
    if expected == "FIRE":
        return fire_count > 0
    if expected == "SMOKE":
        return smoke_count > 0 and fire_count == 0
    return fire_count == 0 and smoke_count == 0


# 4. 비교 결과 요약 및 CSV/JSON 저장
# 4-1. 신뢰도 및 NMS 조합별 누락·오탐·중복 박스 수를 계산합니다.
def summarize(rows):
    groups = {}
    for row in rows:
        key = (row["conf"], row["iou"])
        groups.setdefault(key, []).append(row)
    summary_rows = []
    for (conf, iou), cases in sorted(groups.items()):
        fires = [x for x in cases if x["expected"] == "FIRE"]
        smokes = [x for x in cases if x["expected"] == "SMOKE"]
        normals = [x for x in cases if x["expected"] == "NORMAL"]
        summary_rows.append({
            "conf": conf,
            "iou": iou,
            "images": len(cases),
            "passed": sum(x["case_passed"] for x in cases),
            "fire_misses": sum(x["fire_count"] == 0 for x in fires),
            "smoke_misses": sum(x["smoke_count"] == 0 for x in smokes),
            "smoke_as_fire": sum(x["fire_count"] > 0 for x in smokes),
            "normal_false_alarms": sum(x["fire_count"] > 0 or x["smoke_count"] > 0 for x in normals),
            "overlap_pairs_iou_05": sum(x["overlap_pairs_iou_05"] for x in cases),
            "large_box_images_over_50pct": sum(x["max_box_area_ratio"] > .5 for x in cases),
            "avg_inference_ms": round(sum(x["inference_ms"] for x in cases) / len(cases), 2),
        })
    return summary_rows


def save_csv(path, rows, columns):
    # 4-2. Excel에서 한글이 깨지지 않도록 UTF-8 BOM으로 저장합니다.
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# 5. 실제 일괄 추론 실행
# 5-1. 모델을 한 번 생성한 뒤 모든 테스트 이미지와 설정에 재사용합니다.
def run_batch(manifest_path=DEFAULT_MANIFEST, output_dir=DEFAULT_OUTPUT_DIR,
              confidences=None, ious=None, image_size=640, device="cpu", save_annotated=False):
    confidences = [0.15, 0.20, 0.25] if confidences is None else confidences
    ious = [0.45, 0.50, 0.70] if ious is None else ious
    cases = load_manifest(manifest_path)
    if type(image_size) is not int or not 32 <= image_size <= 2048:
        raise ValueError("image_size는 32~2048 사이의 정수여야 합니다.")
    require_model_file(MODEL_PATH)
    from ultralytics import YOLO  # 추론 실행 시에만 무거운 라이브러리를 가져옵니다.

    start_load = time.perf_counter()
    model = YOLO(str(MODEL_PATH))
    model_init_ms = round((time.perf_counter() - start_load) * 1000, 2)

    # 5-2. 손상 이미지가 있으면 결과 파일을 쓰기 전에 오류를 알립니다.
    images = {}
    for case in cases:
        image = cv2.imread(str(case["path"]))
        if image is None:
            raise ValueError(f"이미지를 읽을 수 없습니다: {case['path']}")
        images[case["file"]] = image

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    details = []
    total = len(cases) * len(confidences) * len(ious)
    current = 0
    for conf in confidences:
        for iou in ious:
            setting = f"conf_{conf:.2f}_iou_{iou:.2f}"
            annotated_dir = output_dir / setting
            if save_annotated:
                annotated_dir.mkdir(parents=True, exist_ok=True)
            for case in cases:
                # 5-3. 같은 사진을 현재 설정으로 추론하여 처리 시간을 측정합니다.
                frame = images[case["file"]]
                start = time.perf_counter()
                result = model.predict(source=frame, conf=conf, iou=iou,
                                       imgsz=image_size, device=device, verbose=False)[0]
                inference_ms = round((time.perf_counter() - start) * 1000, 2)
                detections = extract_detections(result, model.names, frame.shape)
                stats = analyze_detections(detections)
                passed = is_case_passed(case["expected"], stats["fire_count"], stats["smoke_count"])
                record = {
                    "image_name": case["file"], "expected": case["expected"],
                    "conf": conf, "iou": iou, "case_passed": passed,
                    "inference_ms": inference_ms, **stats,
                }
                records.append(record)
                details.append({**record, "detections": detections})
                if save_annotated:
                    annotated = result.plot()
                    target = annotated_dir / f"{Path(case['file']).stem}_detected.jpg"
                    if not cv2.imwrite(str(target), annotated):
                        raise OSError(f"결과 이미지 저장 실패: {target}")
                current += 1
                print(f"[{current:02d}/{total:02d}] {setting} | {case['file']} | "
                      f"FIRE={stats['fire_count']} SMOKE={stats['smoke_count']} | "
                      f"{'PASS' if passed else 'CHECK'} | {inference_ms:.2f}ms")

    summary_rows = summarize(records)
    # 5-4. 상세 비교표와 설정별 집계, 탐지 박스 원본 데이터를 저장합니다.
    detail_columns = ["image_name", "expected", "conf", "iou", "case_passed",
                      "fire_count", "smoke_count", "max_confidence", "inference_ms",
                      "overlap_pairs_iou_05", "max_box_area_ratio"]
    summary_columns = ["conf", "iou", "images", "passed", "fire_misses", "smoke_misses",
                       "smoke_as_fire", "normal_false_alarms", "overlap_pairs_iou_05",
                       "large_box_images_over_50pct", "avg_inference_ms"]
    save_csv(output_dir / "detections.csv", records, detail_columns)
    save_csv(output_dir / "summary.csv", summary_rows, summary_columns)
    payload = {
        "note": "소수의 생성 이미지 비교 결과이며 실제 화재·연기 감지 성능이나 안전성을 보장하지 않습니다.",
        "model": str(MODEL_PATH),
        "model_init_ms": model_init_ms,
        "image_size": image_size,
        "device": device,
        "image_count": len(cases),
        "settings_count": len(confidences) * len(ious),
        "summary": summary_rows,
        "results": details,
    }
    with (output_dir / "results.json").open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(f"\n완료: 이미지 {len(cases)}장 × 설정 {len(confidences) * len(ious)}종")
    print(f"결과 폴더: {output_dir}")
    print("요약 CSV: summary.csv / 이미지별 CSV: detections.csv / 상세 JSON: results.json")
    return payload


# 6. 콘솔 실행 인자
# 6-1. --save-annotated를 지정한 경우에만 박스가 그려진 결과 이미지를 만듭니다.
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--conf", default="0.15,0.20,0.25", help="신뢰도 기준값 목록")
    parser.add_argument("--iou", default="0.45,0.50,0.70", help="YOLO NMS IoU 기준값 목록")
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--save-annotated", action="store_true")
    args = parser.parse_args(argv)
    try:
        run_batch(args.manifest, args.output_dir,
                  parse_levels(args.conf, "conf"), parse_levels(args.iou, "iou"),
                  args.image_size, args.device, args.save_annotated)
    except (ValueError, FileNotFoundError, OSError) as error:
        parser.exit(1, f"[테스트 중단] {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

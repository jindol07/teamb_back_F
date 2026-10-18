# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/results_catalog.py

"""허용된 결과 폴더에서 실행 요약과 차량 판정만 읽는 저장소."""

import math
import re
from pathlib import Path

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import read_json, iter_jsonl
from ai_vision.recognition.plate_consensus import summarize_plate_samples

PLATE_STATUSES = {"CONFIRMED", "CONFLICT", "INSUFFICIENT_EVIDENCE", "NO_VALID_KOREAN_PLATE"}


def _counts(value, allowed):
    if not isinstance(value, dict) or any(k not in allowed or type(v) is not int or v < 0 for k, v in value.items()):
        raise ValueError("결과 건수 형식이 유효하지 않습니다.")
    return dict(value)


class ResultCatalog:
    def __init__(self, root=RESULT_DIR / "recognition"):
        self.root = Path(root).resolve()

    def folder(self, run_id):
        # 1. 사용자에게 파일 경로를 받지 않고 제한된 폴더 이름만 받습니다.
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", run_id):
            raise ValueError("실행 ID 형식이 유효하지 않습니다.")
        folder = (self.root / run_id).resolve()
        if folder.parent != self.root:
            raise ValueError("허용된 결과 폴더 밖으로 접근할 수 없습니다.")
        if not folder.is_dir():
            raise FileNotFoundError("실행 결과가 없습니다.")
        return folder

    def safe_file(self, path):
        # 폴더 내부 심볼릭 링크도 최종 경로를 확인해 외부 파일 접근 차단
        path = Path(path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("허용된 결과 파일이 아닙니다.")
        if not path.is_file():
            raise FileNotFoundError("결과 파일이 없습니다.")
        return path

    def overview(self, run_id):
        folder = self.folder(run_id)
        manifest = folder / "pipeline.json"
        state = read_json(self.safe_file(manifest)) if manifest.exists() else None
        result = {"run_id": run_id, "http_enabled": False}
        if state is not None:
            if state.get("http_enabled") is not False or state.get("status") not in {"RUNNING", "FAILED", "COMPLETED"}:
                raise ValueError("통합 실행 상태를 확인해 주세요.")
            result.update(kind="pipeline", status=state["status"], stage=state.get("stage"))
            if state["status"] != "COMPLETED":
                # 내부 오류 메시지에 포함될 수 있는 로컬 절대 경로는 노출하지 않음
                return result
        summary = read_json(self.safe_file(folder / "summary.json"))
        if summary.get("http_enabled") is not False:
            raise ValueError("로컬 전용 결과가 아닙니다.")
        if "total_crossings" in summary:
            result.update(kind="pipeline", status=result.get("status", "SAVED"),
                          crossing_counts=_counts(summary["crossing_counts"], {"UP", "DOWN"}),
                          plate_status_counts=_counts(summary["plate_status_counts"], PLATE_STATUSES))
            for key in ("total_crossings", "ocr_processed", "ocr_not_processed"):
                if type(summary[key]) is not int or summary[key] < 0:
                    raise ValueError("처리 건수가 유효하지 않습니다.")
                result[key] = summary[key]
            if result["ocr_processed"] + result["ocr_not_processed"] != result["total_crossings"]:
                raise ValueError("처리·미처리 합계가 일치하지 않습니다.")
            result["ocr_coverage"] = summary["ocr_coverage"]
        elif "counts" in summary:
            result.update(kind="tracking", status="SAVED", crossing_counts=_counts(summary["counts"], {"UP", "DOWN"}))
            result["total_crossings"] = sum(result["crossing_counts"].values())
        elif "processed_tracks" in summary:
            result.update(kind="ocr", status="SAVED")
            for key in ("crossings_in_run", "processed_tracks", "confirmed_plates"):
                if type(summary[key]) is not int or summary[key] < 0:
                    raise ValueError("OCR 처리 건수가 유효하지 않습니다.")
                result[key] = summary[key]
        else:
            raise ValueError("지원하지 않는 결과 요약입니다.")
        return result

    def list_runs(self, offset=0, limit=20):
        self.pagination(offset, limit)
        if not self.root.is_dir():
            return {"total": 0, "offset": offset, "limit": limit, "items": []}
        items = []
        # 2. 목록은 이름순이며 모델 초기화, 재시도, 파일 쓰기를 수행하지 않음
        for folder in sorted(self.root.iterdir(), key=lambda p: p.name):
            if not folder.is_dir() or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", folder.name):
                continue
            if not (folder / "summary.json").exists() and not (folder / "pipeline.json").exists():
                continue
            try:
                items.append(self.overview(folder.name))
            except (OSError, ValueError, KeyError, TypeError):
                items.append({"run_id": folder.name, "status": "UNAVAILABLE"})
        return {"total": len(items), "offset": offset, "limit": limit, "items": items[offset:offset + limit]}

    @staticmethod
    def pagination(offset, limit):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("offset은 0 이상, limit은 1~100이어야 합니다.")

    def passages(self, run_id, offset=0, limit=20):
        self.pagination(offset, limit)
        folder = self.folder(run_id)
        overview = self.overview(run_id)
        if overview["kind"] == "pipeline":
            if overview["status"] not in {"COMPLETED", "SAVED"}:
                raise ValueError("완료되지 않은 실행입니다.")
            summary = read_json(self.safe_file(folder / "summary.json"))
            folder = Path(summary["ocr_dir"])
        elif overview["kind"] != "ocr":
            raise FileNotFoundError("이 실행에는 OCR 결과가 없습니다.")
        path = self.safe_file(folder / "passages.jsonl")
        selected, total = [], 0
        for index, row in enumerate(iter_jsonl(path)):
            if (row.get("http_enabled") is not False or row.get("record_type") != "LOCAL_TRACKED_PASSAGE" or
                    type(row.get("track_id")) is not int or row["track_id"] < 0 or
                    row.get("screen_direction") not in {"UP", "DOWN"}):
                raise ValueError("통과 판정 결과 형식이 유효하지 않습니다.")
            time = row.get("crossing_video_seconds")
            if isinstance(time, bool) or not isinstance(time, (int, float)) or not math.isfinite(time) or time < 0:
                raise ValueError("통과 시각이 유효하지 않습니다.")
            consensus = row["plate_consensus"]
            checked = summarize_plate_samples(row["samples"], consensus["minimum_votes"], consensus["minimum_spacing_seconds"])
            if checked != consensus:
                raise ValueError("번호판 판정과 원본 표본이 일치하지 않습니다.")
            if offset <= index < offset + limit:
                selected.append({"track_id": row["track_id"], "screen_direction": row["screen_direction"],
                                 "video_seconds": time, "plate_status": checked["status"],
                                 "plate_number": checked["plate_number"], "sample_count": len(row["samples"])})
            total += 1
        return {"run_id": run_id, "total": total, "offset": offset, "limit": limit,
                "items": selected, "http_enabled": False}

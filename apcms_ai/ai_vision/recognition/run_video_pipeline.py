# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/run_video_pipeline.py

"""영상 추적과 통과 차량 OCR을 순서대로 실행하는 로컬 전용 작업 도구."""

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

from ai_vision.paths import BASE_DIR
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.tracking_config import parse_with_config
from ai_vision.recognition.local_io import read_json as strict_read_json, iter_jsonl, write_json_atomic


def read_json(path):
    return strict_read_json(path)


def read_rows(path):
    return list(iter_jsonl(path))


def preflight(args):
    # 1. 재사용 경로가 잘못된 경우 무거운 OCR을 시작하기 전에 중단합니다.
    if not args.source.is_file():
        raise ValueError("입력 영상이 없습니다.")
    if args.reuse_ocr and not args.reuse_tracking:
        raise ValueError("OCR 재사용에는 원래 추적 결과도 필요합니다.")
    if args.reuse_tracking:
        folder = args.reuse_tracking
        for name in ("summary.json", "crossings.jsonl", "observations.jsonl"):
            if not (folder / name).is_file():
                raise ValueError(f"재사용 추적 결과가 없습니다: {name}")
        summary = read_json(folder / "summary.json")
        if Path(summary["source"]).resolve() != args.source.resolve() or summary.get("http_enabled") is not False:
            raise ValueError("재사용 추적 결과의 영상 또는 로컬 실행 설정이 다릅니다.")
    if args.reuse_ocr:
        # 실제 표본 연결 관계까지 사전 검사해 불일치 자료를 섞지 않음
        combine_results(args.source, args.reuse_tracking, args.reuse_ocr)


def combine_results(source, tracking_dir, ocr_dir):
    # 1. 다른 영상이나 다른 실행에서 나온 결과가 섞이지 않았는지 확인합니다.
    tracking = read_json(tracking_dir / "summary.json")
    ocr = read_json(ocr_dir / "summary.json")
    if (Path(tracking["source"]).resolve() != source.resolve() or
            Path(ocr["source_video"]).resolve() != source.resolve() or
            Path(ocr["source_run"]).resolve() != tracking_dir.resolve()):
        raise ValueError("영상 또는 추적 실행 폴더가 서로 다른 결과입니다.")
    if tracking.get("http_enabled") is not False or ocr.get("http_enabled") is not False:
        raise ValueError("로컬 전용 결과만 결합할 수 있습니다.")
    events = read_rows(tracking_dir / "crossings.jsonl")
    passages = read_rows(ocr_dir / "passages.jsonl")
    counts = Counter(row["direction"] for row in events)
    if dict(counts) != {key: value for key, value in tracking["counts"].items() if value}:
        raise ValueError("추적 요약과 실제 통과 건수가 다릅니다.")
    by_id = {event["track_id"]: event for event in events}
    if len(by_id) != len(events):
        raise ValueError("같은 ID에 여러 통과 기록이 있어 검토가 필요합니다.")
    if ocr["crossings_in_run"] != len(events) or ocr["processed_tracks"] != len(passages):
        raise ValueError("OCR 요약과 실제 처리 건수가 다릅니다.")
    # 표본 프레임이 해당 ID로 관찰된 기록인지 확인해 다른 차량의 OCR 혼입을 방지
    observed_frames = {}
    for row in iter_jsonl(tracking_dir / "observations.jsonl"):
        key = (row["track_id"], row["frame_index"])
        if key in observed_frames:
            raise ValueError("같은 ID와 프레임의 관찰 기록이 중복됐습니다.")
        observed_frames[key] = row["video_seconds"]

    # 2. 번호판 결과가 실제 통과한 ID/방향/시각에 연결됐는지 확인합니다.
    seen = set()
    for row in passages:
        track_id = row["track_id"]
        if track_id not in by_id or track_id in seen:
            raise ValueError("OCR 결과의 차량 ID가 없거나 중복되었습니다.")
        seen.add(track_id)
        event = by_id[track_id]
        if (row["screen_direction"] != event["direction"] or
                abs(row["crossing_video_seconds"] - event["video_seconds"]) > .001 or
                row.get("http_enabled") is not False):
            raise ValueError("통과 방향·시각 또는 로컬 실행 설정이 일치하지 않습니다.")
        if row.get("record_type") != "LOCAL_TRACKED_PASSAGE":
            raise ValueError("로컬 통과 관찰 형식이 아닙니다.")
        for sample in row["samples"]:
            observed_time = observed_frames.get((track_id, sample["frame_index"]))
            if (observed_time is None or abs(observed_time - sample["video_seconds"]) > .001 or
                    not event["video_seconds"] - 2 <= sample["video_seconds"] <= event["video_seconds"] + .75):
                raise ValueError("OCR 표본이 해당 차량의 통과 전후 관찰과 일치하지 않습니다.")
        # 저장된 CONFIRMED 표시를 그대로 믿지 않고 원본 OCR 표본으로 다시 판정
        consensus = row["plate_consensus"]
        if consensus["minimum_votes"] < 2 or consensus["minimum_spacing_seconds"] < .25:
            raise ValueError("번호판 확정 기준이 현재 정책보다 약합니다.")
        checked = summarize_plate_samples(row["samples"], consensus["minimum_votes"],
                                          consensus["minimum_spacing_seconds"])
        if checked != consensus:
            raise ValueError("OCR 표본과 번호판 확정 결과가 다릅니다.")
    statuses = Counter(row["plate_consensus"]["status"] for row in passages)
    if ocr["confirmed_plates"] != statuses["CONFIRMED"]:
        raise ValueError("OCR 확정 요약 건수가 다릅니다.")

    # 3. 실행 성공과 모든 차량의 OCR 완료 여부를 구분합니다.
    return {"source_video": str(source.resolve()), "tracking_dir": str(tracking_dir.resolve()),
            "ocr_dir": str(ocr_dir.resolve()), "crossing_counts": dict(counts),
            "total_crossings": len(events), "ocr_processed": len(passages),
            "ocr_not_processed": len(events) - len(passages),
            "ocr_coverage": "ALL_RECORDED_TRACKS" if len(events) == len(passages) else "PARTIAL",
            "plate_status_counts": dict(statuses), "http_enabled": False,
            "note": "로컬 처리 결과이며 실제 입출차·번호판 정답 검증 완료를 뜻하지 않습니다."}


def run(args):
    # 4. 새 폴더에서 실행해 이전 결과를 덮어쓰거나 실패 결과와 섞지 않습니다.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = args.output_dir / "pipeline.json"
    manifest = {"status": "RUNNING", "stage": "tracking", "http_enabled": False, "stages": {}}
    manifest["config_file"] = str(args.config.resolve()) if getattr(args, "config", None) else None

    def save():
        write_json_atomic(manifest_path, manifest)

    def execute(stage, module, options):
        # 명령을 문자열로 합치지 않고 인수 목록으로 실행해 공백이 있는 경로도 처리
        manifest["stage"] = stage
        manifest["stages"][stage] = "RUNNING"
        save()
        environment = os.environ.copy()
        environment.update(PYTHONIOENCODING="utf-8", YOLO_AUTOINSTALL="false",
                           PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="True")
        print(f"[{stage}] 실행 중", flush=True)
        with (args.output_dir / f"{stage}.log").open("w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-m", module, *map(str, options)],
                           cwd=BASE_DIR.parent, env=environment, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        manifest["stages"][stage] = "GENERATED"
        save()

    save()
    try:
        manifest["stage"] = "preflight"
        manifest["stages"]["preflight"] = "RUNNING"
        save()
        preflight(args)
        manifest["stages"]["preflight"] = "VALIDATED"
        # 새 실행의 실제 좌표와 추적기를 복사해 원본 설정이 바뀌어도 근거 보존
        if not args.reuse_tracking:
            write_json_atomic(args.output_dir / "tracking_config.json", {
                key: getattr(args, key) for key in ("tracker", "line_y", "line_x", "roi")})
        save()
        tracking_dir = args.reuse_tracking or args.output_dir / "tracking"
        ocr_dir = args.reuse_ocr or args.output_dir / "ocr"
        if args.reuse_tracking:
            manifest["stages"]["tracking"] = "REUSED"
        else:
            options = ["--source", args.source, "--output-dir", tracking_dir,
                       "--tracker", args.tracker, "--save-observations",
                       "--line-y", args.line_y, "--line-x", *args.line_x, "--roi", *args.roi]
            if getattr(args, "config", None):
                options += ["--config", args.config.resolve()]
            if args.max_seconds is not None:
                options += ["--max-seconds", args.max_seconds]
            execute("tracking", "ai_vision.recognition.vehicle_tracking", options)
        if args.reuse_ocr:
            manifest["stages"]["ocr"] = "REUSED"
        else:
            options = ["--run-dir", tracking_dir, "--output-dir", ocr_dir]
            if args.max_tracks is not None:
                options += ["--max-tracks", args.max_tracks]
            execute("ocr", "ai_vision.recognition.recognize_tracked_passages", options)
        manifest["stage"] = "validation"
        manifest["stages"]["validation"] = "RUNNING"
        save()
        report = combine_results(args.source, tracking_dir, ocr_dir)
        write_json_atomic(args.output_dir / "summary.json", report)
        manifest.update(status="COMPLETED", stage="done")
        manifest["stages"]["validation"] = "VALIDATED"
        save()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except BaseException as error:
        # 5. 실패한 단계를 기록하고 종료 코드도 실패로 반환합니다. 다음 단계를 진행하지 않음
        manifest.update(status="FAILED", error_type=type(error).__name__, error=str(error))
        manifest["stages"][manifest["stage"]] = "FAILED"
        save()
        raise


if __name__ == "__main__":
    # 6. 신규 영상은 기본 traffic 영역을 사용하므로 실제 카메라에 맞게 좌표를 지정
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tracker", choices=["bytetrack", "botsort"], default="bytetrack")
    parser.add_argument("--line-y", type=float, default=.60)
    parser.add_argument("--line-x", type=float, nargs=2, default=(.15, .90))
    parser.add_argument("--roi", type=float, nargs=8, default=(.10, 1, .365, .24, .64, .24, .92, 1))
    parser.add_argument("--max-seconds", type=float)
    parser.add_argument("--max-tracks", type=int)
    parser.add_argument("--reuse-tracking", type=Path)
    parser.add_argument("--reuse-ocr", type=Path)
    args = parse_with_config(parser)
    if not args.source.is_file() or (args.reuse_ocr and not args.reuse_tracking):
        parser.error("입력 영상이 필요하며 OCR 재사용 시 해당 추적 폴더도 지정해야 합니다.")
    if ((args.max_tracks is not None and args.max_tracks < 1) or
            (args.max_seconds is not None and args.max_seconds <= 0)):
        parser.error("처리 제한은 양수여야 합니다.")
    # 자식 프로세스의 작업 폴더와 관계없이 같은 경로를 가리키도록 절대 경로로 변환
    for name in ("source", "output_dir", "reuse_tracking", "reuse_ocr"):
        if getattr(args, name) is not None:
            setattr(args, name, getattr(args, name).resolve())
    run(args)

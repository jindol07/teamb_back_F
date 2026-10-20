# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/run_video_pipeline.py

"""저장 영상을 대상으로 차량 추적 → 통과 차량 OCR → 결과 검증을 수행합니다.

이 파일은 각 처리 모듈을 별도 Python 프로세스로 실행하는 *로컬 분석 도구*입니다.
카메라 실시간 수집이나 Spring Boot HTTP 전송을 시작하지 않습니다.
출력 폴더는 새 폴더여야 하며, 실행 단계와 실패 여부를 pipeline.json에 기록합니다.
"""

# 1. 실행에 필요한 표준 라이브러리와 프로젝트 모듈
# 1-1. argparse: 명령행 옵션(--source, --tracker 등)을 읽고 검사합니다.
# 1-2. json: 최종 검증 보고서를 보기 쉬운 JSON 문자열로 출력합니다.
# 1-3. os/subprocess/sys: 환경변수를 정해 추적·OCR 모듈을 자식 프로세스로 실행합니다.
# 1-4. Counter: 차량 통과 방향과 OCR 상태별 건수를 집계합니다.
# 1-5. Path: 운영체제별 파일 경로를 다루고 존재 여부를 검사합니다.
import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

# 1-6. BASE_DIR은 작업 실행 위치를 맞추는 기준 경로입니다.
# 1-7. summarize_plate_samples는 OCR 원본 표본으로 번호판 확정 결과를 재계산합니다.
# 1-8. parse_with_config는 명령행 인수와 영상별 JSON 설정을 함께 적용합니다.
# 1-9. local_io는 JSON/JSONL의 엄격한 읽기와 JSON 원자적 저장을 제공합니다.
from ai_vision.paths import BASE_DIR
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.tracking_config import parse_with_config
from ai_vision.recognition.local_io import read_json as strict_read_json, iter_jsonl, write_json_atomic


# 2. 결과 파일을 읽기 위한 보조 함수
# 2-1. read_json(): JSON 결과 파일을 프로젝트 공용 검증 함수로 읽습니다.
# 경로를 전달받아 파싱된 Python 객체(주로 dict)를 반환합니다.
def read_json(path):
    return strict_read_json(path)


# 2-2. read_rows(): JSONL 파일의 각 줄을 개별 기록으로 읽어 리스트로 반환합니다.
# JSONL은 '한 줄에 JSON 객체 하나'를 저장하는 형식입니다.
# iter_jsonl()은 반복자로 읽으므로 list()를 적용해 전체 기록을 메모리에 모읍니다.
def read_rows(path):
    return list(iter_jsonl(path))


# 3. 본격적인 분석 전에 입력 파일과 재사용 결과를 사전 검증합니다.
# 3-1. preflight(): 문제가 있으면 YOLO/OCR 실행 전에 ValueError로 중단합니다.
# args: argparse로 읽은 실행 설정 객체입니다.
def preflight(args):
    # 3-2. 입력 영상 파일이 실제로 존재하는지 확인합니다.
    # 기존 OCR 결과를 재사용하려면 그것이 참조한 추적 결과도 함께 필요합니다.
    if not args.source.is_file():
        raise ValueError("입력 영상이 없습니다.")
    if args.reuse_ocr and not args.reuse_tracking:
        raise ValueError("OCR 재사용에는 원래 추적 결과도 필요합니다.")
    # 3-3. 추적 결과를 재사용할 경우 필수 결과 파일 세 개를 검사합니다.
    # summary.json: 실행 요약 / crossings.jsonl: 통과 이벤트 / observations.jsonl: 프레임별 관찰
    # 원본 영상 경로가 다르거나 HTTP 비활성 실행 기록이 아니면 재사용하지 않습니다.
    if args.reuse_tracking:
        folder = args.reuse_tracking
        for name in ("summary.json", "crossings.jsonl", "observations.jsonl"):
            if not (folder / name).is_file():
                raise ValueError(f"재사용 추적 결과가 없습니다: {name}")
        summary = read_json(folder / "summary.json")
        if Path(summary["source"]).resolve() != args.source.resolve() or summary.get("http_enabled") is not False:
            raise ValueError("재사용 추적 결과의 영상 또는 로컬 실행 설정이 다릅니다.")
    # 3-4. OCR 재사용에는 추적 결과와의 연결 관계까지 사전에 검증합니다.
    # 파일이 존재한다는 사실만으로 동일 차량·동일 영상의 결과라고 볼 수 없기 때문입니다.
    if args.reuse_ocr:
        # combine_results()로 통과 ID, OCR 표본, 실행 원본을 확인합니다.
        combine_results(args.source, args.reuse_tracking, args.reuse_ocr)


# 4. 추적 결과와 번호판 OCR 결과의 일치 여부를 검증하고 요약합니다.
# 4-1. source: 입력 영상 / tracking_dir: 차량 추적 결과 폴더 / ocr_dir: OCR 결과 폴더
# 실제 번호판 정답률을 계산하는 함수가 아니라, 저장 결과의 내부 일관성을 검증합니다.
def combine_results(source, tracking_dir, ocr_dir):
    # 4-2. 두 단계의 summary.json을 읽어 동일 원본 영상/추적 실행을 가리키는지 검사합니다.
    # resolve()는 상대 경로를 절대 경로로 바꾸어 경로 표현 차이를 줄입니다.
    # 둘 중 하나라도 http_enabled=False가 아니면 이 로컬 처리 경로에서 결합하지 않습니다.
    tracking = read_json(tracking_dir / "summary.json")
    ocr = read_json(ocr_dir / "summary.json")
    if (Path(tracking["source"]).resolve() != source.resolve() or
            Path(ocr["source_video"]).resolve() != source.resolve() or
            Path(ocr["source_run"]).resolve() != tracking_dir.resolve()):
        raise ValueError("영상 또는 추적 실행 폴더가 서로 다른 결과입니다.")
    if tracking.get("http_enabled") is not False or ocr.get("http_enabled") is not False:
        raise ValueError("로컬 전용 결과만 결합할 수 있습니다.")
    # 4-3. 통과 기록과 OCR 통과 결과를 불러옵니다.
    # crossings.jsonl: 추적 중 기준선을 통과한 차량 ID와 방향·시간
    # passages.jsonl: 통과 차량의 OCR 표본과 번호판 합의(plate_consensus)
    events = read_rows(tracking_dir / "crossings.jsonl")
    passages = read_rows(ocr_dir / "passages.jsonl")
    # 4-4. 통과 방향별 건수를 재집계하고 추적 요약의 counts와 비교합니다.
    # 값이 0인 방향은 비교 대상에서 빼 원본 저장 형식의 차이를 처리합니다.
    counts = Counter(row["direction"] for row in events)
    if dict(counts) != {key: value for key, value in tracking["counts"].items() if value}:
        raise ValueError("추적 요약과 실제 통과 건수가 다릅니다.")
    # 4-5. track_id를 키로 조회할 수 있게 만들고 동일 ID 중복 통과 여부를 검사합니다.
    # 이 파이프라인은 한 통과 ID마다 하나의 통과 기록을 기대합니다.
    by_id = {event["track_id"]: event for event in events}
    if len(by_id) != len(events):
        raise ValueError("같은 ID에 여러 통과 기록이 있어 검토가 필요합니다.")
    if ocr["crossings_in_run"] != len(events) or ocr["processed_tracks"] != len(passages):
        raise ValueError("OCR 요약과 실제 처리 건수가 다릅니다.")
    # 4-6. (차량 ID, 프레임 번호)를 키로 실제 관찰 시각을 저장합니다.
    # OCR 결과가 다른 차량의 프레임을 잘못 참조하는 상황을 막기 위한 대조표입니다.
    observed_frames = {}
    for row in iter_jsonl(tracking_dir / "observations.jsonl"):
        key = (row["track_id"], row["frame_index"])
        if key in observed_frames:
            raise ValueError("같은 ID와 프레임의 관찰 기록이 중복됐습니다.")
        observed_frames[key] = row["video_seconds"]

    # 4-7. OCR 처리한 각 차량이 통과 목록에 존재하고 중복되지 않았는지 검사합니다.
    # 처리한 일부 차량만 OCR에 포함될 수 있으므로 전체 통과 건수와 동일할 필요는 없습니다.
    seen = set()
    for row in passages:
        track_id = row["track_id"]
        if track_id not in by_id or track_id in seen:
            raise ValueError("OCR 결과의 차량 ID가 없거나 중복되었습니다.")
        seen.add(track_id)
        # 4-8. OCR 기록에 적힌 방향·통과 시각이 원본 추적 이벤트와 같은지 비교합니다.
        # 시각 허용 오차 .001은 초 단위 오차 1밀리초를 뜻합니다.
        event = by_id[track_id]
        if (row["screen_direction"] != event["direction"] or
                abs(row["crossing_video_seconds"] - event["video_seconds"]) > .001 or
                row.get("http_enabled") is not False):
            raise ValueError("통과 방향·시각 또는 로컬 실행 설정이 일치하지 않습니다.")
        if row.get("record_type") != "LOCAL_TRACKED_PASSAGE":
            raise ValueError("로컬 통과 관찰 형식이 아닙니다.")
        # 4-9. 각 OCR 표본의 차량 ID·프레임·시각이 원본 관찰과 맞는지 확인합니다.
        # 표본 시점은 기준선 통과 2초 전부터 0.75초 후까지만 허용합니다.
        for sample in row["samples"]:
            observed_time = observed_frames.get((track_id, sample["frame_index"]))
            if (observed_time is None or abs(observed_time - sample["video_seconds"]) > .001 or
                    not event["video_seconds"] - 2 <= sample["video_seconds"] <= event["video_seconds"] + .75):
                raise ValueError("OCR 표본이 해당 차량의 통과 전후 관찰과 일치하지 않습니다.")
        # 4-10. 저장된 CONFIRMED 상태를 무조건 신뢰하지 않고 원본 표본으로 다시 계산합니다.
        # 최소 투표 수는 2 이상, 서로 다른 OCR 표본의 간격은 0.25초 이상이어야 합니다.
        # 재계산 결과가 저장된 plate_consensus와 다르면 데이터 불일치로 중단합니다.
        consensus = row["plate_consensus"]
        if consensus["minimum_votes"] < 2 or consensus["minimum_spacing_seconds"] < .25:
            raise ValueError("번호판 확정 기준이 현재 정책보다 약합니다.")
        checked = summarize_plate_samples(row["samples"], consensus["minimum_votes"],
                                          consensus["minimum_spacing_seconds"])
        if checked != consensus:
            raise ValueError("OCR 표본과 번호판 확정 결과가 다릅니다.")
    # 4-11. 번호판 판정 상태별 건수와 OCR 요약의 확정 건수가 일치하는지 검사합니다.
    statuses = Counter(row["plate_consensus"]["status"] for row in passages)
    if ocr["confirmed_plates"] != statuses["CONFIRMED"]:
        raise ValueError("OCR 확정 요약 건수가 다릅니다.")

    # 4-12. 검증 완료 보고서를 반환합니다.
    # total_crossings: 통과 차량 ID 건수 / ocr_processed: OCR 수행 건수
    # ocr_not_processed: OCR 미처리 건수 / ocr_coverage: 전체 또는 일부 처리 구분
    # COMPLETED는 분석 흐름이 끝났다는 뜻이지 실제 한국 번호판 인식 정확도 합격이 아닙니다.
    return {"source_video": str(source.resolve()), "tracking_dir": str(tracking_dir.resolve()),
            "ocr_dir": str(ocr_dir.resolve()), "crossing_counts": dict(counts),
            "total_crossings": len(events), "ocr_processed": len(passages),
            "ocr_not_processed": len(events) - len(passages),
            "ocr_coverage": "ALL_RECORDED_TRACKS" if len(events) == len(passages) else "PARTIAL",
            "plate_status_counts": dict(statuses), "http_enabled": False,
            "note": "로컬 처리 결과이며 실제 입출차·번호판 정답 검증 완료를 뜻하지 않습니다."}


# 5. 영상 분석의 전체 실행 순서를 관리합니다.
# 5-1. run(): 사전 검사 → 차량 추적 → OCR → 결과 검증을 차례로 수행합니다.
# --reuse-tracking/--reuse-ocr가 지정된 단계는 기존 결과를 사용합니다.
def run(args):
    # 5-2. 작업 결과를 저장할 새 폴더를 생성합니다.
    # exist_ok=False이므로 동일 이름의 기존 결과가 있으면 덮어쓰지 않고 실패합니다.
    # pipeline.json에는 현재 단계와 각 단계 상태를 수시로 기록합니다.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = args.output_dir / "pipeline.json"
    manifest = {"status": "RUNNING", "stage": "tracking", "http_enabled": False, "stages": {}}
    manifest["config_file"] = str(args.config.resolve()) if getattr(args, "config", None) else None

    # 5-3. 내부 함수 save(): pipeline.json을 원자적으로 기록합니다.
    # 프로그램이 중간에 실패해도 직전 처리 단계 정보를 확인할 수 있습니다.
    def save():
        write_json_atomic(manifest_path, manifest)

    # 5-4. 내부 함수 execute(): 추적 또는 OCR 모듈을 별도 Python 프로세스로 실행합니다.
    # stage는 tracking/ocr, module은 -m 뒤 모듈명, options는 명령행 인수 목록입니다.
    # 표준 출력과 표준 오류는 각각 tracking.log 또는 ocr.log에 함께 저장합니다.
    def execute(stage, module, options):
        # 5-5. 현재 단계가 실행 중임을 먼저 기록하고 전용 환경변수를 설정합니다.
        # subprocess.run()에 쉘 문자열 대신 인수 리스트를 전달하여 공백이 있는 경로도 처리합니다.
        # check=True이므로 자식 프로세스가 비정상 종료하면 예외가 발생합니다.
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

    # 5-6. 처음 상태를 저장하고 예외를 포함한 전체 파이프라인을 실행합니다.
    save()
    try:
        manifest["stage"] = "preflight"
        manifest["stages"]["preflight"] = "RUNNING"
        save()
        preflight(args)
        manifest["stages"]["preflight"] = "VALIDATED"
        # 5-7. 사전 검사 통과를 기록하고, 새로 추적할 때는 실제 설정을 별도 저장합니다.
        # tracking_config.json: 적용된 tracker, 통과선, ROI 좌표의 사본입니다.
        if not args.reuse_tracking:
            write_json_atomic(args.output_dir / "tracking_config.json", {
                key: getattr(args, key) for key in ("tracker", "line_y", "line_x", "roi")})
        save()
        # 5-8. 재사용 디렉터리가 있으면 그 위치를, 없으면 새 하위 폴더를 사용합니다.
        tracking_dir = args.reuse_tracking or args.output_dir / "tracking"
        ocr_dir = args.reuse_ocr or args.output_dir / "ocr"
        # 5-9. 추적 재사용이면 REUSED를 기록합니다.
        # 새 추적이면 vehicle_tracking 모듈로 영상/ROI/기준선 옵션을 전달합니다.
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
        # 5-10. OCR 재사용이면 REUSED를 기록합니다.
        # 새 OCR이면 통과 차량의 추적 폴더를 지정해 recognize_tracked_passages를 실행합니다.
        if args.reuse_ocr:
            manifest["stages"]["ocr"] = "REUSED"
        else:
            options = ["--run-dir", tracking_dir, "--output-dir", ocr_dir]
            if args.max_tracks is not None:
                options += ["--max-tracks", args.max_tracks]
            execute("ocr", "ai_vision.recognition.recognize_tracked_passages", options)
        # 5-11. 추적과 OCR 두 단계가 준비되면 결과의 연결 관계를 최종 검증합니다.
        # 문제없으면 summary.json을 기록하고 전체 상태를 COMPLETED로 변경합니다.
        manifest["stage"] = "validation"
        manifest["stages"]["validation"] = "RUNNING"
        save()
        report = combine_results(args.source, tracking_dir, ocr_dir)
        write_json_atomic(args.output_dir / "summary.json", report)
        manifest.update(status="COMPLETED", stage="done")
        manifest["stages"]["validation"] = "VALIDATED"
        save()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    # 5-12. 실행 중 예외가 발생하면 실패 단계와 예외 종류를 저장한 뒤 다시 발생시킵니다.
    # 다음 단계를 수행하지 않으므로 부분 실행을 성공으로 잘못 표시하지 않습니다.
    except BaseException as error:
        # error_type에는 예외 클래스명, error에는 예외 메시지, stages에는 실패 단계가 남습니다.
        manifest.update(status="FAILED", error_type=type(error).__name__, error=str(error))
        manifest["stages"][manifest["stage"]] = "FAILED"
        save()
        raise


# 6. 명령행에서 직접 실행할 때의 진입점
# 6-1. python -m ai_vision.recognition.run_video_pipeline 형태로 실행한 경우에만 적용됩니다.
if __name__ == "__main__":
    # 6-2. 인식할 동영상 경로와 결과 출력 폴더를 필수로 받습니다.
    # --tracker: bytetrack 또는 botsort / --line-y: 화면 높이 대비 수평선 비율
    # --line-x: 수평선 양 끝 x좌표 비율 / --roi: 네 꼭짓점의 (x,y) 비율 8개
    # --max-seconds: 분석할 영상 길이 제한 / --max-tracks: OCR 수행 ID 수 제한
    # --reuse-tracking, --reuse-ocr: 과거 실행 결과를 재사용할 폴더
    # 기본 좌표는 예제 traffic 영상 기준이므로 다른 촬영 구도에서는 재설정해야 합니다.
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
    # 6-3. JSON 설정 파일과 직접 지정한 옵션을 결합하여 인수를 해석합니다.
    args = parse_with_config(parser)
    # 6-4. 파일 존재, 재사용 조합, 처리 제한값을 마지막으로 확인합니다.
    # 문제가 있으면 argparse의 parser.error()로 사용법과 함께 중단합니다.
    if not args.source.is_file() or (args.reuse_ocr and not args.reuse_tracking):
        parser.error("입력 영상이 필요하며 OCR 재사용 시 해당 추적 폴더도 지정해야 합니다.")
    if ((args.max_tracks is not None and args.max_tracks < 1) or
            (args.max_seconds is not None and args.max_seconds <= 0)):
        parser.error("처리 제한은 양수여야 합니다.")
    # 6-5. 자식 프로세스에서도 같은 경로를 사용하도록 입력 경로들을 절대 경로로 바꿉니다.
    # 최종적으로 run(args)를 호출하여 전체 작업을 수행합니다.
    for name in ("source", "output_dir", "reuse_tracking", "reuse_ocr"):
        if getattr(args, name) is not None:
            setattr(args, name, getattr(args, name).resolve())
    run(args)

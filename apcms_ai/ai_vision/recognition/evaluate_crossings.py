"""관찰한 차량별 통과 구간과 자동 이벤트를 일대일로 대조합니다."""

import argparse
import json
from pathlib import Path


# 역할: 관찰 차량과 자동 통과 이벤트를 검토 범위 안에서 일대일로 연결해 보고서를 반환합니다.
def evaluate(events, annotations):
    # 1. 검토한 시간과 차로만 선택합니다. 다른 차로·다른 시간은 오탐으로 세지 않음
    # 1-1. scope는 사람이 실제로 확인한 시간·차로 범위이고 vehicles는 차량별 허용 시각·방향 목록입니다.
    scope = annotations["scope"]
    labels = annotations["vehicles"]
    if not (scope["start_seconds"] < scope["end_seconds"] and scope["x_min"] < scope["x_max"]):
        raise ValueError("검토 시간과 차로 범위를 확인해 주세요.")
    if len({label["label_id"] for label in labels}) != len(labels):
        raise ValueError("차량별 label_id는 중복될 수 없습니다.")
    for label in labels:
        if not (scope["start_seconds"] <= label["earliest_seconds"] <=
                label["latest_seconds"] <= scope["end_seconds"]):
            raise ValueError("차량 통과 허용 구간은 검토 시간 안에 있어야 합니다.")
        if label["direction"] not in {"UP", "DOWN"}:
            raise ValueError("관찰 방향은 UP 또는 DOWN이어야 합니다.")
    # 1-2. enumerate()로 원본 이벤트의 0부터 시작하는 번호를 보존하며 시간·가로 범위를 거릅니다.
    selected = [(index, event) for index, event in enumerate(events)
                if scope["start_seconds"] <= event["video_seconds"] < scope["end_seconds"]
                and scope["x_min"] <= event["crossing_point"][0] <= scope["x_max"]]

    # 2. 방향과 관찰 시간 구간이 맞는 자동 기록을 각 차량의 후보로 연결합니다.
    candidates = []
    for label in labels:
        midpoint = (label["earliest_seconds"] + label["latest_seconds"]) / 2
        possible = [index for index, event in selected
                    if event["direction"] == label["direction"]
                    and label["earliest_seconds"] <= event["video_seconds"] <= label["latest_seconds"]]
        # 2-1. 후보의 시각이 관찰 구간 가운데에 가까운 순으로 정렬합니다. 가능한 대응을 우선 시도할 순서입니다.
        candidates.append(sorted(possible, key=lambda i: abs(events[i]["video_seconds"] - midpoint)))

    # 3. 한 차량에 여러 이벤트를 성공으로 붙이지 않도록 일대일 대응을 찾습니다.
    # 3-1. 허용 구간이 겹치면 기존 대응을 옮겨 가능한 전체 대응 수를 확보(이분 매칭)
    # 3-2. 키는 원본 자동 이벤트의 인덱스, 값은 연결된 관찰 차량의 인덱스입니다.
    event_to_label = {}

    # 역할: 깊이 우선 탐색으로 이미 연결된 이벤트를 다른 차량에 재배치할 수 있는지 찾습니다.
    def match(label_index, visited):
        for event_index in candidates[label_index]:
            if event_index in visited:
                continue
            visited.add(event_index)
            # 3-3. 점유된 이벤트라도 기존 차량을 다른 후보로 옮길 수 있으면 현재 차량에 연결합니다.
            if event_index not in event_to_label or match(event_to_label[event_index], visited):
                event_to_label[event_index] = label_index
                return True
        return False

    for label_index in range(len(labels)):
        match(label_index, set())
    # 3-4. 집합으로 연결 성공한 관찰 차량을 중복 없이 모읍니다.
    matched_labels = set(event_to_label.values())
    unmatched = [index for index, _ in selected if index not in event_to_label]
    # 3-5. 대응되지 않은 기록 중 어떤 차량의 허용 구간에는 들어가는 기록을 중복 후보로 분류합니다.
    duplicate_candidates = [index for index in unmatched
                            if any(index in options for options in candidates)]

    # 4. 잠정 관찰 결과는 정확도가 아니라 대응·누락·추가 기록으로 구분합니다.
    return {
        "label_status": annotations["label_status"],
        "scope": scope, "expected_vehicles": len(labels), "recorded_events": len(selected),
        "matched_vehicles": len(matched_labels),
        "missing_label_ids": [label["label_id"] for i, label in enumerate(labels) if i not in matched_labels],
        # 4-1. 보고서의 이벤트 번호는 로그의 순서와 대조하기 쉽도록 0 기반 인덱스에 1을 더합니다.
        "extra_event_indices": [i + 1 for i in unmatched],
        "duplicate_candidate_indices": [i + 1 for i in duplicate_candidates],
        "matches": [{"label_id": labels[label_index]["label_id"], "event_index": index + 1,
                     "track_id": events[index]["track_id"], "video_seconds": events[index]["video_seconds"]}
                    for index, label_index in sorted(event_to_label.items())],
        "note": "Codex 잠정 관찰 기준의 비교이며 독립 정답이나 전체 영상 정확도를 뜻하지 않습니다."
    }


# 역할: 추적 결과와 관찰 파일의 조건을 확인한 뒤 JSON 평가 보고서를 저장합니다.
def run(run_dir, annotation_path):
    # 5. 다른 영상이나 다른 기준선의 로그를 비교하지 않도록 기본 설정도 확인합니다.
    annotations = json.loads(annotation_path.read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    if (Path(summary["source"]).name != annotations["source_name"] or
            summary["line_y"] != annotations["line_y"]):
        raise ValueError("영상 이름 또는 기준선 높이가 관찰 자료와 다릅니다.")
    start = summary.get("start_seconds", 0)
    # 5-1. 처리 프레임 수·건너뛰기 간격·원본 FPS로 실행 구간의 끝을 계산합니다.
    end = start + summary["processed_frames"] * summary["stride"] / summary["source_fps"]
    if start > annotations["scope"]["start_seconds"] or end < annotations["scope"]["end_seconds"]:
        raise ValueError("자동 실행 결과가 관찰 구간 전체를 포함하지 않습니다.")
    events = [json.loads(line) for line in (run_dir / "crossings.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    report = evaluate(events, annotations)
    report["annotations"] = str(annotation_path.resolve())
    path = run_dir / f"evaluation_{annotation_path.stem}.json"
    # 5-2. 평가 보고서를 현재 추적 실행 폴더에 JSON 파일로 저장합니다.
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # 6. 모델이나 서버를 호출하지 않고 이미 저장된 파일만 비교합니다.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    args = parser.parse_args()
    run(args.run_dir, args.annotations)

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_report_html.py

"""검사된 세션 자료를 외부 연결 없는 HTML로 표시합니다."""

from html import escape


def render_html(report):
    # 1. 카메라 이름·번호판 등 모든 값은 HTML 문자로 이스케이프합니다.
    def cell(value):
        return escape("" if value is None else str(value), quote=True)

    headers = ("차량 ID", "수집 시각", "경과 초", "번호판 상태", "번호판", "표본 수", "판정", "응답 상태", "요청 시도",
               "채택 표 수", "필요 표 수", "최소 표본 간격(초)")
    keys = ("track_id", "captured_at", "crossing_elapsed_seconds", "plate_status", "plate_number",
            "sample_count", "decision", "receipt_state", "request_attempted",
            "accepted_votes", "required_votes", "minimum_spacing_seconds")
    rows = "".join("<tr>" + "".join(f"<td>{cell('UNKNOWN' if key == 'request_attempted' and row[key] is None else row[key])}</td>"
                   for key in keys) + "</tr>" for row in report["rows"])
    if not rows:
        rows = f'<tr><td colspan="{len(headers)}">통과 자료가 없습니다.</td></tr>'
    source = "합성 예시" if report["uses_synthetic_source"] else "카메라 실행 기록"
    summary = [("실행 출처", source), ("상태 / 종료 사유", f'{report["status"]} / {report["stop_reason"]}'),
               ("카메라", report["camera_id"]), ("세션", report["session_id"]),
               ("화면 DOWN 방향", report["down_direction"]), ("프레임 수", report["captured_frames"]),
               ("통과 자료 수", report["processed_passages"]), ("HTTP 활성", report["http_enabled"]),
               ("요청 시도 수", report["request_attempts"]), ("요청 시도 여부 불명", report["unknown_request_attempts"]),
               ("자원 정리 오류", report["cleanup_errors"]), ("오류 종류", report["error_type"]),
               ("crop 보관 실패", report["dropped_crops"]), ("차량 한도로 생략한 관찰", report["dropped_tracks"])]
    end_policy = report.get("source_end_expected")
    summary.append(("입력 종료 정책", "기록 없음" if end_policy is None else
                    ("입력 끝을 정상 종료로 허용" if end_policy else "카메라 읽기 종료는 실패로 처리")))
    details = "".join(f"<dt>{cell(key)}</dt><dd>{cell(value)}</dd>" for key, value in summary)
    counts = " / ".join(f"{key}: {value}" for key, value in sorted(report["decision_counts"].items())) or "없음"
    context = report.get("run_context")
    settings = '<h2>실행 당시 설정</h2>'
    if context is None:
        settings += '<p>이 결과에는 실행 설정 사본이 없습니다.</p>'
    else:
        settings += (f'<p>최대 실행 시간: {cell(context["seconds"])}초 / 프레임 제한: {cell(context["max_frames"])}</p>')
        if context["source_type"] == "SYNTHETIC":
            settings += '<p>합성 처리기 실행으로 카메라 번호·ROI·기준선을 사용하지 않았습니다.</p>'
        else:
            config = context["tracking_config"]
            settings += (f'<p>카메라 번호: {cell(context["camera_index"])} / 추적기: {cell(config["tracker"])}</p>'
                         f'<p>line_y: {cell(config["line_y"])} / line_x: {cell(config["line_x"])} / ROI: {cell(config["roi"])}</p>'
                         f'<p>설정 SHA-256: {cell(context["tracking_config_sha256"])}</p>')
    performance = report.get("performance")
    diagnostics = '<h2>처리 시간과 관찰 통계</h2>'
    deadline = report.get("deadline")
    if deadline is not None:
        diagnostics += (f'<p>읽기 전 시간 확인: {cell(deadline["checks"])}회 / 마지막 확인 경과: '
                        f'{cell(deadline["last_checked_elapsed_seconds"])}초 / 다음 읽기 전 시간 초과: '
                        f'{cell(deadline["expired_before_read"])}</p>')
    if performance is None:
        diagnostics += '<p>이 결과에는 처리 시간 측정값이 없습니다.</p>'
    else:
        diagnostics += ('<p>최대 수집 간격: ' + cell(performance["max_frame_gap_seconds"]) +
                        '초 / 1초 초과 간격: ' + cell(performance["frame_gaps_over_one_second"]) + '회</p><ul>')
        for name, label in (("read", "카메라 읽기"), ("process", "추적·OCR·후보 처리")):
            stage = performance["stages"][name]
            average = stage["total_seconds"] / stage["calls"] if stage["calls"] else None
            diagnostics += (f'<li>{label}: 호출 {cell(stage["calls"])}회 / 예외 {cell(stage["errors"])}회 / '
                            f'합계 {cell(stage["total_seconds"])}초 / 최대 {cell(stage["max_seconds"])}초 / '
                            f'평균 {cell(average) if average is not None else "측정 없음"}초</li>')
        diagnostics += '</ul><p>초기 모델 로딩을 포함할 수 있는 로컬 소요 시간입니다. 센서 지연이나 순수 모델 FPS가 아닙니다.</p>'
    statistics = report.get("processor_statistics")
    if statistics is not None:
        labels = {"frames": "관찰 검사 완료 프레임", "observations": "전체 관찰", "already_counted": "이미 통과한 ID 관찰",
                  "outside_roi": "ROI 밖 관찰", "eligible": "ROI 안 처리 대상 관찰", "gap_resets": "관찰 공백으로 crop 초기화",
                  "crossings": "통과 판정", "ocr_calls": "OCR 표본 처리 호출", "peak_buffer_bytes": "최대 crop 보관 바이트"}
        # 이전 결과에 없는 초기화 횟수를 0으로 추정하지 않습니다.
        for key, label in (("roi_resets", "ROI 이탈로 위치·crop 초기화"), ("speed_resets", "위치 점프로 위치·crop 초기화"),
                           ("expired_history_crops", "시각 기록 만료로 제외한 crop")):
            if key in statistics:
                labels[key] = label
        diagnostics += '<ul>' + ''.join(f'<li>{label}: {cell(statistics[key])}</li>' for key, label in labels.items()) + '</ul>'
        diagnostics += '<p>관찰 건수는 같은 차량의 반복 검출을 포함합니다. 실제 차량 정답 수가 아닙니다.</p>'
    # 2. 원본 OCR 표본이 없는 요약으로 정확도나 DB 반영 성공을 추정하지 않습니다.
    return ('<!doctype html><html lang="ko"><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>AI Vision 세션 보고서</title><style>body{font-family:sans-serif;margin:24px;line-height:1.5}'
            'dt{font-weight:bold}dd{margin-bottom:8px}table{border-collapse:collapse;white-space:nowrap}'
            'th,td{border:1px solid #aaa;padding:8px}.table{overflow:auto}</style>'
            '<h1>AI Vision 세션 보고서</h1><p>저장된 실행 요약입니다. 번호판 정확도와 실제 DB 반영을 입증하지 않습니다.'
            ' 자동 재전송 기능은 없습니다.</p><dl>' + details + '</dl><p>판정별 건수: ' + cell(counts) + '</p>'
            + settings + diagnostics + '<div class="table"><table><thead><tr>' + ''.join(f'<th>{cell(h)}</th>' for h in headers) +
            '</tr></thead><tbody>' + rows + '</tbody></table></div></html>')

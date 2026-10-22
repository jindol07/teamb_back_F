"""기존 화재 감지기를 실행하면서 사건 변화만 자동으로 HTTP 전송하는 선택적 실행기.

기본값은 네트워크 전송이 없는 DRY-RUN입니다. --send와 --allow-test-records,
--url을 함께 지정해야 실제 시험 API로 전송합니다. 기존 감지 코드는
--publish-alert-session으로 세션 식별 정보만 시작할 때 기록하도록 합니다.

실행 예:
  python -m ai_vision.safety.fire_alert_live --output ./results/demo \
      --send --allow-test-records --url http://127.0.0.1:8765/api/mock/fire-alerts \
      -- --video ./video.mp4 --fire-conf 0.30 --smoke-conf 0.30 --max-seconds 0
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import time
from pathlib import Path

from ai_vision.safety import fire_alert_sender as sender


# 1. 기존 JSON 계약을 그대로 재사용하여 사건 ID와 전송 ID를 일치시킵니다.
def load_live_payloads(output_dir: Path) -> list[dict]:
    """1-1. 감지 실행 중에는 alert_session.json, 종료 뒤에는 summary.json 사용."""
    folder = Path(output_dir)
    final_path = folder / "summary.json"
    session_path = folder / "alert_session.json"
    history_path = folder / "incident_history.json"
    if not history_path.is_file() or not (session_path.is_file() or final_path.is_file()):
        return []
    # 정상 종료 전후에 같은 started_at_utc를 사용하므로 transition_id가 보존됩니다.
    meta = sender._read_json_object(final_path if final_path.is_file() else session_path)
    history = sender._read_json_object(history_path)
    transitions = history.get("transitions")
    if not isinstance(transitions, list) or len(transitions) > sender.MAX_TRANSITIONS:
        raise ValueError("유효하지 않은 실시간 사건 목록입니다.")
    result, seen = [], set()
    for row in transitions:
        # 기존 송신기와 동일한 검증을 수행합니다. 잘못된 기록은 전송하지 않습니다.
        payload = sender._normalize_transition(row, meta)
        if payload["status"] not in sender.ACTIONABLE_STATUSES:
            continue
        key = payload["transition_id"]
        if key not in seen:
            result.append(payload)
            seen.add(key)
    return result


# 2. 새로운 이벤트만 미리보기/전송하고 성공한 이벤트는 체크포인트로 남깁니다.
def delivery_cycle(output_dir: Path, *, send: bool = False, url: str | None = None,
                   allow_test_records: bool = False, state_file: Path | None = None,
                   preview_ids: set | None = None, token: str | None = None,
                   timeout: float = 5.0, max_retries: int = 2,
                   post=sender.post_payload) -> dict:
    """2-1. 한 시점의 JSON 스냅샷을 읽어 새 상태 변화만 처리."""
    output_dir = Path(output_dir)
    payloads = load_live_payloads(output_dir)
    if not send:
        if preview_ids is None:
            raise ValueError("DRY-RUN에는 preview_ids 상태 집합이 필요합니다.")
        newly_seen = [p for p in payloads if p["transition_id"] not in preview_ids]
        if newly_seen:
            preview_ids.update(p["transition_id"] for p in newly_seen)
            sender._write_json_atomic(output_dir / "fire_alert_live_preview.json", {
                "schema_version": sender.SCHEMA_VERSION, "alerts": payloads,
            })
            for p in newly_seen:
                print(f"[알림 미리보기] {p['hazard_type']} {p['status']} | "
                      f"incident={p['incident_id'][:8]} | transition={p['transition_id'][:12]}", flush=True)
        return {"total": len(payloads), "new": len(newly_seen), "already": len(payloads) - len(newly_seen)}
    if not url:
        raise ValueError("실제 HTTP 전송에는 --url이 필요합니다.")
    sender.validate_endpoint(url)
    if any(p["is_test"] for p in payloads) and not allow_test_records:
        raise ValueError("시험 기록은 --allow-test-records가 필요합니다.")
    checkpoint = Path(state_file) if state_file else output_dir / "fire_alert_sent_state.json"
    outcome = sender.send_pending(payloads, url, state_file=checkpoint, token=token,
                                  timeout=timeout, max_retries=max_retries, post=post)
    if outcome["sent"]:
        print(f"[자동 전송] 신규 {outcome['sent']}건 | 이전 성공 {outcome['already_sent']}건", flush=True)
    return {"total": outcome["total"], "new": outcome["sent"], "already": outcome["already_sent"]}


# 3. subprocess는 기존 YOLO 실행기를 그대로 사용합니다.
def build_detector_command(output_dir: Path, detector_args: list[str]) -> list[str]:
    """3-1. 감지기의 출력 폴더를 고정해 사건과 체크포인트가 섞이지 않게 합니다."""
    if not detector_args:
        raise ValueError("-- 뒤에 --camera 또는 --video 등 감지기 인수를 입력하세요.")
    for arg in detector_args:
        if arg in ("--output", "--publish-alert-session") or arg.startswith("--output="):
            raise ValueError("--output/--publish-alert-session은 실행기가 지정하므로 뒤에 넣지 마세요.")
    return [sys.executable, "-m", "ai_vision.safety.live_fire_smoke",
            *detector_args, "--output", str(output_dir), "--publish-alert-session"]


def validate_new_output_folder(output_dir: Path) -> None:
    """3-2. 기존 결과를 덮어쓰거나 과거 사건을 새 사건으로 재전송하지 않습니다."""
    folder = Path(output_dir)
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        raise ValueError("--output은 존재하지 않거나 비어 있는 새 폴더여야 합니다.")


def run_launcher(output_dir: Path, detector_args: list[str], *, send=False, url=None,
                 allow_test_records=False, poll_seconds=0.25, token=None,
                 timeout=5.0, max_retries=2, state_file=None,
                 process_factory=subprocess.Popen, sleep=time.sleep) -> int:
    """3-3. 감지기와 송신기를 함께 실행하고 종료 후 남은 사건까지 처리합니다."""
    if type(poll_seconds) not in (int, float) or not math.isfinite(poll_seconds) or not 0.05 <= poll_seconds <= 30:
        raise ValueError("poll_seconds는 0.05~30초여야 합니다.")
    if send:
        if not url:
            raise ValueError("--send에는 --url이 필요합니다.")
        sender.validate_endpoint(url)
        if not allow_test_records:
            raise ValueError("이 감지기는 시험 기록을 만듭니다. --allow-test-records가 필요합니다.")
    if not (0 < timeout <= 60) or type(max_retries) is not int or not 0 <= max_retries <= 5:
        raise ValueError("timeout/max_retries 범위를 확인하세요.")
    validate_new_output_folder(output_dir)
    cmd = build_detector_command(output_dir, detector_args)
    output_dir.mkdir(parents=True, exist_ok=True)
    child = process_factory(cmd)
    preview_ids = set()
    new_alerts = 0
    last_error = None
    next_try = 0.0
    try:
        while child.poll() is None:
            if time.monotonic() >= next_try:
                try:
                    result = delivery_cycle(output_dir, send=send, url=url,
                                            allow_test_records=allow_test_records,
                                            state_file=state_file, preview_ids=preview_ids,
                                            token=token, timeout=timeout, max_retries=max_retries)
                    new_alerts += result["new"]
                    last_error = None
                except (ValueError, OSError, RuntimeError, UnicodeError) as exc:
                    # HTTP 장애 중에도 감지기를 중단하지 않습니다. 체크포인트 미기록 건은 재시도합니다.
                    last_error = str(exc)
                    print(f"[자동 알림 재시도 대기] {type(exc).__name__}: {exc}", flush=True)
                    next_try = time.monotonic() + 2.0
            sleep(poll_seconds)
        # 감지 종료 직후 기록된 전이도 모두 처리합니다.
        result = delivery_cycle(output_dir, send=send, url=url,
                                allow_test_records=allow_test_records,
                                state_file=state_file, preview_ids=preview_ids,
                                token=token, timeout=timeout, max_retries=max_retries)
        new_alerts += result["new"]
        if last_error and send and result["new"] == 0:
            print("[참고] 이전 네트워크 오류 이후 잔여 전송을 재확인했습니다.", flush=True)
        print(f"[자동 알림 완료] 신규 {new_alerts}건 | 결과 폴더: {output_dir}", flush=True)
        return 0 if child.returncode == 0 else 1
    except KeyboardInterrupt:
        print("[중단] 감지기를 종료합니다. 성공 기록은 보존됩니다.", flush=True)
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
        return 130
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


# 4. CLI

def main(argv=None) -> int:
    args_in = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="화재 감지 + 사건 발생 시 자동 HTTP 전송 (기본 DRY-RUN)")
    parser.add_argument("--output", type=Path, required=True, help="비어 있는 신규 결과 폴더")
    parser.add_argument("--send", action="store_true", help="자동 POST 요청 실행")
    parser.add_argument("--url", help="localhost 모의 서버 또는 HTTPS API")
    parser.add_argument("--allow-test-records", action="store_true", help="시험 데이터 전송 허용")
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--token-env", default="FIRE_ALERT_TOKEN")
    parser.add_argument("--state-file", type=Path)
    parser.epilog = "예: --output ./results/test --send --allow-test-records --url http://127.0.0.1:8765/api/mock/fire-alerts -- --video ./test.mp4 --max-seconds 0"
    if "--" not in args_in:
        parser.error("감지기 옵션 앞에 -- 구분자를 추가해 주세요.")
    delimiter = args_in.index("--")
    options = parser.parse_args(args_in[:delimiter])
    detector_args = args_in[delimiter + 1:]
    token = os.environ.get(options.token_env) or None
    try:
        return run_launcher(options.output, detector_args, send=options.send,
                            url=options.url, allow_test_records=options.allow_test_records,
                            poll_seconds=options.poll_seconds, timeout=options.timeout,
                            max_retries=options.max_retries, token=token,
                            state_file=options.state_file)
    except (ValueError, OSError, RuntimeError, UnicodeError) as exc:
        print(f"[실패] {type(exc).__name__}: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

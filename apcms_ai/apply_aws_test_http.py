"""AI Vision 시험용 AWS HTTP 허용 패치.

기존 fire_alert_sender.py 전체를 덮어쓰지 않고, 정확히 한 조건식만 수정합니다.
기존 파일은 프로젝트의 ai_vision/results/safety/patch_backups/에 백업합니다.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

TARGET_URL = "http://52.79.133.132:3000/admin-api/api/parking/ai/fire-alerts"
PATCH_MARKER = "_allow_explicit_apcms_aws_test_http"

# 최신 GitHub develop 원본뿐 아니라 주석 보완된 로컬본에도 동일한 조건식 사용.
ORIGINAL = 'if parsed.scheme == "http" and parsed.hostname.lower() not in ("localhost", "127.0.0.1", "::1"):'
REPLACED = 'if parsed.scheme == "http" and parsed.hostname.lower() not in ("localhost", "127.0.0.1", "::1") and not _allow_explicit_apcms_aws_test_http(url):'
HELPER = '''# APCMS 팀 AWS 시험용 HTTP 예외. 다른 외부 HTTP/운영 이벤트에는 적용하지 않습니다.
_APCMS_AWS_TEST_HTTP_URL = "http://52.79.133.132:3000/admin-api/api/parking/ai/fire-alerts"


def _allow_explicit_apcms_aws_test_http(url: str) -> bool:
    """환경변수 명시 승인 + 시험 모드 + 정확한 목적지 URL 세 조건 모두 충족."""
    return (
        os.environ.get("SAFETY_TEST_AWS_HTTP", "").strip() == "1"
        and os.environ.get("SAFETY_CAMERA_SEND_MODE", "test").strip().lower() == "test"
        and url == _APCMS_AWS_TEST_HTTP_URL
    )


'''


def patch_text(original: str) -> str:
    if PATCH_MARKER in original:
        if REPLACED not in original or original.count(REPLACED) != 1:
            raise ValueError("부분 적용 또는 다른 코드가 감지되었습니다. 원본을 확인하세요.")
        return original
    if original.count(ORIGINAL) != 1:
        raise ValueError("기존 HTTP 검사 구문을 정확히 찾지 못했습니다. 로컬 소스와 맞는지 확인하세요.")
    if not re.search(r"^import os\s*$", original, flags=re.MULTILINE):
        raise ValueError("fire_alert_sender.py에서 import os를 찾지 못했습니다.")
    if original.count("def validate_endpoint(url: str) -> str:") != 1:
        raise ValueError("기존 validate_endpoint 함수를 확인할 수 없습니다.")
    eol = "\r\n" if "\r\n" in original else "\n"
    updated = original.replace(ORIGINAL, REPLACED, 1)
    anchor = "def validate_endpoint(url: str) -> str:" + eol
    if anchor not in updated:
        raise ValueError("validate_endpoint 선언 끝의 줄바꿈 형식이 예상과 다릅니다.")
    updated = updated.replace(anchor, HELPER.replace("\n", eol) + anchor, 1)
    ast.parse(updated)
    return updated


def apply(project: Path, *, check: bool = False) -> int:
    project = project.resolve()
    target = project / "ai_vision" / "safety" / "fire_alert_sender.py"
    if not target.is_file():
        print(f"[오류] 원본 파일을 찾지 못했습니다: {target}", file=sys.stderr)
        return 1
    with target.open("r", encoding="utf-8", newline="") as stream:
        original = stream.read()
    try:
        updated = patch_text(original)
    except (ValueError, SyntaxError) as exc:
        print(f"[오류] 자동 패치 중지: {exc}", file=sys.stderr)
        return 1
    if updated == original:
        print("[확인] 이미 적용된 상태입니다. 파일을 다시 수정하지 않았습니다.")
        return 0
    if check:
        print("[확인] 원본 코드가 패치와 호환됩니다. --check를 해제하면 적용됩니다.")
        return 0

    backup_dir = project / "ai_vision" / "results" / "safety" / "patch_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"fire_alert_sender_{datetime.now():%Y%m%d_%H%M%S_%f}.py.bak"
    shutil.copy2(target, backup)
    try:
        with target.open("w", encoding="utf-8", newline="") as stream:
            stream.write(updated)
    except BaseException:
        shutil.copy2(backup, target)
        raise
    print(f"[적용 완료] {target}")
    print(f"[원본 백업] {backup}")
    print("[정책] 기본은 외부 HTTP 차단 / 명시적인 팀 AWS 시험 URL만 예외 / 운영은 HTTPS 필수")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="팀 AWS 시험용 HTTP 허용 설정 (원본 백업 후 최소 수정)")
    ap.add_argument("--project", type=Path, default=Path.cwd(), help="apcms_ai 프로젝트 루트")
    ap.add_argument("--check", action="store_true", help="적용하지 않고 호환성만 확인")
    options = ap.parse_args()
    raise SystemExit(apply(options.project, check=options.check))

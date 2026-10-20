# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/asyncio_runtime_check.py

"""API 검사 전에 비동기 런타임 초기화가 가능한지 제한 시간 안에 확인합니다."""

import subprocess
import sys


PROBE = """
import asyncio
import socket
socket.setdefaulttimeout(1)
asyncio.run(asyncio.sleep(0))
print('ASYNCIO_RUNTIME_OK')
"""


def ensure_asyncio_runtime():
    # 1. 별도 프로세스에서 검사해 소켓 기본값·이벤트 루프를 본 테스트와 분리합니다.
    try:
        completed = subprocess.run([sys.executable, "-I", "-c", PROBE],
                                   capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("ASYNCIO_RUNTIME_UNAVAILABLE: 비동기 런타임 초기화에 실패했습니다. "
                           "로컬 루프백 통신이 허용된 실행 환경에서 같은 테스트를 실행하세요.") from error
    # 2. 환경 문제를 테스트 성공·건너뛰기로 처리하지 않고 즉시 오류로 알려 줍니다.
    if completed.returncode != 0 or completed.stdout.strip() != "ASYNCIO_RUNTIME_OK":
        raise RuntimeError("ASYNCIO_RUNTIME_UNAVAILABLE: Python 이벤트 루프를 만들 수 없습니다. "
                           "Windows 내부 소켓의 루프백 통신 권한을 확인하세요. "
                           "FastAPI API 검사는 실행되지 않았습니다.")

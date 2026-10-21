# D:/finalProjectB/back/apcms_ai/ai_vision/camera_runtime.py

"""운영체제에 맞는 카메라 연결과 GUI 실행 조건을 제공합니다."""

import os
import sys


def release_resources(*resources):
    # 1. 한 자원의 해제가 실패해도 나머지는 정리하고, 처리 중 발생한 원래 예외는 유지합니다.
    failures = 0
    for resource in resources:
        if resource is not None:
            try:
                resource.release()
            except Exception:
                failures += 1
    if failures and sys.exception() is None:
        raise OSError("카메라·영상 저장기 해제에 실패했습니다.")
    return failures


def open_camera(index):
    import cv2
    # 1. DirectShow는 Windows에서만 지정하고 Linux에서는 OpenCV 자동 선택을 사용합니다.
    return cv2.VideoCapture(index, cv2.CAP_DSHOW) if sys.platform == "win32" else cv2.VideoCapture(index)


def require_display():
    # 2. Linux의 창 생성은 Qt가 프로세스를 강제 종료할 수 있어 호출 전에 차단합니다.
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise RuntimeError("화면 없는 환경에서는 GUI 도구를 실행할 수 없습니다. 녹화는 --no-preview를 사용하세요.")
    import cv2
    for line in cv2.getBuildInformation().splitlines():
        if line.strip().startswith("GUI:") and line.split(":", 1)[1].strip() == "NONE":
            raise RuntimeError("현재 OpenCV는 GUI를 지원하지 않습니다. 녹화는 --no-preview를 사용하세요.")

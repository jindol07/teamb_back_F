# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/probe_runtime_imports.py

"""별도 프로세스에서 패키지 import 성공 여부를 확인합니다."""

import argparse
import json
import subprocess
import sys


PROFILES = {
    "api": ("fastapi", "starlette", "httpx", "uvicorn", "multipart", "PIL", "numpy", "cv2"),
    "vision": ("numpy", "cv2", "torch", "ultralytics", "lap"),
    "ocr": ("paddle", "paddleocr"),
}
MARKER = "VISION_IMPORT_OK"


def probe_imports(profile="api", timeout=30, runner=None):
    if profile not in PROFILES or type(timeout) not in (int, float) or not 1 <= timeout <= 300:
        raise ValueError("점검 분야와 제한 시간(1~300초)을 확인해 주세요.")
    runner = subprocess.run if runner is None else runner
    checks = []
    # 1. 한 패키지의 충돌·정지가 다음 점검에 영향을 주지 않도록 프로세스를 나눕니다.
    for module in PROFILES[profile]:
        script = f"import importlib; importlib.import_module({module!r}); print({MARKER!r})"
        try:
            result = runner([sys.executable, "-I", "-c", script], capture_output=True,
                            text=True, errors="replace", timeout=timeout)
            ok = result.returncode == 0 and MARKER in result.stdout.splitlines()
            status = "IMPORTED" if ok else "FAILED"
        except subprocess.TimeoutExpired:
            status = "TIMEOUT"
        except OSError:
            status = "PROCESS_ERROR"
        # 2. 외부 패키지 출력에 경로·환경 정보가 섞일 수 있어 원문은 보고서에 넣지 않습니다.
        checks.append({"module": module, "status": status})
    return {"record_type": "VISION_IMPORT_PROBE", "profile": profile,
            "status": "PASSED" if all(row["status"] == "IMPORTED" for row in checks) else "FAILED",
            "checks": checks, "scope": "IMPORT_ONLY"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(PROFILES), default="api")
    parser.add_argument("--timeout", type=float, default=30, help="패키지 하나당 제한 시간(초)")
    args = parser.parse_args(argv)
    try:
        report = probe_imports(args.profile, args.timeout)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

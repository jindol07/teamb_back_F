# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_preflight.py

"""실시간 실행 전 설정·파일 점검과 선택적인 카메라 확인을 묶습니다."""

from ai_vision.recognition.live_gate_environment import check_environment
from ai_vision.recognition.live_gate_camera_probe import probe_camera
from ai_vision.recognition.local_io import read_json
from ai_vision.recognition.tracking_config import validate_config
from ai_vision.recognition.vehicle_contract import validate_camera_id
from ai_vision.recognition.probe_runtime_imports import probe_imports


def run_preflight(config_path, camera_id, down_direction, camera_index=0, probe=False,
                  environment_checker=None, camera_checker=None, *,
                  check_imports=False, import_timeout=30, import_checker=None):
    validate_camera_id(camera_id)
    if down_direction not in {"ENTRY", "EXIT"}:
        raise ValueError("DOWN 방향은 ENTRY 또는 EXIT여야 합니다.")
    if type(camera_index) is not int or not 0 <= camera_index <= 32 or type(probe) is not bool:
        raise ValueError("카메라 번호·점검 옵션이 올바르지 않습니다.")
    if (type(check_imports) is not bool or type(import_timeout) not in (int, float)
            or not 1 <= import_timeout <= 300):
        raise ValueError("import 점검 옵션·제한 시간(1~300초)을 확인해 주세요.")
    # 1. 잘못된 설정은 카메라를 열기 전에 차단합니다.
    config = validate_config(read_json(config_path))
    environment = (check_environment if environment_checker is None else environment_checker)()
    missing = [item["name"] for item in environment if item["status"] != "FOUND"]
    camera = {"status": "NOT_CHECKED", "camera_index": camera_index}
    # 2. 선택한 경우에만 외부 패키지를 불러옵니다. 설치 누락 시 무거운 점검은 생략합니다.
    imports = {"status": "NOT_CHECKED", "reports": []}
    if check_imports:
        imports["status"] = "SKIPPED_MISSING_ENVIRONMENT"
        if not missing:
            checker = probe_imports if import_checker is None else import_checker
            imports["reports"] = [checker(profile, import_timeout) for profile in ("vision", "ocr")]
            imports["status"] = ("PASSED" if all(item["status"] == "PASSED"
                                               for item in imports["reports"]) else "FAILED")
    imports_failed = imports["status"] == "FAILED"
    # 2. 파일 점검에서 문제가 있으면 요청된 카메라 점검도 건너뜁니다.
    if probe and not missing and not imports_failed:
        camera = (probe_camera if camera_checker is None else camera_checker)(camera_index)
    blocked = bool(missing) or imports_failed or camera["status"] == "FAILED"
    return {"record_type": "LIVE_GATE_PREFLIGHT", "status": "BLOCKED" if blocked else "CHECKED",
            "camera_id": camera_id, "down_direction": down_direction, "config": config,
            "environment": environment, "missing_items": missing, "camera": camera,
            "imports": imports, "import_probe_requested": check_imports,
            "camera_probe_requested": probe, "http_enabled": False,
            "unverified": ["PACKAGE_IMPORT_AND_COMPATIBILITY", "MODEL_LOADING_AND_INTEGRITY",
                           "PADDLE_OCR_CACHE_AND_INFERENCE", "ROI_AND_DIRECTION_IN_REAL_SCENE",
                           "KOREAN_MOVING_PLATE_ACCURACY", "BOOT_AND_DATABASE_INTEGRATION"]}

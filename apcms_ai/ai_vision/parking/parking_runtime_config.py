"""주차 자동 실행 설정. 비활성 상태에서는 파일·모델을 읽지 않습니다."""
import os
from pathlib import Path
from urllib.parse import urlsplit


def load_runtime_config(environment, *, check_safety=True):
    flag = environment.get("PARKING_RUNTIME_ENABLED", "false")
    if not isinstance(flag, str) or flag.lower() not in ("true", "false"):
        raise ValueError("PARKING_RUNTIME_ENABLED는 true/false로 지정하세요.")
    if flag.lower() == "false":
        return None
    path = Path(environment.get("PARKING_RUNTIME_CONFIG", ""))
    if not path.is_file():
        raise ValueError("운영 주차 설정 파일이 필요합니다.")
    from ai_vision.recognition.local_io import read_json
    config = read_json(path, max_bytes=65536)
    required = {"gate_camera", "parking_camera", "gate_id", "parking_id", "down_direction",
                "gate_config", "spaces_config", "reference", "allowed_codes", "boot_context_url", "output_dir"}
    if not isinstance(config, dict) or not required <= set(config) <= required | {"delivery_enabled", "preview"}:
        raise ValueError("운영 주차 설정 항목을 확인하세요.")
    config.setdefault("preview", False)
    if type(config["preview"]) is not bool:
        raise ValueError("preview는 명시적인 true/false여야 합니다.")
    config.setdefault("delivery_enabled", False)
    if type(config["delivery_enabled"]) is not bool:
        raise ValueError("delivery_enabled는 명시적인 true/false여야 합니다.")
    for key in ("gate_camera", "parking_camera"):
        if type(config[key]) is not int or not 0 <= config[key] <= 32:
            raise ValueError("현재 운영 연결은 로컬 카메라 정수 번호 0~32를 지원합니다.")
    if config["gate_camera"] == config["parking_camera"]:
        raise ValueError("A와 B 카메라는 달라야 합니다.")
    # 2. 화재 담당의 기본 활성화 규칙과 동일하게 장치 충돌을 사전에 확인합니다.
    safety_default = os.name == "nt" and environment.get("APP_ENV", "development").lower() == "development"
    raw_safety = environment.get("SAFETY_CAMERA_AUTOSTART", str(safety_default)).strip().lower()
    if raw_safety not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
        raise ValueError("화재 자동감시 활성화 설정을 확인하세요.")
    if check_safety and raw_safety in ("true", "1", "yes", "on"):
        safety_index = int(environment.get("SAFETY_CAMERA_INDEX", "0"))
        if safety_index in (config["gate_camera"], config["parking_camera"]):
            raise ValueError("화재·주차 카메라가 겹칩니다. 같은 장치를 동시에 열 수 없습니다.")
    from ai_vision.recognition.vehicle_contract import validate_camera_id
    for key in ("gate_id", "parking_id"):
        validate_camera_id(config[key])
    if config["gate_id"] == config["parking_id"] or config["down_direction"] not in ("ENTRY", "EXIT"):
        raise ValueError("카메라 ID·입차 방향을 확인하세요.")
    url = urlsplit(config["boot_context_url"])
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Boot 주소 형식이 잘못됐습니다.")
    from ai_vision.recognition.tracking_config import validate_config
    from ai_vision.parking.parking_calibration import load_reference
    for key in ("gate_config", "spaces_config", "reference", "output_dir"):
        if not isinstance(config[key], str) or not config[key]:
            raise ValueError("운영 파일 경로가 필요합니다.")
        config[key] = str((path.parent / config[key]).resolve())
    validate_config(read_json(config["gate_config"]))
    spaces = read_json(config["spaces_config"])
    load_reference(config["reference"], spaces)
    from ai_vision.parking.parking_delivery import delivery_settings
    if not isinstance(config["allowed_codes"], list) or not all(isinstance(c,str) for c in config["allowed_codes"]):
        raise ValueError("허용 구획 목록이 필요합니다.")
    # 1. 점유와 입출차는 동일 Boot·키를 사용하며 임시 구획은 허용하지 않습니다.
    if any(c.startswith("999F-") for c in config["allowed_codes"]):
        raise ValueError("운영 모드에서는 임시 시험 구획을 사용하지 않습니다.")
    # 4. 관찰 모드는 인증키를 요구하거나 실제 송신 객체를 만들지 않습니다.
    if not config["delivery_enabled"]:
        from ai_vision.parking.parking_event_sender import convert_space_code
        configured = {convert_space_code(row['id']) for row in spaces['spaces']}
        if not config["allowed_codes"] or not set(config["allowed_codes"]) <= configured:
            raise ValueError("허용 구획과 좌표가 일치하지 않습니다.")
        return config
    env = dict(environment, PARKING_AI_BASE_URL=config["boot_context_url"])
    if env.get("PARKING_AI_API_URL"):
        raise ValueError("운영 모드에서는 개별 점유 URL을 재정의하지 않습니다.")
    delivery_settings(spaces, True, config["allowed_codes"], env)
    from ai_vision.parking.parking_event_sender import _configured_api_key
    from ai_vision.recognition.vehicle_http import VehicleHTTPClient
    VehicleHTTPClient(context_url=config["boot_context_url"], api_key=_configured_api_key(env), enabled=True)
    return config


def main(argv=None):
    """파일·설정만 검사하며 서버·카메라·전송 작업을 시작하지 않습니다."""
    import argparse
    from dotenv import dotenv_values
    from ai_vision.paths import BASE_DIR
    parser = argparse.ArgumentParser(description="주차 운영 설정 사전검사: 카메라·HTTP·DB 실행 없음")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--parking-only", action="store_true", help="화재 라우터가 없는 Vision 전용 서버용 검사")
    args = parser.parse_args(argv)
    # 3. 사용자 설정 파일·터미널 환경을 덮어쓰지 않는 별도 검사입니다.
    env = {**dotenv_values(BASE_DIR.parent/".env", encoding="utf-8-sig", interpolate=False), **os.environ,
           "PARKING_RUNTIME_ENABLED":"true", "PARKING_RUNTIME_CONFIG":str(args.config)}
    try:
        config = load_runtime_config(env, check_safety=not args.parking_only)
    except (ValueError, OSError, TypeError) as error:
        print("PRECHECK_BLOCKED: " + (str(error) if isinstance(error, ValueError) else type(error).__name__))
        return 1
    print(f"PRECHECK_OK: A={config['gate_camera']} B={config['parking_camera']} / 허용 구획 {len(config['allowed_codes'])}개 / 전송={config.get('delivery_enabled', False)}")
    print("카메라·서버·HTTP·DB 작업 없음. 실제 구도·DB 구획·예약은 별도 확인이 필요합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

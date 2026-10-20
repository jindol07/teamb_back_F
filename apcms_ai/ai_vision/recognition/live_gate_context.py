# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_context.py

"""실제 사용한 추적 설정과 실행 제한을 독립적인 사본으로 보존합니다."""

import hashlib
import json
import math

from ai_vision.recognition.tracking_config import validate_config


def build_run_context(config, camera_index, seconds=20, max_frames=100000, synthetic=False):
    if (type(synthetic) is not bool or isinstance(seconds, bool) or
            not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 < seconds <= 300 or
            type(max_frames) is not int or not 1 <= max_frames <= 100000):
        raise ValueError("실행 설정의 시간·프레임 제한이 올바르지 않습니다.")
    # 1. 합성 예시에 실제 카메라 설정을 사용한 것처럼 기록하지 않습니다.
    snapshot, fingerprint = None, None
    if synthetic:
        if config is not None or camera_index is not None:
            raise ValueError("합성 예시에는 카메라 번호·추적 설정을 기록하지 않습니다.")
    else:
        if type(camera_index) is not int or not 0 <= camera_index <= 32:
            raise ValueError("카메라 번호는 0~32 정수여야 합니다.")
        checked = validate_config(config)
        # 2. 원본 목록을 공유하지 않고 숫자 표현을 통일해 설정 내용의 해시를 계산합니다.
        snapshot = {"tracker": checked["tracker"], "line_y": float(checked["line_y"]),
                    "line_x": list(map(float, checked["line_x"])), "roi": list(map(float, checked["roi"]))}
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        fingerprint = hashlib.sha256(encoded).hexdigest()
    return {"version": 1, "source_type": "SYNTHETIC" if synthetic else "CAMERA",
            "camera_index": camera_index, "seconds": float(seconds), "max_frames": max_frames,
            "tracking_config": snapshot, "tracking_config_sha256": fingerprint}


def validate_run_context(value, synthetic):
    keys = {"version", "source_type", "camera_index", "seconds", "max_frames",
            "tracking_config", "tracking_config_sha256"}
    if not isinstance(value, dict) or set(value) != keys or type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("실행 설정 사본의 형식이 올바르지 않습니다.")
    expected = build_run_context(value["tracking_config"], value["camera_index"], value["seconds"],
                                 value["max_frames"], synthetic)
    # 3. 해시는 저장 내용의 일치 검사이며 서명이나 변조 방지 보장은 아닙니다.
    if value != expected:
        raise ValueError("실행 출처·추적 설정 해시가 일치하지 않습니다.")
    return expected

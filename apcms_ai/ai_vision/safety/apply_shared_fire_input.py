"""주차 프레임 공유 입력 모드를 AI Vision 화재 감지기 하나에 최소 패치합니다.

현 로컬 코드가 예상된 구문과 다르면 수정하지 않습니다. 작업 중 다른 기능의
소스 코드를 덮어쓰지 않고, 백업과 동일 적용 판별을 지원합니다.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime
import os
from pathlib import Path
import shutil
import tempfile

MARKER = "SAFETY_SHARED_FRAME_INPUT_V1"
TARGET = Path("ai_vision/safety/live_fire_smoke.py")
NEW_FILES = (
    Path("ai_vision/safety/shared_frame_source.py"),
    Path("ai_vision/tests/safety/test_shared_frame_source.py"),
)


def replace_one(text: str, needle: str, replacement: str, label: str) -> str:
    if text.count(needle) != 1:
        raise ValueError(f"{label}: 예상한 소스 구문이 정확히 한 번 나타나지 않습니다. 덮어쓰지 않습니다.")
    return text.replace(needle, replacement, 1)


def patch_live(text: str) -> str:
    if MARKER in text:
        if text.count(MARKER) != 1 or 'source.add_argument("--shared-run-dir"' not in text:
            raise ValueError("부분 적용 또는 다른 공유 프레임 구현 흔적이 있습니다.")
        return text
    text = replace_one(text,
        "    video_path: str | None = None\n",
        "    video_path: str | None = None\n"
        "    # " + MARKER + ": 주차 A/B 공유 프레임. 직접 카메라를 열지 않습니다.\n"
        "    shared_run_dir: Path | None = None\n"
        "    shared_role: str | None = None\n"
        "    shared_camera_id: str | None = None\n"
        "    shared_max_age: float = 3.0\n"
        "    shared_max_silence: float = 12.0\n", "LiveConfig 입력 필드")
    text = replace_one(text,
        '        for name in ("interval", "max_seconds", "cooldown"):\n',
        '        if self.shared_run_dir is not None:\n'
        '            if self.video_path is not None or self.shared_role not in ("gate", "parking"):\n'
        '                raise ValueError("공유 입력에서는 --video 대신 role=gate/parking을 지정하세요.")\n'
        '            if (not isinstance(self.shared_camera_id, str) or not self.shared_camera_id.strip()\n'
        '                    or len(self.shared_camera_id) > 128):\n'
        '                raise ValueError("공유 입력에는 예상 논리 camera_id가 필요합니다.")\n'
        '            for key in ("shared_max_age", "shared_max_silence"):\n'
        '                val = getattr(self, key)\n'
        '                if type(val) not in (int, float) or not math.isfinite(val) or val <= 0:\n'
        '                    raise ValueError(f"{key}는 양의 유한한 시간(초)이어야 합니다.")\n'
        '            if self.shared_max_silence <= self.shared_max_age:\n'
        '                raise ValueError("공유 입력 대기시간은 프레임 만료시간보다 길어야 합니다.")\n'
        '        elif self.shared_role is not None or self.shared_camera_id is not None:\n'
        '            raise ValueError("공유 프레임 설정에는 shared_run_dir가 필요합니다.")\n'
        '        for name in ("interval", "max_seconds", "cooldown"):\n', "LiveConfig 검증")
    text = replace_one(text,
        '    factory = cv2.VideoCapture if capture_factory is None else capture_factory\n',
        '    # 공유 모드에서는 VideoCapture를 생성하지 않고 제공받은 원본 프레임만 읽습니다.\n'
        '    factory = cv2.VideoCapture if capture_factory is None else capture_factory\n', "기존 카메라 입력 유지")
    text = replace_one(text,
        '    def open_source():\n        nonlocal capture, capture_open_attempts, camera_reconnect_attempts\n',
        '    def open_source():\n        nonlocal capture, capture_open_attempts, camera_reconnect_attempts\n'
        '        if config.shared_run_dir is not None:\n'
        '            from ai_vision.safety.shared_frame_source import SharedFrameCapture\n'
        '            capture = SharedFrameCapture(config.shared_run_dir, config.shared_role,\n'
        '                config.shared_camera_id, max_age=config.shared_max_age,\n'
        '                max_silence=config.shared_max_silence)\n'
        '            return capture.isOpened()\n', "공유 입력 생성")
    text = replace_one(text,
        '    started_utc = datetime.now(timezone.utc).isoformat()\n',
        '    started_utc = datetime.now(timezone.utc).isoformat()\n'
        '    input_name = (f"{config.shared_role}:{config.shared_camera_id}"\n'
        '                  if config.shared_run_dir is not None else\n'
        '                  (Path(config.video_path).name if config.video_path else f"camera_{config.camera_index}"))\n',
        "입력 출처 식별")
    text = replace_one(text,
        '\n            "source_name": Path(config.video_path).name if config.video_path else f"camera_{config.camera_index}",',
        '\n            "source_name": input_name,', "송신용 세션 출처")
    text = replace_one(text,
        '            status = "VIDEO_OPEN_FAILED" if config.video_path else "CAMERA_OPEN_FAILED"\n',
        '            status = ("SHARED_INPUT_UNAVAILABLE" if config.shared_run_dir is not None else\n'
        '                      ("VIDEO_OPEN_FAILED" if config.video_path else "CAMERA_OPEN_FAILED"))\n', "소스 시작 실패")
    text = replace_one(text,
        '                    camera_read_failures += 1\n                    record_health("CAMERA_READ_FAILED")\n',
        '                    if config.shared_run_dir is not None:\n'
        '                        # 입력 만료/CLOSED/손상 시 과거 프레임을 재사용하지 않고 사건을 종료.\n'
        '                        # 주차 카메라 장치 재연결은 시도하지 않습니다.\n'
        '                        status = "SHARED_INPUT_UNAVAILABLE"\n'
        '                        record_health("SHARED_INPUT_" + (capture.last_reason or "UNAVAILABLE"))\n'
        '                        break\n'
        '                    camera_read_failures += 1\n                    record_health("CAMERA_READ_FAILED")\n',
        "공유 프레임 중단 시 안전 종료")
    text = replace_one(text,
        '\n                "source_name": Path(config.video_path).name if config.video_path else f"camera_{config.camera_index}",',
        '\n                "source_name": input_name,', "결과 요약 출처")
    text = replace_one(text,
        '    source.add_argument("--video", type=str, help="MP4 등 영상 파일 경로")\n',
        '    source.add_argument("--video", type=str, help="MP4 등 영상 파일 경로")\n'
        '    source.add_argument("--shared-run-dir", type=Path, help="주차 최신 프레임 실행 폴더(run_id). 카메라 재오픈 없음")\n'
        '    parser.add_argument("--shared-role", choices=("gate", "parking"))\n'
        '    parser.add_argument("--shared-camera-id", help="주차 설정의 gate_id 또는 parking_id")\n'
        '    parser.add_argument("--shared-max-age", type=float, default=3.0)\n'
        '    parser.add_argument("--shared-max-silence", type=float, default=12.0)\n',
        "CLI 공유 입력 옵션")
    text = replace_one(text,
        '    config = LiveConfig(camera_index=args.camera, video_path=args.video, interval=args.interval,\n',
        '    config = LiveConfig(camera_index=args.camera, video_path=args.video, interval=args.interval,\n'
        '                        shared_run_dir=args.shared_run_dir, shared_role=args.shared_role,\n'
        '                        shared_camera_id=args.shared_camera_id, shared_max_age=args.shared_max_age,\n'
        '                        shared_max_silence=args.shared_max_silence,\n',
        "CLI와 실행 설정 연결")
    text = replace_one(text,
        '"VIDEO_OPEN_FAILED", "VIDEO_READ_FAILED") else 1\n',
        '"VIDEO_OPEN_FAILED", "VIDEO_READ_FAILED", "SHARED_INPUT_UNAVAILABLE") else 1\n',
        "공유 입력 실패 종료 코드")
    ast.parse(text)
    return text


def apply(root: Path, bundle: Path, dry_run: bool) -> None:
    target = root / TARGET
    with target.open("r", encoding="utf-8-sig", newline="") as f:
        original = f.read()
    newline = "\r\n" if "\r\n" in original else "\n"
    patched = patch_live(original.replace("\r\n", "\n")).replace("\n", newline)
    to_copy = []
    for rel in NEW_FILES:
        src, dst = bundle / rel, root / rel
        if not src.is_file():
            raise FileNotFoundError(src)
        if dst.exists():
            if not dst.is_file() or src.read_bytes() != dst.read_bytes():
                raise ValueError(f"기존 파일과 충돌하므로 중단합니다: {dst}")
        else:
            to_copy.append((src, dst))
    # 공유 주차 송신 코드가 현재 로컬에 없는 경우, 패치 자체는 가능하더라도
    # 실제 실행은 불가능하므로 명시적으로 미배포 상황을 알립니다.
    parking_source = root / "ai_vision/parking/frame_exchange.py"
    print(f"[{'준비됨' if parking_source.is_file() else '주의: 미존재'}] 주차 수신 API: {parking_source}")
    print(f"[{'변경' if patched != original else '이미 적용'}] {TARGET}")
    for _, dst in to_copy:
        print(f"[추가 예정] {dst.relative_to(root)}")
    if dry_run:
        print("[사전검사 완료] 소스 변경 없음")
        return
    backup = root / "ai_vision/results/safety/patch_backups" / f"shared_frame_{datetime.now():%Y%m%d_%H%M%S_%f}"
    modified = patched != original
    backup_src = backup / TARGET
    written, replaced = [], False
    try:
        if modified:
            backup_src.parent.mkdir(parents=True, exist_ok=False)
            shutil.copy2(target, backup_src)
            tmp = None
            try:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=target.parent,
                                                 prefix=".shared-frame-", suffix=".tmp", delete=False) as f:
                    tmp = Path(f.name)
                    f.write(patched)
                os.replace(tmp, target)
                replaced = True
            finally:
                if tmp is not None and tmp.exists():
                    tmp.unlink()
        for src, dst in to_copy:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            written.append(dst)
    except Exception:
        for dst in written:
            dst.unlink(missing_ok=True)
        if replaced:
            shutil.copy2(backup_src, target)
        raise
    print(f"[완료] 기존 파일 {int(modified)}개 최소 변경, 새 파일 {len(written)}개 추가")
    if modified:
        print(f"[백업] {backup}")
    if not parking_source.is_file():
        print("[시연 보류] 주차 프레임 공유 모듈이 아직 로컬에 없습니다. 코덱스 구현 반영 후 실행하세요.")


def main():
    p = argparse.ArgumentParser(description="화재 AI에 주차 A/B 원본 프레임 입력 추가")
    p.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent)
    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--apply", action="store_true")
    args = p.parse_args()
    apply(args.project_root.resolve(), Path(__file__).resolve().parent / "new_files", args.check)

if __name__ == "__main__":
    main()

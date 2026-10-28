"""간단한 합성 소스에서 안전한 부분 패치와 재적용 방지를 검사."""
import unittest
from apply_shared_fire_input import patch_live

# 대상의 각 변경 지점은 현재 develop(2026-10-27)와 동일한 줄을 사용합니다.
# 전체 실제 소스 대상 검증은 사용자의 --check로 수행합니다.
FAKE_SOURCE = '''from pathlib import Path
class LiveConfig:
    video_path: str | None = None
    def __post_init__(self):
        for name in ("interval", "max_seconds", "cooldown"):
            pass

def run_live(config, capture_factory=None):
    factory = cv2.VideoCapture if capture_factory is None else capture_factory
    started_utc = datetime.now(timezone.utc).isoformat()
    write_json_atomic(output_dir / "alert_session.json", {
            "source_name": Path(config.video_path).name if config.video_path else f"camera_{config.camera_index}",
    })
    def open_source():
        nonlocal capture, capture_open_attempts, camera_reconnect_attempts
        for attempt in range(config.camera_retries + 1 if config.video_path is None else 1):
            pass
    if not open_source():
            status = "VIDEO_OPEN_FAILED" if config.video_path else "CAMERA_OPEN_FAILED"
    if True:
                    camera_read_failures += 1
                    record_health("CAMERA_READ_FAILED")
    summary = {
                "source_name": Path(config.video_path).name if config.video_path else f"camera_{config.camera_index}",
    }

def main(argv=None):
    source.add_argument("--video", type=str, help="MP4 등 영상 파일 경로")
    config = LiveConfig(camera_index=args.camera, video_path=args.video, interval=args.interval,
                        conf=args.conf)
    return 0 if report["status"] not in ("ERROR", "CAMERA_READ_FAILED", "CAMERA_OPEN_FAILED", "VIDEO_OPEN_FAILED", "VIDEO_READ_FAILED") else 1
'''

class SafetyPatchTests(unittest.TestCase):
    def test_patch_and_rerun(self):
        after = patch_live(FAKE_SOURCE)
        self.assertIn('"SHARED_INPUT_UNAVAILABLE"', after)
        self.assertIn('source.add_argument("--shared-run-dir"', after)
        self.assertEqual(after.count("SAFETY_SHARED_FRAME_INPUT_V1"), 1)
        self.assertEqual(after, patch_live(after))

    def test_unexpected_source_refused(self):
        with self.assertRaisesRegex(ValueError, '예상한 소스 구문'):
            patch_live(FAKE_SOURCE.replace('    video_path: str | None = None\n', ''))

    def test_invalid_partial_marker_refused(self):
        with self.assertRaisesRegex(ValueError, '부분 적용'):
            patch_live(FAKE_SOURCE + '\n# SAFETY_SHARED_FRAME_INPUT_V1\n')

if __name__ == '__main__':
    unittest.main()

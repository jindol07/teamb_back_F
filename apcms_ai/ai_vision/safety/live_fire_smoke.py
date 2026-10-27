# D:/finalProjectB/back/apcms_ai/ai_vision/safety/live_fire_smoke.py
"""웹캠/MP4에서 화재·연기를 주기적으로 탐지하고 '화재 의심' 이벤트를 로컬 기록합니다.

이 코드는 연구·보조 모니터링 용도입니다. 소방 설비나 사람의 확인을 대체하지 않습니다.
기본 실행 시 영상·증거 이미지는 저장하지 않고 Spring Boot/외부 API로 전송하지 않습니다.
"""

import argparse
import json
import math
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from ai_vision.paths import RESULT_DIR
from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.recognition.model_files import require_model_file
from ai_vision.safety.fire_smoke_detector import MODEL_PATH
from ai_vision.safety.fire_event_state import FireEventStateManager
from ai_vision.safety.preroll_buffer import PreEventFrameBuffer


# 1. 추론·화면 표시의 기본값 (테스트 이미지 비교 결과를 기반으로 한 임시 설정)
CLASS_COLORS = {"FIRE": (0, 0, 255), "SMOKE": (0, 255, 255)}  # OpenCV BGR
PREVIEW_TITLE = "AI Vision - Fire/Smoke (press Q to quit)"


@dataclass(frozen=True)
class LiveConfig:
    # 1-1. 영상 입력: video_path가 없다면 로컬 카메라 사용
    camera_index: int = 0
    video_path: str | None = None
    # SAFETY_SHARED_FRAME_INPUT_V1: 주차 A/B 공유 프레임. 직접 카메라를 열지 않습니다.
    shared_run_dir: Path | None = None
    shared_role: str | None = None
    shared_camera_id: str | None = None
    shared_max_age: float = 3.0
    shared_max_silence: float = 12.0
    interval: float = 0.5
    conf: float = 0.20                  # 기존 공통 임계값 (호환 유지)
    fire_conf: float | None = None      # 미지정 시 conf 사용
    smoke_conf: float | None = None     # 미지정 시 conf 사용
    candidate_conf: float = 0.20        # 후보 기록용 YOLO 최저 임계값
    save_candidates: bool = False       # 후보 기록은 명시적으로 켠 경우에만 저장
    iou: float = 0.45
    image_size: int = 640
    device: str = "cpu"

    # 1-2. 연속 탐지/이벤트 설정: 최근 5회 중 3회, 3회 미탐지 시 재무장
    window: int = 5
    min_hits: int = 3
    clear_after: int = 3
    cooldown: float = 30.0
    region_iou: float = 0.15      # 의심 영역 간 IoU 매칭 기준
    heartbeat: float = 10.0       # ONGOING 유지 이력 기록 간격(초)
    max_regions: int = 16         # 카메라당 추적할 최대 영역 수

    # 1-3. 시험 중 무한 실행 방지를 위한 기본 제한과 로컬 결과 설정
    max_seconds: float = 20.0  # 0은 시간 제한 없음
    max_frames: int = 0        # 0은 프레임 수 제한 없음
    show: bool = False
    save_evidence: bool = False
    save_video: bool = False
    save_preroll: bool = False          # 사건 직전 추론 샘플 JPEG 보관(기본 꺼짐)
    preroll_seconds: float = 5.0      # 가장 최근 5초의 추론 샘플
    preroll_max_frames: int = 30     # 메모리 보관 최대 샘플 개수
    output_dir: Path | None = None

    # 1-4. 카메라를 열기 전에 실제 YOLO 모델을 준비하고, 장애 시 제한적으로 재연결합니다.
    warmup: bool = True             # 실제 모델을 내부에서 불러온 경우에만 자동 워밍업
    camera_retries: int = 3         # 처음 열기 실패·연결 끊김당 추가 재시도 횟수
    camera_retry_delay: float = 1.0 # 재시도 사이 대기(초); 0 허용
    publish_alert_session: bool = False  # 외부 실시간 전송기가 읽을 세션 메타데이터(기본 꺼짐)
    production_camera: bool = False  # 기본 시험 모드. 운영은 CAMERA에서 명시적으로만 허용

    def __post_init__(self):
        # 사용자 설정 오류를 카메라 접근 전에 거부합니다.
        if type(self.camera_index) is not int or self.camera_index < 0:
            raise ValueError("카메라 번호는 0 이상의 정수여야 합니다.")
        if self.video_path is not None and (not isinstance(self.video_path, str) or not self.video_path.strip()):
            raise ValueError("영상 파일 경로를 확인하세요.")
        if self.shared_run_dir is not None:
            if self.video_path is not None or self.shared_role not in ("gate", "parking"):
                raise ValueError("공유 입력에서는 --video 대신 role=gate/parking을 지정하세요.")
            if (not isinstance(self.shared_camera_id, str) or not self.shared_camera_id.strip()
                    or len(self.shared_camera_id) > 128):
                raise ValueError("공유 입력에는 예상 논리 camera_id가 필요합니다.")
            # 3. Boot source.name 계약과 같은 문자·길이 제한을 모델 로드 전에 검사합니다.
            source_name = f"{self.shared_role}.{self.shared_camera_id}"
            if len(source_name) > 128 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for c in source_name):
                raise ValueError("공유 출처 이름은 영문·숫자·밑줄·점·하이픈 128자 이하여야 합니다.")
            for key in ("shared_max_age", "shared_max_silence"):
                val = getattr(self, key)
                if type(val) not in (int, float) or not math.isfinite(val) or val <= 0:
                    raise ValueError(f"{key}는 양의 유한한 시간(초)이어야 합니다.")
            if self.shared_max_silence <= self.shared_max_age:
                raise ValueError("공유 입력 대기시간은 프레임 만료시간보다 길어야 합니다.")
        elif self.shared_role is not None or self.shared_camera_id is not None:
            raise ValueError("공유 프레임 설정에는 shared_run_dir가 필요합니다.")
        for name in ("interval", "max_seconds", "cooldown"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or (value <= 0 if name == "interval" else value < 0):
                raise ValueError(f"{name} 설정은 유효한 시간(초)이어야 합니다.")
        for name in ("conf", "fire_conf", "smoke_conf", "candidate_conf", "iou"):
            value = getattr(self, name)
            if value is None and name in ("fire_conf", "smoke_conf"):
                continue
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value < 1:
                raise ValueError(f"{name}은 0과 1 사이여야 합니다.")
        if type(self.publish_alert_session) is not bool:
            raise ValueError("publish_alert_session은 True/False여야 합니다.")
        if type(self.production_camera) is not bool:
            raise ValueError("production_camera는 True/False여야 합니다.")
        if self.production_camera and self.video_path is not None:
            raise ValueError("운영 모드는 실제 CAMERA 입력에서만 허용합니다. 영상 파일은 TEST로 처리하세요.")
        if type(self.warmup) is not bool:
            raise ValueError("warmup은 True/False여야 합니다.")
        if type(self.camera_retries) is not int or not 0 <= self.camera_retries <= 20:
            raise ValueError("camera_retries는 0~20의 정수여야 합니다.")
        if (type(self.camera_retry_delay) not in (int, float) or
                not math.isfinite(self.camera_retry_delay) or not 0 <= self.camera_retry_delay <= 30):
            raise ValueError("camera_retry_delay는 0~30초여야 합니다.")
        if type(self.save_preroll) is not bool:
            raise ValueError("save_preroll은 True/False여야 합니다.")
        if type(self.preroll_seconds) not in (int, float) or not math.isfinite(self.preroll_seconds) or self.preroll_seconds <= 0:
            raise ValueError("preroll_seconds는 양의 시간(초)이어야 합니다.")
        if type(self.preroll_max_frames) is not int or not 1 <= self.preroll_max_frames <= 120:
            raise ValueError("preroll_max_frames는 1~120이어야 합니다.")
        if type(self.save_candidates) is not bool:
            raise ValueError("save_candidates는 True/False여야 합니다.")
        if self.save_candidates and self.candidate_conf > min(self.thresholds.values()):
            raise ValueError("candidate_conf는 FIRE·SMOKE 임계값보다 높을 수 없습니다.")
        if type(self.image_size) is not int or self.image_size < 32:
            raise ValueError("이미지 입력 크기를 확인하세요.")
        for name in ("window", "min_hits", "clear_after"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name}은 양의 정수여야 합니다.")
        if self.min_hits > self.window:
            raise ValueError("min_hits는 window보다 클 수 없습니다.")
        if type(self.region_iou) not in (int, float) or not math.isfinite(self.region_iou) or not 0 < self.region_iou <= 1:
            raise ValueError("영역 IoU는 0 초과 1 이하여야 합니다.")
        if type(self.heartbeat) not in (int, float) or not math.isfinite(self.heartbeat) or self.heartbeat <= 0:
            raise ValueError("유지 상태 기록 간격을 확인하세요.")
        if type(self.max_regions) is not int or not 1 <= self.max_regions <= 128:
            raise ValueError("최대 추적 영역 수는 1~128이어야 합니다.")
        if type(self.max_frames) is not int or self.max_frames < 0:
            raise ValueError("max_frames는 0 이상의 정수여야 합니다.")
        if not isinstance(self.device, str) or not self.device.strip():
            raise ValueError("추론 장치를 확인하세요.")

    @property
    def thresholds(self):
        """종류별 임계값을 해석합니다. 기존 --conf 옵션도 그대로 지원합니다."""
        return {"FIRE": self.conf if self.fire_conf is None else self.fire_conf,
                "SMOKE": self.conf if self.smoke_conf is None else self.smoke_conf}


# 2. 프레임별 탐지와 시간 창을 분리하여 오탐을 줄이는 상태 관리자
class FireSmokeWindow:
    """연속 검출을 '의심 이벤트'로 변환합니다. 안전상 화재 확정 판단은 하지 않습니다."""

    def __init__(self, window=5, min_hits=3, clear_after=3, cooldown=30.0):
        if type(window) is not int or type(min_hits) is not int or not 1 <= min_hits <= window:
            raise ValueError("최근 탐지 창과 최소 탐지 횟수를 확인하세요.")
        if type(clear_after) is not int or clear_after < 1:
            raise ValueError("재무장에 필요한 미탐지 횟수를 확인하세요.")
        if type(cooldown) not in (int, float) or not math.isfinite(cooldown) or cooldown < 0:
            raise ValueError("쿨다운 시간을 확인하세요.")
        self.window = window
        self.min_hits = min_hits
        self.clear_after = clear_after
        self.cooldown = float(cooldown)
        self.history = {kind: deque(maxlen=window) for kind in CLASS_COLORS}
        self.latched = {kind: False for kind in CLASS_COLORS}
        self.absent = {kind: 0 for kind in CLASS_COLORS}
        self.last_event = {kind: None for kind in CLASS_COLORS}
        self.last_time = None

    def update(self, source_seconds, detections):
        # 2-1. 시각은 단조 증가해야 합니다. MP4는 영상 시각, 웹캠은 실행 경과 시각.
        if type(source_seconds) not in (int, float) or not math.isfinite(source_seconds) or source_seconds < 0:
            raise ValueError("프레임 시각이 잘못되었습니다.")
        if self.last_time is not None and source_seconds < self.last_time:
            raise ValueError("프레임 시각이 이전보다 빠릅니다.")
        self.last_time = source_seconds

        # 2-2. 한 프레임에서 같은 불꽃 박스가 여러 개여도 1회 탐지로 계산
        strongest = {}
        for det in detections:
            kind = det["class_name"]
            if kind in CLASS_COLORS and (kind not in strongest or det["confidence"] > strongest[kind]["confidence"]):
                strongest[kind] = det

        new_events = []
        for kind in CLASS_COLORS:
            found = kind in strongest
            self.history[kind].append(found)
            self.absent[kind] = 0 if found else self.absent[kind] + 1
            if self.latched[kind] and self.absent[kind] >= self.clear_after:
                self.latched[kind] = False
            hits = sum(self.history[kind])
            # 2-3. 현재 프레임에도 감지되고 지정 횟수 이상 검출되었을 때만 의심
            if found and hits >= self.min_hits and not self.latched[kind]:
                self.latched[kind] = True
                last = self.last_event[kind]
                if last is None or source_seconds - last >= self.cooldown:
                    self.last_event[kind] = source_seconds
                    new_events.append({
                        "type": kind,
                        "confidence": strongest[kind]["confidence"],
                        "bbox": list(strongest[kind]["bbox"]),
                        "hits_in_window": hits,
                    })
        return new_events


# 3. YOLO 결과를 안전하게 추출해 화면 표시와 기록에 공통 사용
def detect_frame(model, frame, *, conf=0.20, iou=0.45, image_size=640, device="cpu",
                 fire_conf=None, smoke_conf=None, candidate_conf=None, candidates_out=None):
    """YOLO 결과를 종류별로 걸러 의심 판정에 전달할 탐지만 반환합니다.

    candidates_out을 전달한 경우에는 더 낮은 candidate_conf부터 예측해
    수용/제외 여부를 추가로 저장합니다. 기존 반환값 (detections, inference_ms)은 유지합니다.
    """
    # 3-1. 빈 프레임 검사: 카메라 접근 전에 잘못된 입력을 발견합니다.
    if frame is None or getattr(frame, "size", 0) == 0:
        raise ValueError("빈 카메라 프레임은 분석할 수 없습니다.")
    thresholds = {"FIRE": conf if fire_conf is None else fire_conf,
                  "SMOKE": conf if smoke_conf is None else smoke_conf}
    if candidates_out is not None:
        if not isinstance(candidates_out, list):
            raise TypeError("candidates_out은 목록이어야 합니다.")
        if candidate_conf is None or candidate_conf > min(thresholds.values()):
            raise ValueError("후보 기록 임계값은 클래스별 임계값 이하여야 합니다.")
    # 3-2. 모델의 conf를 너무 높게 설정하면 낮은 점수의 후보가 YOLO에서 먼저 사라집니다.
    prediction_conf = min(thresholds.values())
    if candidates_out is not None:
        prediction_conf = min(prediction_conf, candidate_conf)
    started = time.perf_counter()
    results = model.predict(source=frame, conf=prediction_conf, iou=iou, imgsz=image_size,
                            device=device, verbose=False)
    inference_ms = round((time.perf_counter() - started) * 1000, 2)
    if not results:
        raise RuntimeError("YOLO 추론 결과가 비어 있습니다.")

    height, width = frame.shape[:2]
    detections = []
    for box in results[0].boxes:
        class_id = int(box.cls[0].item())
        names = model.names
        try:
            name = str(names[class_id]).upper()
        except (IndexError, KeyError, TypeError):
            continue
        if name not in CLASS_COLORS:
            continue
        score = float(box.conf[0].item())
        coords = box.xyxy[0].tolist()
        if not 0 <= score <= 1 or not math.isfinite(score) or len(coords) != 4 or not all(math.isfinite(float(v)) for v in coords):
            continue
        x1, y1, x2, y2 = (int(round(float(v))) for v in coords)
        x1, x2 = max(0, min(width - 1, x1)), max(0, min(width - 1, x2))
        y1, y2 = max(0, min(height - 1, y1)), max(0, min(height - 1, y2))
        if x2 <= x1 or y2 <= y1:
            continue
        # 3-3. 후보 목록에 포함될 최저 점수는 실제 YOLO와 동일하게 검사합니다.
        if score < prediction_conf:
            continue
        item = {"class_name": name, "confidence": round(score, 4),
                "bbox": [x1, y1, x2, y2]}
        accepted = score >= thresholds[name]
        if candidates_out is not None:
            candidates_out.append({**item, "class_threshold": thresholds[name],
                                   "accepted": accepted,
                                   "reason": "ACCEPTED" if accepted else "BELOW_CLASS_THRESHOLD"})
        if accepted:
            detections.append(item)
    return detections, inference_ms


def draw_detections(frame, detections):
    # 3-2. 추론에 사용한 원본 배열은 수정하지 않습니다.
    drawn = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        color = CLASS_COLORS[det["class_name"]]
        cv2.rectangle(drawn, (x1, y1), (x2, y2), color, 2)
        cv2.putText(drawn, f"{det['class_name']} {det['confidence']:.2f}",
                    (x1, max(17, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return drawn


# 4-0. 모델 사전 준비는 사건 판단과 별도로 실행합니다.
def warmup_fire_smoke_model(model, config):
    """카메라를 열기 전에 빈 프레임으로 YOLO 초기 연산을 완료합니다.

    워밍업 결과는 후보·이벤트·추론 횟수에 포함하지 않습니다.
    가짜 모델을 주입한 테스트에서는 run_live가 자동 워밍업하지 않습니다.
    """
    dummy = np.zeros((config.image_size, config.image_size, 3), dtype=np.uint8)
    begin = time.perf_counter()
    predictions = model.predict(source=dummy, conf=min(config.thresholds.values()),
                                iou=config.iou, imgsz=config.image_size,
                                device=config.device, verbose=False)
    if not predictions:
        raise RuntimeError("YOLO 모델 워밍업 결과가 비어 있습니다.")
    return round((time.perf_counter() - begin) * 1000, 2)


# 4. 실시간 감지 실행기: 모델 한 번 로드, 주기적 추론, 기본 로컬 기록만 수행
def run_live(config, *, model=None, capture=None, monotonic=None, capture_factory=None):
    """영상 분석 및 원본 입력 연결 상태를 함께 관리합니다.

    capture_factory는 카메라 재연결 테스트를 위한 선택적 주입 지점입니다.
    재연결 시에는 예전 사건을 SESSION_ENDED로 표시하고 새 관찰 세션을 시작합니다.
    이를 실제 화재 진압(CLEARED)으로 잘못 기록하지 않습니다.
    """
    if not isinstance(config, LiveConfig):
        raise TypeError("LiveConfig로 실행 설정을 전달하세요.")
    if config.video_path is not None and not Path(config.video_path).is_file():
        raise FileNotFoundError(f"영상 파일을 찾을 수 없습니다: {config.video_path}")
    if config.show:
        from ai_vision.camera_runtime import require_display
        require_display()

    owned_model = model is None
    # 공유 모드에서는 VideoCapture를 생성하지 않고 제공받은 원본 프레임만 읽습니다.
    factory = cv2.VideoCapture if capture_factory is None else capture_factory
    clock = time.monotonic if monotonic is None else monotonic
    writer = None
    candidate_handle = None
    window_opened = False
    preview_frames = preview_wait_pumps = 0
    last_preview_tick = None
    preview_title = (f"{PREVIEW_TITLE} [{config.shared_role}:{config.shared_camera_id}]"
                     if config.shared_run_dir is not None else PREVIEW_TITLE)

    def preview_wait():
        nonlocal window_opened, preview_wait_pumps
        # 2. 수신 0장이어도 입력 대기 상태를 보이고 Q를 처리합니다.
        preview_wait_pumps += 1
        # 새 표본 사이에는 마지막 분석 화면을 유지하고 입력 만료 때만 대기로 전환합니다.
        if last_preview_tick is not None and time.monotonic() - last_preview_tick <= config.shared_max_age:
            return cv2.waitKey(1) & 0xFF != ord("q")
        canvas = np.zeros((240, 640, 3), dtype=np.uint8)
        cv2.putText(canvas, "WAITING FOR FRESH SHARED FRAME", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 255, 255), 2)
        cv2.putText(canvas, f"{config.shared_role}:{config.shared_camera_id}", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 2)
        cv2.putText(canvas, "Check parking runtime / current run_id. Q: stop", (20, 160), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1)
        cv2.imshow(preview_title, canvas)
        window_opened = True
        return cv2.waitKey(1) & 0xFF != ord("q")
    frame_count = sample_count = total_inference_ms = 0
    last_sample_sec = None
    status = "STOPPED"
    error_type = None
    model_load_ms = model_warmup_ms = None
    warmup_completed = False
    capture_open_attempts = camera_reconnect_attempts = camera_reconnects = camera_read_failures = 0
    camera_health = []
    camera_health_total = 0
    saved_video_segments = []
    video_fps = None
    video_part = 1
    events = []
    candidate_counts = {name: {"total": 0, "accepted": 0, "rejected": 0} for name in CLASS_COLORS}
    candidate_samples = 0
    preroll = (PreEventFrameBuffer(seconds=config.preroll_seconds,
                                   max_frames=config.preroll_max_frames)
               if config.save_preroll else None)
    preroll_saved = preroll_image_count = 0
    transitions = []
    counts = {kind: 0 for kind in ("SUSPECTED", "ONGOING", "CLEARED", "REOPENED", "SESSION_ENDED")}

    def new_state():
        return FireEventStateManager(config.window, config.min_hits, config.clear_after,
                                     config.cooldown, region_iou=config.region_iou,
                                     heartbeat_seconds=config.heartbeat, max_regions=config.max_regions)

    state = new_state()
    session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    output_dir = (Path(config.output_dir) if config.output_dir is not None
                  else RESULT_DIR / "safety" / "live" / session_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    started_utc = datetime.now(timezone.utc).isoformat()
    input_name = (f"{config.shared_role}.{config.shared_camera_id}"
                  if config.shared_run_dir is not None else
                  (Path(config.video_path).name if config.video_path else f"camera_{config.camera_index}"))
    # 실행 도중 생성하는 sidecar와 종료 summary가 같은 운영/시험 식별자를 사용합니다.
    record_type = "FIRE_SMOKE_LIVE_PRODUCTION" if config.production_camera else "FIRE_SMOKE_LIVE_TEST"
    # 4-1. 실시간 전송용 식별 정보는 시작 시점에만 선택적으로 기록합니다.
    # 종료 시 만들어지는 summary.json과 정확히 같은 started_at_utc를 사용하므로
    # 실시간 전송과 사후 재전송의 transition_id가 동일하게 유지됩니다.
    if config.publish_alert_session:
        if any((output_dir / name).exists() for name in
               ("alert_session.json", "summary.json", "incident_history.json", "fire_alert_sent_state.json")):
            raise ValueError("실시간 알림 출력 폴더에는 이전 실행 기록이 없어야 합니다.")
        write_json_atomic(output_dir / "alert_session.json", {
            "record_type": record_type,
            "source": "VIDEO" if config.video_path else "CAMERA",
            "source_name": input_name,
            "started_at_utc": started_utc,
            "status": "RUNNING",
        })
    started_tick = None

    def record_health(kind, *, attempt=None):
        nonlocal camera_health_total
        camera_health_total += 1
        row = {"status": kind, "logged_at_utc": datetime.now(timezone.utc).isoformat(),
               "frame_index": frame_count}
        if attempt is not None:
            row["attempt"] = attempt
        camera_health.append(row)
        # 장시간 동작 시에도 메모리 크기가 무한히 증가하지 않도록 최근 200건만 유지합니다.
        if len(camera_health) > 200:
            del camera_health[:-200]
        # 매 변화마다 남겨 갑작스러운 중단 후에도 연결 이력을 확인할 수 있게 합니다.
        write_json_atomic(output_dir / "camera_health.json", {"total_changes": camera_health_total, "changes": camera_health})

    def close_capture():
        nonlocal capture
        if capture is not None:
            capture.release()
            capture = None

    def open_source():
        nonlocal capture, capture_open_attempts, camera_reconnect_attempts
        if config.shared_run_dir is not None:
            from ai_vision.safety.shared_frame_source import SharedFrameCapture
            capture = SharedFrameCapture(config.shared_run_dir, config.shared_role,
                config.shared_camera_id, max_age=config.shared_max_age,
                max_silence=config.shared_max_silence,
                on_wait=preview_wait if config.show else None)
            return capture.isOpened()
        # 첫 번째 시도는 별도 연결 지연 없이 실행합니다.
        for attempt in range(config.camera_retries + 1 if config.video_path is None else 1):
            if attempt:
                camera_reconnect_attempts += 1
                time.sleep(config.camera_retry_delay)
            if capture is None:
                capture = factory(config.video_path if config.video_path is not None else config.camera_index)
                capture_open_attempts += 1
            if capture is not None and capture.isOpened():
                return True
            if config.video_path is None:
                record_health("CAMERA_OPEN_FAILED", attempt=attempt + 1)
            close_capture()
        return False

    def close_previous_observation(second, reason):
        # 카메라 손실은 '미탐지'가 아니라 관찰 중단입니다.
        for change in state.finish(second, frame_count, reason):
            counts[change["status"]] += 1
            transitions.append({**change, "logged_at_utc": datetime.now(timezone.utc).isoformat()})
        write_json_atomic(output_dir / "incident_history.json", {"transitions": transitions})

    try:
        if config.show and config.shared_run_dir is not None:
            if not preview_wait():
                raise KeyboardInterrupt
        if config.save_candidates:
            candidate_handle = (output_dir / "detection_candidates.jsonl").open("w", encoding="utf-8", newline="\n")

        if owned_model:
            # YOLO 모델을 한 번 로드합니다. 지연되는 첫 추론은 카메라 열기 전에 처리합니다.
            require_model_file(MODEL_PATH)
            from ultralytics import YOLO
            begin = time.perf_counter()
            model = YOLO(str(MODEL_PATH))
            model_load_ms = round((time.perf_counter() - begin) * 1000, 2)
            if config.warmup:
                model_warmup_ms = warmup_fire_smoke_model(model, config)
                warmup_completed = True
        # 주입된 가짜/외부 모델은 자동 워밍업하지 않아 기존 테스트·호출자를 유지합니다.
        if not open_source():
            status = ("SHARED_INPUT_UNAVAILABLE" if config.shared_run_dir is not None else
                      ("VIDEO_OPEN_FAILED" if config.video_path else "CAMERA_OPEN_FAILED"))
        else:
            started_tick = clock()   # 모델 로드·워밍업·카메라 열기 시간은 관찰시간에서 제외
            if config.video_path is not None:
                fps_value = float(capture.get(cv2.CAP_PROP_FPS))
                video_fps = fps_value if math.isfinite(fps_value) and fps_value > 0 else 25.0

            while True:
                if config.max_frames and frame_count >= config.max_frames:
                    status = "MAX_FRAMES"
                    break
                # 카메라는 프레임이 없어도 실행시간 제한이 동작해야 합니다.
                # 기존 mock clock의 호출횟수를 바꾸지 않도록 정상 프레임에서는 기존 로직을 사용합니다.
                success, frame = capture.read()
                if not success or frame is None or getattr(frame, "size", 0) == 0:
                    if config.video_path is not None:
                        # 프레임 메타데이터가 신뢰할 만한 경우에만 비정상 EOF를 구분합니다.
                        total = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
                        position = float(capture.get(cv2.CAP_PROP_POS_FRAMES))
                        bad_end = (frame_count == 0 or (math.isfinite(total) and math.isfinite(position)
                                   and total > 0 and 0 <= position < total - 1.5))
                        status = "VIDEO_READ_FAILED" if bad_end else "VIDEO_END"
                        break

                    if config.shared_run_dir is not None:
                        # 입력 만료/CLOSED/손상 시 과거 프레임을 재사용하지 않고 사건을 종료.
                        # 주차 카메라 장치 재연결은 시도하지 않습니다.
                        status = "USER_INTERRUPTED" if capture.last_reason == "USER_INTERRUPTED" else "SHARED_INPUT_UNAVAILABLE"
                        record_health("SHARED_INPUT_" + (capture.last_reason or "UNAVAILABLE"))
                        break
                    camera_read_failures += 1
                    record_health("CAMERA_READ_FAILED")
                    recovered = False
                    # 고장 난 캡처 객체를 다시 사용하지 않고 장치를 새로 엽니다.
                    for attempt in range(1, config.camera_retries + 1):
                        camera_reconnect_attempts += 1
                        close_capture()
                        time.sleep(config.camera_retry_delay)
                        capture = factory(config.camera_index)
                        capture_open_attempts += 1
                        if capture is not None and capture.isOpened():
                            success, frame = capture.read()
                            if success and frame is not None and getattr(frame, "size", 0) > 0:
                                recovered = True
                                break
                        record_health("CAMERA_RECONNECT_FAILED", attempt=attempt)
                    if not recovered:
                        status = "CAMERA_READ_FAILED"
                        break
                    camera_reconnects += 1
                    record_health("CAMERA_RECONNECTED", attempt=attempt)
                    last_second = state.last_time if state.last_time is not None else 0.0
                    close_previous_observation(last_second, "CAMERA_DISCONNECTED")
                    state = new_state()
                    last_sample_sec = None
                    if preroll is not None:
                        preroll = PreEventFrameBuffer(seconds=config.preroll_seconds,
                                                      max_frames=config.preroll_max_frames)
                    # 장치 재연결 시 해상도가 달라질 수 있으므로 MP4도 새 파일로 구분합니다.
                    if writer is not None:
                        writer.release()
                        writer = None
                        video_part += 1

                frame_count += 1
                source_sec = ((frame_count - 1) / video_fps if video_fps is not None
                              else max(0.0, clock() - started_tick))
                if config.max_seconds and source_sec >= config.max_seconds:
                    status = "TIME_LIMIT"
                    break

                annotated = frame
                if last_sample_sec is None or source_sec - last_sample_sec >= config.interval - 1e-9:
                    last_sample_sec = source_sec
                    candidates = [] if config.save_candidates else None
                    detections, ms = detect_frame(model, frame, conf=config.conf, iou=config.iou,
                                                  image_size=config.image_size, device=config.device,
                                                  fire_conf=config.fire_conf, smoke_conf=config.smoke_conf,
                                                  candidate_conf=config.candidate_conf if config.save_candidates else None,
                                                  candidates_out=candidates)
                    sample_count += 1
                    if candidates is not None:
                        candidate_samples += 1
                        for candidate in candidates:
                            stats = candidate_counts[candidate["class_name"]]
                            stats["total"] += 1
                            stats["accepted" if candidate["accepted"] else "rejected"] += 1
                        line = {"frame_index": frame_count, "source_seconds": round(source_sec, 3),
                                "inference_ms": ms, "candidates": candidates}
                        candidate_handle.write(json.dumps(line, ensure_ascii=False, allow_nan=False) + "\n")
                        candidate_handle.flush()
                    total_inference_ms += ms
                    annotated = draw_detections(frame, detections)
                    updates = state.update(source_sec, frame_count, detections)
                    for change in updates:
                        status_name = change["status"]
                        counts[status_name] += 1
                        record = {**change, "logged_at_utc": datetime.now(timezone.utc).isoformat()}
                        if preroll is not None and status_name in ("SUSPECTED", "REOPENED"):
                            folder_name = (f"preroll_{preroll_saved + 1:04d}_"
                                           f"{change['type'].lower()}_{frame_count:06d}_{uuid.uuid4().hex[:8]}")
                            path_name, saved_count = preroll.save_before(output_dir, folder_name, source_sec)
                            record["preroll_folder"] = path_name
                            record["preroll_samples"] = saved_count
                            preroll_saved += 1
                            preroll_image_count += saved_count
                        if status_name == "SUSPECTED":
                            event = {**record, "evidence_image": None}
                            if config.save_evidence:
                                name = f"event_{len(events) + 1:04d}_{change['type'].lower()}.jpg"
                                file = output_dir / name
                                if not cv2.imwrite(str(file), annotated):
                                    raise OSError(f"증거 이미지 저장 실패: {file}")
                                event["evidence_image"] = name
                            events.append(event)
                            write_json_atomic(output_dir / "events.json", {"events": events})
                        transitions.append(record)
                        write_json_atomic(output_dir / "incident_history.json", {"transitions": transitions})
                        if status_name != "ONGOING":
                            print(f"[{status_name}] {change['type']} | {source_sec:.2f}s | "
                                  f"conf={change['confidence']:.2f} | frame={frame_count}")
                    if preroll is not None:
                        preroll.add(frame, source_sec, frame_count)

                if config.save_video:
                    if writer is None:
                        h, w = frame.shape[:2]
                        fps = video_fps if video_fps is not None else 20.0
                        video_name = ("annotated.mp4" if video_part == 1
                                      else f"annotated_part_{video_part:02d}.mp4")
                        writer = cv2.VideoWriter(str(output_dir / video_name),
                                                 cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
                        if not writer.isOpened():
                            raise OSError("결과 MP4 기록기를 열지 못했습니다.")
                        saved_video_segments.append(video_name)
                    writer.write(annotated)
                if config.show:
                    cv2.imshow(preview_title, annotated)
                    preview_frames += 1
                    last_preview_tick = time.monotonic()
                    window_opened = True
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        status = "USER_INTERRUPTED"
                        break
    except KeyboardInterrupt:
        status = "USER_INTERRUPTED"
    except Exception as error:
        status = "ERROR"
        error_type = type(error).__name__
        raise
    finally:
        try:
            if writer is not None:
                writer.release()
        finally:
            try:
                if candidate_handle is not None:
                    candidate_handle.close()
            finally:
                close_capture()
            if window_opened:
                cv2.destroyWindow(preview_title)
            last_second = state.last_time if state.last_time is not None else 0.0
            end_changes = state.finish(last_second, frame_count, status)
            for change in end_changes:
                counts[change["status"]] += 1
                transitions.append({**change, "logged_at_utc": datetime.now(timezone.utc).isoformat()})
            write_json_atomic(output_dir / "incident_history.json", {"transitions": transitions})
            write_json_atomic(output_dir / "incident_states.json", state.snapshot())
            summary = {
                "record_type": record_type, "status": status,
                "error_type": error_type, "source": "VIDEO" if config.video_path else "CAMERA",
                "source_name": input_name,
                "started_at_utc": started_utc, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "captured_frames": frame_count, "inference_samples": sample_count,
                "preview_requested": config.show, "preview_frames": preview_frames,
                "preview_wait_pumps": preview_wait_pumps,
                "suspected_events": len(events),
                "average_inference_ms": round(total_inference_ms / sample_count, 2) if sample_count else None,
                "model_load_ms": model_load_ms, "model_warmup_ms": model_warmup_ms,
                "warmup_enabled": config.warmup, "warmup_completed": warmup_completed,
                "camera_open_attempts": capture_open_attempts,
                "camera_reconnect_attempts": camera_reconnect_attempts,
                "camera_reconnects": camera_reconnects, "camera_read_failures": camera_read_failures,
                "camera_health_log": "camera_health.json" if camera_health else None,
                "camera_health_events": camera_health_total,
                "saved_video_segments": saved_video_segments,
                "conf": config.conf, "fire_conf": config.thresholds["FIRE"],
                "smoke_conf": config.thresholds["SMOKE"], "iou": config.iou,
                "interval_seconds": config.interval,
                "saved_candidates": config.save_candidates,
                "candidate_conf": config.candidate_conf if config.save_candidates else None,
                "candidate_log": "detection_candidates.jsonl" if config.save_candidates else None,
                "candidate_samples": candidate_samples if config.save_candidates else None,
                "candidate_counts_by_type": candidate_counts if config.save_candidates else None,
                "window": config.window, "min_hits": config.min_hits,
                "clear_after": config.clear_after, "cooldown_seconds": config.cooldown,
                "saved_evidence": config.save_evidence, "saved_video": config.save_video,
                "saved_preroll": config.save_preroll,
                "preroll_seconds": config.preroll_seconds if config.save_preroll else None,
                "preroll_max_frames": config.preroll_max_frames if config.save_preroll else None,
                "preroll_event_folders": preroll_saved if config.save_preroll else None,
                "preroll_saved_images": preroll_image_count if config.save_preroll else None,
                "incident_transition_counts": counts,
                "active_incidents_at_end": state.snapshot()["active"],
                "ignored_regions": state.ignored_regions,
                "region_iou": config.region_iou, "heartbeat_seconds": config.heartbeat,
            }
            write_json_atomic(output_dir / "summary.json", summary)
            write_json_atomic(output_dir / "events.json", {"events": events})
    return summary


# 5. CLI: 다른 Vision 기능을 바꾸지 않고 단독 실행 가능
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--camera", type=int, default=0, help="웹캠 번호 (기본값 0)")
    source.add_argument("--video", type=str, help="MP4 등 영상 파일 경로")
    source.add_argument("--shared-run-dir", type=Path, help="주차 최신 프레임 실행 폴더(run_id). 카메라 재오픈 없음")
    parser.add_argument("--shared-role", choices=("gate", "parking"))
    parser.add_argument("--shared-camera-id", help="주차 설정의 gate_id 또는 parking_id")
    parser.add_argument("--shared-max-age", type=float, default=3.0)
    parser.add_argument("--shared-max-silence", type=float, default=12.0)
    parser.add_argument("--interval", type=float, default=0.5, help="추론 간격(초); 기본 0.5")
    parser.add_argument("--conf", type=float, default=0.20, help="공통 신뢰도 임계값 (기존 옵션; 기본 0.20)")
    parser.add_argument("--fire-conf", type=float, help="FIRE 신뢰도 기준 (미지정 시 --conf 사용)")
    parser.add_argument("--smoke-conf", type=float, help="SMOKE 신뢰도 기준 (미지정 시 --conf 사용)")
    parser.add_argument("--save-candidates", action="store_true", help="수용·제외된 탐지 후보를 JSONL로 저장")
    parser.add_argument("--candidate-conf", type=float, default=0.20,
                        help="후보 저장을 위한 최저 YOLO 신뢰도 (기본 0.20; 클래스 기준 이하여야 함)")
    parser.add_argument("--iou", type=float, default=0.45, help="YOLO NMS IoU")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--min-hits", type=int, default=3)
    parser.add_argument("--clear-after", type=int, default=3)
    parser.add_argument("--cooldown", type=float, default=30.0)
    parser.add_argument("--region-iou", type=float, default=0.15, help="같은 영역 IoU 매칭 기준")
    parser.add_argument("--heartbeat", type=float, default=10.0, help="의심 상태 유지 이력 기록 간격(초)")
    parser.add_argument("--max-regions", type=int, default=16, help="추적 영역 최대 수")
    parser.add_argument("--max-seconds", type=float, default=20.0, help="0이면 시간 제한 없음")
    parser.add_argument("--max-frames", type=int, default=0, help="0이면 제한 없음")
    parser.add_argument("--show", action="store_true", help="화면 표시 (Q로 종료)")
    parser.add_argument("--save-evidence", action="store_true", help="의심 이벤트 이미지 저장")
    parser.add_argument("--save-video", action="store_true", help="전체 처리 영상 저장")
    parser.add_argument("--save-preroll", action="store_true", help="SUSPECTED/REOPENED 직전 추론 프레임을 JPEG로 저장")
    parser.add_argument("--preroll-seconds", type=float, default=5.0, help="보관할 과거 초(기본 5초)")
    parser.add_argument("--preroll-max-frames", type=int, default=30, help="메모리에 보관할 최대 JPEG 샘플(기본 30개)")
    parser.add_argument("--warmup", dest="warmup", action="store_true", default=True,
                        help="카메라 연결 전 실제 YOLO 모델 사전 추론(기본 켜짐)")
    parser.add_argument("--no-warmup", dest="warmup", action="store_false",
                        help="모델 사전 추론 생략(속도 비교용)")
    parser.add_argument("--camera-retries", type=int, default=3,
                        help="카메라 열기/읽기 장애 시 추가 재연결 횟수(기본 3)")
    parser.add_argument("--camera-retry-delay", type=float, default=1.0,
                        help="재연결 간 대기 시간(초, 기본 1)")
    parser.add_argument("--publish-alert-session", action="store_true",
                        help="실시간 알림용 세션 메타데이터 기록(기본 꺼짐)")
    parser.add_argument("--production-camera", action="store_true",
                        help="실제 카메라 결과를 운영 데이터로 표시. 단독 실행은 HTTP 전송 안 함")
    parser.add_argument("--output", type=Path, help="결과 저장 폴더")
    args = parser.parse_args(argv)
    config = LiveConfig(camera_index=args.camera, video_path=args.video, interval=args.interval,
                        shared_run_dir=args.shared_run_dir, shared_role=args.shared_role,
                        shared_camera_id=args.shared_camera_id, shared_max_age=args.shared_max_age,
                        shared_max_silence=args.shared_max_silence,
                        conf=args.conf, fire_conf=args.fire_conf, smoke_conf=args.smoke_conf,
                        save_candidates=args.save_candidates, candidate_conf=args.candidate_conf,
                        iou=args.iou, image_size=args.imgsz, device=args.device,
                        window=args.window, min_hits=args.min_hits, clear_after=args.clear_after,
                        cooldown=args.cooldown, region_iou=args.region_iou, heartbeat=args.heartbeat,
                        max_regions=args.max_regions, max_seconds=args.max_seconds, max_frames=args.max_frames,
                        show=args.show, save_evidence=args.save_evidence, save_video=args.save_video,
                        save_preroll=args.save_preroll, preroll_seconds=args.preroll_seconds,
                        preroll_max_frames=args.preroll_max_frames, output_dir=args.output,
                        warmup=args.warmup, camera_retries=args.camera_retries,
                        camera_retry_delay=args.camera_retry_delay,
                        publish_alert_session=args.publish_alert_session,
                        production_camera=args.production_camera)
    report = run_live(config)
    print(f"[완료] {report['status']} | 수집 {report['captured_frames']}프레임 | "
          f"추론 {report['inference_samples']}회 | 의심 이벤트 {report['suspected_events']}건")
    return 0 if report["status"] not in ("ERROR", "CAMERA_READ_FAILED", "CAMERA_OPEN_FAILED", "VIDEO_OPEN_FAILED", "VIDEO_READ_FAILED", "SHARED_INPUT_UNAVAILABLE") else 1


if __name__ == "__main__":
    raise SystemExit(main())

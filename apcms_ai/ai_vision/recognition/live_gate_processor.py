# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_processor.py

"""실시간 카메라 프레임에서 차량을 추적하고, 기준선 통과 차량에만 OCR을 수행합니다.

처리 순서: 설정 검사 → 차량 추적 → ROI 확인 → crop 보관 → 기준선 통과 판정
→ 번호판 OCR → 여러 프레임의 OCR 결과 합의 → 통과 기록 반환.
이 모듈 자체는 HTTP 요청을 전송하지 않습니다.
"""

# 1. 필요한 모듈과 의존 기능 불러오기
# 1-1. os는 YOLO의 자동 설치 동작을 제한하기 위해 사용합니다.
import os
from math import isfinite
from datetime import datetime
# 1-2. deepcopy는 외부 설정 변경이 실행 중 설정에 영향을 주지 않게 합니다.
from copy import deepcopy
# 1-3. deque는 차량별 최근 crop을 양쪽에서 효율적으로 추가·삭제하는 자료구조입니다.
from collections import deque

# 1-4. 모델 위치, 통과선 판정기, OCR 다중 표본 집계, 설정 검사 함수를 재사용합니다.
from ai_vision.paths import MODEL_DIR
from ai_vision.recognition.model_files import require_model_file
from ai_vision.recognition.line_crossing import LineCrossingCounter
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.plate_review import sample_review_reasons
from ai_vision.recognition.tracking_config import validate_config
from ai_vision.recognition.live_gate_clock import FrameStamp


# 2. 실시간 차량 추적 및 번호판 처리기
class LiveGateProcessor:
    # 2-1. 실행 설정과 버퍼 용량을 초기화합니다.
    # tracker/plate_reader에 가짜 함수를 주입하면 실제 모델 없이 단위 테스트할 수 있습니다.
    def __init__(self, config, tracker=None, plate_reader=None, max_tracks=16, max_buffer_bytes=32 * 1024 * 1024):
        self.config = deepcopy(validate_config(config))
        # bool도 Python에서 int의 하위 타입이므로 type(...) is int로 엄격하게 검사합니다.
        if type(max_tracks) is not int or not 1 <= max_tracks <= 128 or type(max_buffer_bytes) is not int or max_buffer_bytes < 1:
            raise ValueError("차량·이미지 보관 한도를 확인해 주세요.")
        self._tracker, self._reader = tracker, plate_reader
        self._limit, self._budget = max_tracks, max_buffer_bytes
        # 각 ID별 이미지 목록, 마지막 관찰 시각, 현재 사용 중인 이미지 바이트 수입니다.
        self._buffers, self._last_seen, self._bytes = {}, {}, 0
        # YOLO는 최초 프레임 처리 시 로드하고, 화면 크기와 통과 판정기도 그때 결정합니다.
        self._model, self._shape, self._counter = None, None, None
        self._closed = False
        # 처리기 직접 호출에서도 과거 프레임을 다시 연결하지 않도록 마지막 순서를 보관합니다.
        self._last_frame_index, self._last_seconds = -1, None
        self._minimum_frame_index = 0
        self.dropped_crops = self.dropped_tracks = 0
        # 누적 통계는 처리 중 이미지 버퍼를 지워도 남습니다.
        self._statistics = {key: 0 for key in ("frames", "observations", "already_counted", "outside_roi",
                            "eligible", "gap_resets", "crossings", "ocr_calls", "peak_buffer_bytes",
                            "roi_resets", "speed_resets", "expired_history_crops")}

    # 3. 촬영 전에 모델을 준비할 때와 첫 추적 때 같은 객체를 재사용합니다.
    def _prepare_tracker(self):
        # 3-1. 실제 추적을 처음 실행할 때만 모델을 읽는 지연 로딩 방식입니다.
        if self._model is None:
            os.environ["YOLO_AUTOINSTALL"] = "false"
            model = MODEL_DIR / "yolo11n.pt"
            require_model_file(model)
            from ultralytics import YOLO
            self._model = YOLO(model)

    def prepare(self):
        # 카메라·세션 시계 시작 전에 무거운 모델 생성을 마칩니다. 실제 추론 예열은 아닙니다.
        if self._closed:
            raise ValueError("종료된 처리기는 준비할 수 없습니다.")
        if self._tracker is None:
            self._prepare_tracker()
        if self._reader is None:
            from ai_vision.recognition.recognizer import _models
            _models.plate()
            _models.ocr()

    def _track(self, frame):
        self._prepare_tracker()
        # 3-2. COCO 클래스 중 승용차·트럭·버스·오토바이만 추적합니다.
        classes = [key for key, name in self._model.names.items() if name in {"car", "truck", "bus", "motorcycle"}]
        # persist=True는 연속 프레임에서 이전 추적 상태를 유지하게 합니다.
        result = self._model.track(frame, persist=True, tracker=self.config["tracker"] + ".yaml",
                                   classes=classes, conf=.25, iou=.5, imgsz=640, verbose=False)[0]
        # 3-3. 연결된 ID가 없으면 차량 관찰 기록도 만들지 않습니다.
        if result.boxes.id is None:
            return []
        # 반환 예: [{"track_id": 3, "box": [x1, y1, x2, y2]}]
        return [{"track_id": int(box.id.item()), "box": list(map(int, box.xyxy[0].tolist()))} for box in result.boxes]

    # 4. 차량 이미지(crop)에서 번호판 읽기
    @staticmethod
    def _read_plate(crop):
        # 4-1. 차량 영역 내부에서 번호판 상자를 찾고, 그 부분만 잘라 OCR에 전달합니다.
        from ai_vision.recognition.recognizer import detect_best_plate, crop_plate_from_original, recognize_plate
        plate = detect_best_plate(crop)
        if plate is None:
            return {"plate_number": "", "plate_type": "NOT_DETECTED"}
        height, width = crop.shape[:2]
        image = crop_plate_from_original(crop, (0, 0, width, height), plate["box"])
        # 4-2. 빈 번호판 이미지를 OCR에 넣지 않습니다.
        if not image.size:
            return {"plate_number": "", "plate_type": "NOT_DETECTED"}
        # 번호판 탐지 신뢰도는 문자 OCR의 정답 확률과 다릅니다.
        return {**recognize_plate(image), "plate_detection_confidence": float(plate["confidence"])}

    # 5. 차량 한 대의 임시 이미지 버퍼 정리
    def _remove(self, track):
        # 5-1. 저장했던 crop의 크기만큼 전체 메모리 사용량을 차감합니다.
        entries = self._buffers.pop(track, deque())
        self._bytes -= sum(entry["crop"].nbytes for entry in entries)
        self._last_seen.pop(track, None)
        return entries

    # 6. 카메라 프레임 한 장 처리: 이 클래스의 핵심 메서드
    def process(self, frame, stamp, minimum_frame_index=None):
        # 6-1. 종료 여부와 입력 프레임 타입을 검증합니다.
        if self._closed:
            raise ValueError("종료된 프레임 처리기입니다.")
        import cv2
        import numpy as np
        if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or not frame.size:
            raise ValueError("카메라의 BGR uint8 프레임이 필요합니다.")
        # 6-1-1. 시각 오류를 crop 정리·추적기 호출보다 먼저 차단합니다.
        if (not isinstance(stamp, FrameStamp) or type(stamp.frame_index) is not int or
                stamp.frame_index <= self._last_frame_index or
                type(stamp.elapsed_seconds) not in (int, float) or not isfinite(stamp.elapsed_seconds) or
                stamp.elapsed_seconds < 0 or
                (self._last_seconds is not None and stamp.elapsed_seconds <= self._last_seconds) or
                not isinstance(stamp.captured_at, datetime) or stamp.captured_at.utcoffset() is None):
            raise ValueError("프레임 번호·시각이 유효하지 않거나 중복·역행했습니다.")
        if minimum_frame_index is not None and (type(minimum_frame_index) is not int or
                not self._minimum_frame_index <= minimum_frame_index <= stamp.frame_index):
            raise ValueError("시각을 검증할 수 있는 최소 프레임 번호가 올바르지 않습니다.")
        # 6-1-2. 한 번 만료된 시각 경계는 이후 호출에서 생략해도 되돌리지 않습니다.
        boundary = self._minimum_frame_index if minimum_frame_index is None else minimum_frame_index
        height, width = frame.shape[:2]
        # 6-2. 비율로 저장된 ROI와 기준선 좌표를 실제 픽셀 좌표로 변환합니다.
        if self._shape is None:
            self._shape = (height, width)
            self._roi = np.array([(int(self.config["roi"][i] * width), int(self.config["roi"][i + 1] * height))
                                  for i in range(0, 8, 2)], dtype=np.int32)
            self._counter = LineCrossingCounter(self.config["line_y"] * height,
                self.config["line_x"][0] * width, self.config["line_x"][1] * width, max_speed=height * 1.25)
        elif self._shape != (height, width):
            # 실행 중 해상도가 달라지면 좌표 기준도 달라지므로 새 세션을 요구합니다.
            raise ValueError("실행 중 카메라 해상도가 변경됐습니다. 새 세션이 필요합니다.")
        # 6-3. 너무 오래 관찰되지 않은 ID의 추적 상태와 crop을 정리합니다.
        seconds = stamp.elapsed_seconds
        self._counter.expire(seconds)
        for track in list(self._buffers):
            if seconds - self._last_seen[track] > self._counter.max_gap_seconds:
                self._remove(track)
                self._statistics["gap_resets"] += 1
                continue
            if boundary:
                # 6-3-1. 시각 기록에서 제거된 crop은 OCR 전에 버리고 메모리를 반납합니다.
                entries = self._buffers[track]
                while entries and entries[0]["frame_index"] < boundary:
                    self._bytes -= entries.popleft()["crop"].nbytes
                    self._statistics["expired_history_crops"] += 1
        # 6-4. 주입된 추적기가 있으면 사용하고, 없으면 실제 YOLO로 추적합니다.
        rows = list((self._tracker or self._track)(frame))
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("차량 추적 결과는 객체여야 합니다.")
            box = row.get("box")
            # 동일 프레임 ID 중복, 상자 좌표 역전, 화면 바깥 상자를 차단합니다.
            if (type(row.get("track_id")) is not int or row["track_id"] < 0 or row["track_id"] in seen or
                    not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box) or
                    not 0 <= box[0] < box[2] <= width or not 0 <= box[1] < box[3] <= height):
                raise ValueError("추적 ID·차량 상자가 유효하지 않거나 중복됐습니다.")
            seen.add(row["track_id"])
        # 검증된 입력만 다음 프레임의 순서 기준으로 사용합니다.
        self._last_frame_index, self._last_seconds = stamp.frame_index, seconds
        self._minimum_frame_index = boundary
        # 6-5. 관찰 횟수는 프레임마다 반복될 수 있으므로 실제 차량 대수와 다릅니다.
        self._statistics["frames"] += 1
        passages = []
        for row in rows:
            self._statistics["observations"] += 1
            track = row["track_id"]
            # 6-6. 이미 통과한 ID는 같은 실행에서 다시 처리하지 않습니다.
            if track in self._counter.counted_ids:
                self._statistics["already_counted"] += 1
                continue
            x1, y1, x2, y2 = row["box"]
            center = ((x1 + x2) / 2, (y1 + y2) / 2)
            # pointPolygonTest는 ROI 외부일 때 음수를 반환합니다.
            if cv2.pointPolygonTest(self._roi, center, False) < 0:
                self._statistics["outside_roi"] += 1
                # 6-6-1. ROI 밖 경로와 재진입 위치를 잇지 않도록 위치·crop을 함께 비웁니다.
                had_buffer = track in self._buffers
                had_state = self._counter.reset_track(track)
                self._remove(track)
                if had_buffer or had_state:
                    self._statistics["roi_resets"] += 1
                continue
            self._statistics["eligible"] += 1
            if self._counter.continuity_break_reason(track, center, seconds) == "SPEED":
                # 6-6-2. ID가 다른 차량으로 튄 듯하면 이전 OCR 표본도 연결하지 않습니다.
                self._counter.reset_track(track)
                self._remove(track)
                self._statistics["speed_resets"] += 1
            if len(self._counter.counted_ids) >= 10000:
                raise ValueError("세션의 통과 ID 한도에 도달했습니다.")
            # 6-7. 동시 보관 가능한 차량 수를 초과하면 새 차량의 crop은 건너뜁니다.
            if track not in self._buffers and len(self._buffers) >= self._limit:
                self.dropped_tracks += 1
                continue
            entries = self._buffers.setdefault(track, deque())
            self._last_seen[track] = seconds
            # 통과 시점 기준 이전 2초의 이미지 자료만 남깁니다.
            while entries and seconds - entries[0]["video_seconds"] > 2:
                self._bytes -= entries.popleft()["crop"].nbytes
            # 6-8. 같은 차량은 최소 0.25초 간격으로 최대 3장의 crop을 보관합니다.
            if not entries or seconds - entries[-1]["video_seconds"] >= .25 - 1e-9:
                if len(entries) >= 3:
                    self._bytes -= entries.popleft()["crop"].nbytes
                crop = frame[y1:y2, x1:x2]
                # 전체 프레임이 아니라 차량 상자 부분을 복사하며 전체 메모리 제한도 확인합니다.
                if self._bytes + crop.nbytes <= self._budget:
                    entries.append({"crop": crop.copy(), "frame_index": stamp.frame_index, "video_seconds": seconds})
                    self._bytes += crop.nbytes
                    self._statistics["peak_buffer_bytes"] = max(self._statistics["peak_buffer_bytes"], self._bytes)
                else:
                    self.dropped_crops += 1
            # 6-9. 차량 중심이 기준선을 실제로 넘어갔는지 판정합니다.
            event = self._counter.update(track, center, seconds)
            if event is None:
                continue
            self._statistics["crossings"] += 1
            samples = []
            # 6-10. 통과가 확인된 차량에 대해서만 저장한 crop들로 OCR을 수행합니다.
            for entry in self._remove(track):
                self._statistics["ocr_calls"] += 1
                result = (self._reader or self._read_plate)(entry["crop"])
                if not isinstance(result, dict):
                    raise ValueError("번호판 인식 결과는 객체여야 합니다.")
                sample = {"frame_index": entry["frame_index"], "video_seconds": entry["video_seconds"],
                          "plate_number": result.get("plate_number", ""), "plate_type": result.get("plate_type", "NOT_DETECTED")}
                sample["review_reasons"] = sample_review_reasons([sample])
                if "plate_detection_confidence" in result:
                    sample["plate_detection_confidence"] = result["plate_detection_confidence"]
                samples.append(sample)
            # 6-11. 여러 OCR 결과를 합의 판정해 통과 기록 한 건으로 묶습니다.
            # screen_direction은 화면상의 UP/DOWN이며 실제 ENTRY/EXIT는 다른 계층에서 연결합니다.
            passages.append({"record_type": "LIVE_TRACKED_PASSAGE", "http_enabled": False, "track_id": track,
                "screen_direction": event["direction"], "crossing_video_seconds": seconds,
                "samples": samples, "plate_consensus": summarize_plate_samples(samples)})
        return passages

    # 7. 누적 처리 통계 조회
    def statistics(self):
        # 7-1. 내부 통계 원본을 직접 돌려주지 않고 복사본을 반환합니다.
        return dict(self._statistics)

    # 8. 처리기 종료와 메모리 정리
    def close(self):
        # 8-1. 남은 모든 차량 crop을 해제하고 이후 프레임을 거부합니다.
        for track in list(self._buffers):
            self._remove(track)
        self._model = None
        self._closed = True

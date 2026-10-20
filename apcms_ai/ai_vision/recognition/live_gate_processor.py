# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_processor.py

"""카메라 프레임에서 추적·통과 판정 후 제한된 원본 차량 crop에만 OCR을 적용합니다."""

import os
from copy import deepcopy
from collections import deque

from ai_vision.paths import MODEL_DIR
from ai_vision.recognition.line_crossing import LineCrossingCounter
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.tracking_config import validate_config


class LiveGateProcessor:
    def __init__(self, config, tracker=None, plate_reader=None, max_tracks=16, max_buffer_bytes=32 * 1024 * 1024):
        self.config = deepcopy(validate_config(config))
        if type(max_tracks) is not int or not 1 <= max_tracks <= 128 or type(max_buffer_bytes) is not int or max_buffer_bytes < 1:
            raise ValueError("차량·이미지 보관 한도를 확인해 주세요.")
        self._tracker, self._reader = tracker, plate_reader
        self._limit, self._budget = max_tracks, max_buffer_bytes
        self._buffers, self._last_seen, self._bytes = {}, {}, 0
        self._model, self._shape, self._counter = None, None, None
        self._closed = False
        self.dropped_crops = self.dropped_tracks = 0
        self._statistics = {key: 0 for key in ("frames", "observations", "already_counted", "outside_roi",
                            "eligible", "gap_resets", "crossings", "ocr_calls", "peak_buffer_bytes")}

    def _track(self, frame):
        # 모델은 실제 프레임 처리 시에만 불러옵니다. 테스트에서는 추적 함수를 주입합니다.
        if self._model is None:
            os.environ["YOLO_AUTOINSTALL"] = "false"
            from ultralytics import YOLO
            model = MODEL_DIR / "yolo11n.pt"
            if not model.is_file():
                raise FileNotFoundError("차량 모델이 없습니다.")
            self._model = YOLO(model)
        classes = [key for key, name in self._model.names.items() if name in {"car", "truck", "bus", "motorcycle"}]
        result = self._model.track(frame, persist=True, tracker=self.config["tracker"] + ".yaml",
                                   classes=classes, conf=.25, iou=.5, imgsz=640, verbose=False)[0]
        if result.boxes.id is None:
            return []
        return [{"track_id": int(box.id.item()), "box": list(map(int, box.xyxy[0].tolist()))} for box in result.boxes]

    @staticmethod
    def _read_plate(crop):
        from ai_vision.recognition.recognizer import detect_best_plate, crop_plate_from_original, recognize_plate
        plate = detect_best_plate(crop)
        if plate is None:
            return {"plate_number": "", "plate_type": "NOT_DETECTED"}
        height, width = crop.shape[:2]
        image = crop_plate_from_original(crop, (0, 0, width, height), plate["box"])
        if not image.size:
            return {"plate_number": "", "plate_type": "NOT_DETECTED"}
        return {**recognize_plate(image), "plate_detection_confidence": float(plate["confidence"])}

    def _remove(self, track):
        entries = self._buffers.pop(track, deque())
        self._bytes -= sum(entry["crop"].nbytes for entry in entries)
        self._last_seen.pop(track, None)
        return entries

    def process(self, frame, stamp):
        if self._closed:
            raise ValueError("종료된 프레임 처리기입니다.")
        import cv2
        import numpy as np
        if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or not frame.size:
            raise ValueError("카메라의 BGR uint8 프레임이 필요합니다.")
        height, width = frame.shape[:2]
        if self._shape is None:
            self._shape = (height, width)
            self._roi = np.array([(int(self.config["roi"][i] * width), int(self.config["roi"][i + 1] * height))
                                  for i in range(0, 8, 2)], dtype=np.int32)
            self._counter = LineCrossingCounter(self.config["line_y"] * height,
                self.config["line_x"][0] * width, self.config["line_x"][1] * width, max_speed=height * 1.25)
        elif self._shape != (height, width):
            raise ValueError("실행 중 카메라 해상도가 변경됐습니다. 새 세션이 필요합니다.")
        seconds = stamp.elapsed_seconds
        self._counter.expire(seconds)
        for track in list(self._buffers):
            if seconds - self._last_seen[track] > self._counter.max_gap_seconds:
                self._remove(track)
                self._statistics["gap_resets"] += 1
        rows = list((self._tracker or self._track)(frame))
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("차량 추적 결과는 객체여야 합니다.")
            box = row.get("box")
            if (type(row.get("track_id")) is not int or row["track_id"] < 0 or row["track_id"] in seen or
                    not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box) or
                    not 0 <= box[0] < box[2] <= width or not 0 <= box[1] < box[3] <= height):
                raise ValueError("추적 ID·차량 상자가 유효하지 않거나 중복됐습니다.")
            seen.add(row["track_id"])
        # 2. 관찰 횟수는 같은 차량의 반복 검출을 포함하므로 실제 차량 수와 다릅니다.
        self._statistics["frames"] += 1
        passages = []
        for row in rows:
            self._statistics["observations"] += 1
            track = row["track_id"]
            if track in self._counter.counted_ids:
                self._statistics["already_counted"] += 1
                continue
            x1, y1, x2, y2 = row["box"]
            center = ((x1 + x2) / 2, (y1 + y2) / 2)
            if cv2.pointPolygonTest(self._roi, center, False) < 0:
                self._statistics["outside_roi"] += 1
                continue
            self._statistics["eligible"] += 1
            if len(self._counter.counted_ids) >= 10000:
                raise ValueError("세션의 통과 ID 한도에 도달했습니다.")
            if track not in self._buffers and len(self._buffers) >= self._limit:
                self.dropped_tracks += 1
                continue
            entries = self._buffers.setdefault(track, deque())
            self._last_seen[track] = seconds
            while entries and seconds - entries[0]["video_seconds"] > 2:
                self._bytes -= entries.popleft()["crop"].nbytes
            if not entries or seconds - entries[-1]["video_seconds"] >= .25 - 1e-9:
                if len(entries) >= 3:
                    self._bytes -= entries.popleft()["crop"].nbytes
                crop = frame[y1:y2, x1:x2]
                # 1. 전체 프레임 대신 원본 차량 crop 최대 3장/ID, 총 32MB만 보관합니다.
                if self._bytes + crop.nbytes <= self._budget:
                    entries.append({"crop": crop.copy(), "frame_index": stamp.frame_index, "video_seconds": seconds})
                    self._bytes += crop.nbytes
                    self._statistics["peak_buffer_bytes"] = max(self._statistics["peak_buffer_bytes"], self._bytes)
                else:
                    self.dropped_crops += 1
            event = self._counter.update(track, center, seconds)
            if event is None:
                continue
            self._statistics["crossings"] += 1
            samples = []
            for entry in self._remove(track):
                self._statistics["ocr_calls"] += 1
                result = (self._reader or self._read_plate)(entry["crop"])
                if not isinstance(result, dict):
                    raise ValueError("번호판 인식 결과는 객체여야 합니다.")
                sample = {"frame_index": entry["frame_index"], "video_seconds": entry["video_seconds"],
                          "plate_number": result.get("plate_number", ""), "plate_type": result.get("plate_type", "NOT_DETECTED")}
                if "plate_detection_confidence" in result:
                    sample["plate_detection_confidence"] = result["plate_detection_confidence"]
                samples.append(sample)
            passages.append({"record_type": "LIVE_TRACKED_PASSAGE", "http_enabled": False, "track_id": track,
                "screen_direction": event["direction"], "crossing_video_seconds": seconds,
                "samples": samples, "plate_consensus": summarize_plate_samples(samples)})
        return passages

    def statistics(self):
        # 3. 종료 시 crop을 비워도 누적 진단 수치는 보존합니다.
        return dict(self._statistics)

    def close(self):
        for track in list(self._buffers):
            self._remove(track)
        self._model = None
        self._closed = True

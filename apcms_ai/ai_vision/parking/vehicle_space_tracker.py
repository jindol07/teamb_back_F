# D:/finalProjectB/back/apcms_ai/ai_vision/parking/vehicle_space_tracker.py
"""한 카메라의 차량 관찰을 구획 체류·정차·번호판 근거에 연결합니다. 서버 전송은 하지 않습니다."""

import math
import unicodedata
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np

from ai_vision.parking.parking_validation import validate_spaces
from ai_vision.recognition.plate_consensus import summarize_plate_samples
from ai_vision.recognition.plate_review import KOREAN_PLATE_PATTERN


class VehicleSpaceTracker:
    def __init__(self, config, dwell_seconds=2, minimum_samples=4, max_gap=1,
                 maximum_speed=.025, max_tracks=32):
        # 1. 좌표는 이 카메라 영상의 픽셀입니다. 도면 좌표와 혼용하지 않습니다.
        self.config = deepcopy(validate_spaces(config))
        values = (dwell_seconds, max_gap, maximum_speed)
        if (any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values)
                or type(minimum_samples) is not int or not 3 <= minimum_samples <= 120
                or type(max_tracks) is not int or not 1 <= max_tracks <= 128):
            raise ValueError('체류 시간·연속 관찰·추적 한도를 확인하세요.')
        self.polygons = {s['id']: np.asarray(s['points'], dtype=np.float32) for s in self.config['spaces']}
        self.dwell, self.minimum, self.gap = dwell_seconds, minimum_samples, max_gap
        self.speed, self.limit = maximum_speed, max_tracks
        self.states = {}
        self.last_frame, self.last_time = -1, None
        self.diagonal = math.hypot(config['image_width'], config['image_height'])

    def _space(self, box):
        # 2. 차체 하단 중앙과 양옆 점이 모두 구획 안에 있어야 후보입니다.
        # 주차 자세·원근에 맞춘 실제 검증이 필요하며, 경계에 걸치면 보류합니다.
        x1, y1, x2, y2 = box
        points = [(x1 + (x2 - x1) * fraction, y2) for fraction in (.25, .5, .75)]
        matches = [key for key, polygon in self.polygons.items()
                   if all(cv2.pointPolygonTest(polygon, point, False) > 0 for point in points)]
        return matches[0] if len(matches) == 1 else None

    def _touching_spaces(self, box):
        # 구획을 걸쳐 선 차량도 다른 차량의 확정을 막는 관찰 근거로 사용합니다.
        x1, _, x2, y2 = box
        return {key for key, polygon in self.polygons.items() if any(
            cv2.pointPolygonTest(polygon, (x1 + (x2-x1)*fraction, y2), False) >= 0
            for fraction in (.25, .5, .75))}

    @staticmethod
    def _validate_sample(sample):
        if (not isinstance(sample, dict) or not isinstance(sample.get('plate_number'), str)
                or len(sample['plate_number']) > 128):
            raise ValueError('번호판 원문 문자열을 확인하세요.')
        summarize_plate_samples([sample])
        confidence = sample.get('plate_detection_confidence')
        if sample.get('plate_type') == 'KOREAN_VALID' and (
                type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise ValueError('유효 번호판에는 실제 탐지 점수가 필요합니다.')

    def process(self, frame_index, seconds, observations, completed_samples=(), eligible_spaces=None):
        # 3. 잘못된 입력은 상태를 바꾸기 전에 전부 검사합니다.
        if (type(frame_index) is not int or frame_index <= self.last_frame
                or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0
                or (self.last_time is not None and seconds <= self.last_time)
                or not isinstance(observations, list) or len(observations) > self.limit
                or not isinstance(completed_samples, (list, tuple)) or len(completed_samples) > self.limit):
            raise ValueError('프레임·시각·차량 목록이 유효하지 않습니다.')
        delayed = {}
        for job in completed_samples:
            if (not isinstance(job, dict) or type(job.get('track_id')) is not int or job['track_id'] < 0
                    or not isinstance(job.get('space_id'), str) or job['space_id'] not in self.polygons
                    or type(job.get('since')) not in (int, float) or not math.isfinite(job['since'])
                    or job['since'] < 0):
                raise ValueError('비동기 번호판의 원본 차량·구획 근거가 올바르지 않습니다.')
            sample = job.get('sample')
            self._validate_sample(sample)
            if (sample['frame_index'] > self.last_frame or self.last_time is None
                    or not job['since'] <= sample['video_seconds'] <= self.last_time):
                raise ValueError('관찰하지 않은 미래 프레임의 번호판 결과입니다.')
            delayed.setdefault(job['track_id'], []).append(job)
        prepared, seen = [], set()
        for row in observations:
            if not isinstance(row, dict):
                raise ValueError('차량 관찰 객체가 필요합니다.')
            track, box = row.get('track_id'), row.get('box')
            if (type(track) is not int or track < 0 or track in seen or not isinstance(box, (list, tuple))
                    or len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
                    or not 0 <= box[0] < box[2] < self.config['image_width']
                    or not 0 <= box[1] < box[3] < self.config['image_height']):
                raise ValueError('차량 ID 중복 또는 화면 밖 좌표를 확인하세요.')
            sample = row.get('plate_sample')
            if sample is not None:
                self._validate_sample(sample)
                # 외부 표본의 시각·프레임을 덮어쓰지 않고 동일 관찰인지 확인합니다.
                if sample.get('frame_index') != frame_index or sample.get('video_seconds') != seconds:
                    raise ValueError('번호판 표본이 현재 차량 관찰 시각과 다릅니다.')
            seen.add(track)
            prepared.append((track, box, sample, self._space(box), self._touching_spaces(box)))
        active = {key for key, value in self.states.items() if seconds - value['seen'] <= self.gap}
        if len(active | seen) > self.limit:
            raise ValueError('유지할 차량 수가 추적 한도를 초과했습니다.')
        events = []
        if eligible_spaces is not None and (not isinstance(eligible_spaces, (set, frozenset))
                or not eligible_spaces <= self.polygons.keys()):
            raise ValueError('같은 관찰 시각의 점유 구획 목록을 확인하세요.')
        def emit(kind, track, space, number='', confidence=None):
            events.append({'kind': kind, 'track_id': track, 'space_id': space,
                           'plate_number': number, 'frame_index': frame_index,
                           'video_seconds': seconds, 'http_enabled': False,
                           'plate_detection_confidence': confidence})
        for track in list(self.states):
            state = self.states[track]
            if seconds - state['seen'] > self.gap:
                emit('TRACK_LOST', track, state['matched'] or state['space'])
                del self.states[track]  # 보이지 않는 차량을 출차·빈자리로 처리하지 않습니다.
            elif track not in seen:
                # 짧은 가림에도 현재 연결은 철회합니다. ID 보존과 번호판 근거 보존은 다릅니다.
                if state['matched'] is not None:
                    emit('MATCH_REVIEW', track, state['matched'], state['number'])
                state.update(count=0, samples=[], matched=None, number='', interrupted=True)
        counts = {space: sum(space in item[4] for item in prepared) +
                  sum(key not in seen and value['space'] == space for key, value in self.states.items())
                  for space in self.polygons}
        for track, box, sample, space, _ in prepared:
            center = ((box[0] + box[2]) / 2, box[3])
            state = self.states.get(track)
            if state is None:
                state = {'seen': seconds, 'point': center, 'space': None, 'since': seconds,
                         'count': 0, 'samples': [], 'matched': None, 'number': '', 'reviewed': False}
                self.states[track] = state
            dt = seconds - state['seen']
            speed = math.dist(center, state['point']) / self.diagonal / dt if dt > 0 else 0
            stationary = speed <= self.speed
            previous = state['space']
            interrupted = state.pop('interrupted', False)
            if previous != space or not stationary or interrupted:
                state['since'], state['count'], state['samples'] = seconds, 0, []
                state['reviewed'] = False
            if state['matched'] is not None and (state['matched'] != space or not stationary):
                emit('MATCH_REVIEW', track, state['matched'], state['number'])
                state['matched'], state['number'] = None, ''
            if space != previous:
                if previous is not None:
                    emit('LEFT_SPACE_CANDIDATE', track, previous)
                if space is not None:
                    emit('ENTERED_SPACE', track, space)
            state.update(seen=seconds, point=center, space=space)
            occupancy_blocked = eligible_spaces is not None and space not in eligible_spaces
            if space is None or counts[space] > 1 or occupancy_blocked:
                # 4. 한 구획에 여러 ID가 있으면 번호를 어느 차량에 배정할지 추측하지 않습니다.
                if space is not None and counts[space] > 1:
                    emit('AMBIGUOUS_SPACE', track, space)
                if state['matched'] is not None:
                    emit('MATCH_REVIEW', track, state['matched'], state['number'])
                state.update(since=seconds, count=0, samples=[], matched=None, number='')
                if occupancy_blocked:
                    state['interrupted'] = True
                continue
            state['count'] += 1
            if sample is not None:
                state['samples'].append(deepcopy(sample))
            # 4-1. 늦은 OCR을 현재 프레임으로 바꾸지 않습니다. 같은 정차 구간의 원본 표본만 반영합니다.
            for job in delayed.get(track, []):
                if job['space_id'] == space and job['since'] == state['since']:
                    state['samples'].append(deepcopy(job['sample']))
            state['samples'] = state['samples'][-12:]
            consensus = summarize_plate_samples(state['samples'])
            if consensus['status'] == 'CONFLICT':
                if not state['reviewed']:
                    emit('PLATE_CONFLICT', track, space)
                state.update(matched=None, number='', reviewed=True)
                continue
            if state['reviewed']:
                continue
            if (stationary and seconds - state['since'] >= self.dwell and state['count'] >= self.minimum
                    and consensus['status'] == 'CONFIRMED' and state['matched'] is None):
                number = consensus['plate_number']
                other = [key for key, value in self.states.items()
                         if key != track and value['matched'] is not None and value['number'] == number]
                if other:
                    emit('DUPLICATE_PLATE_REVIEW', track, space, number)
                    state['reviewed'] = True
                    for key in other:
                        prior = self.states[key]
                        emit('MATCH_REVIEW', key, prior['matched'], number)
                        prior.update(matched=None, number='', reviewed=True)
                    continue
                # 문자 정답 확률이 아니라, 일치 번호를 지지한 번호판 탐지 점수의 최솟값입니다.
                confidence = min(s['plate_detection_confidence'] for s in state['samples']
                                 if s.get('plate_type') == 'KOREAN_VALID' and
                                 ''.join(unicodedata.normalize('NFC', s['plate_number']).split()) == number)
                emit('LOCAL_SPACE_MATCH', track, space, number, confidence)
                state.update(matched=space, number=number)
        self.last_frame, self.last_time = frame_index, seconds
        return events


def create_vehicle_tracker():
    # 7. 저장 영상과 실시간 구획 관찰에서 같은 차량 모델·추적 설정을 사용합니다.
    import os
    from ai_vision.paths import MODEL_DIR
    from ai_vision.recognition.model_files import require_model_file
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    from ultralytics import YOLO
    require_model_file(MODEL_DIR / 'yolo11n.pt')
    model = YOLO(MODEL_DIR / 'yolo11n.pt')
    classes = [key for key, name in model.names.items() if name in {'car', 'truck', 'bus', 'motorcycle'}]
    if not classes:
        raise ValueError('차량 탐지 클래스가 없습니다.')

    def track(frame):
        result = model.track(frame, persist=True, tracker='bytetrack.yaml', classes=classes,
                             conf=.25, imgsz=640, verbose=False)[0]
        return [] if result.boxes.id is None else [
            {'track_id': int(box.id.item()), 'box': list(map(int, box.xyxy[0].tolist()))}
            for box in result.boxes]
    return model, track


class VehicleSpaceObserver:
    """차량 추적은 호출 스레드에서, 번호판 인식 한 건은 작업 스레드에서 처리합니다."""

    def __init__(self, config, tracker=None, plate_reader=None, max_crop_bytes=8 * 1024 * 1024):
        from concurrent.futures import ThreadPoolExecutor
        if type(max_crop_bytes) is not int or max_crop_bytes < 1:
            raise ValueError('번호판 작업 이미지의 메모리 한도를 확인하세요.')
        self.tracker = VehicleSpaceTracker(config)
        self._track, self._reader = tracker, plate_reader
        self._model = self._pending = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='parking-ocr')
        self._budget, self._last_submit = max_crop_bytes, {}
        self._closed = False
        self._current_observed = False
        self._duplicate_times = 0
        self._submitted = self._completed = self._abandoned = self._oversize = self._peak = 0

    def prepare(self):
        if self._closed:
            raise ValueError('종료된 차량 관찰기입니다.')
        if self._track is None:
            self._model, self._track = create_vehicle_tracker()
        if self._reader is None:
            from ai_vision.recognition.live_gate_processor import LiveGateProcessor
            from ai_vision.recognition.recognizer import _models
            _models.plate()
            _models.ocr()
            self._reader = LiveGateProcessor._read_plate

    def _recognize(self, job, crop):
        result = self._reader(crop)
        if not isinstance(result, dict):
            raise ValueError('번호판 인식 결과 객체가 필요합니다.')
        sample = {**result, 'frame_index': job['frame_index'], 'video_seconds': job['video_seconds']}
        self.tracker._validate_sample(sample)
        return {key: job[key] for key in ('track_id', 'space_id', 'since')} | {'sample': sample}

    def process(self, frame_index, seconds, frame, eligible_spaces=None):
        if self._closed or self._track is None or self._reader is None:
            raise ValueError('차량 관찰기를 준비한 뒤 사용하세요.')
        from ai_vision.parking.parking_calibration import validate_frame_resolution
        validate_frame_resolution(frame, self.tracker.config['image_width'], self.tracker.config['image_height'])
        self._current_observed = False
        if (type(frame_index) is not int or frame_index <= self.tracker.last_frame
                or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0
                or (self.tracker.last_time is not None and seconds < self.tracker.last_time)):
            raise ValueError('차량 관찰 프레임·시각을 확인하세요.')
        if self.tracker.last_time == seconds:
            self._duplicate_times += 1
            return {'events': [], 'observations': [], 'completed_samples': []}
        completed = []
        if self._pending is not None and self._pending.done():
            future, self._pending = self._pending, None
            completed.append(future.result())
            self._completed += 1
        rows = self._track(frame)
        if not isinstance(rows, list) or len(rows) > self.tracker.limit:
            raise ValueError('차량 관찰 목록의 형식 또는 한도가 올바르지 않습니다.')
        valid = []
        for row in rows:
            if (not isinstance(row, dict) or not isinstance(row.get('box'), (list, tuple))
                    or len(row['box']) != 4 or any(type(n) is not int for n in row['box'])):
                raise ValueError('차량 탐지 좌표가 올바르지 않습니다.')
            x1, y1, x2, y2 = row['box']
            if 0 <= x1 < x2 < frame.shape[1] and 0 <= y1 < y2 < frame.shape[0]:
                valid.append(row)
        events = self.tracker.process(frame_index, seconds, valid, completed_samples=completed,
                                      eligible_spaces=eligible_spaces)
        self._current_observed = True
        self._last_submit = {key: value for key, value in self._last_submit.items()
                             if key[0] in self.tracker.states and
                             self.tracker.states[key[0]]['since'] == key[1]}
        if self._pending is None:
            candidates = []
            for row in valid:
                state = self.tracker.states[row['track_id']]
                key = (row['track_id'], state['since'])
                previous = self._last_submit.get(key, -math.inf)
                if (state['space'] is not None and state['count'] > 0 and not state['reviewed']
                        and seconds - previous >= .5):
                    candidates.append((previous, row, state, key))
            # 오래 기다린 차량부터 처리하며 실행 중 작업을 포함해 한 건만 유지합니다.
            for _, row, state, key in sorted(candidates, key=lambda item: item[0]):
                x1, y1, x2, y2 = row['box']
                size = (x2 - x1) * (y2 - y1) * 3
                if size > self._budget:
                    self._oversize += 1
                    continue
                crop = frame[y1:y2, x1:x2].copy()
                job = {'track_id': row['track_id'], 'space_id': state['space'], 'since': state['since'],
                       'frame_index': frame_index, 'video_seconds': seconds}
                self._pending = self._executor.submit(self._recognize, job, crop)
                self._last_submit[key] = seconds
                self._submitted += 1
                self._peak = max(self._peak, size)
                break
        progress = []
        for row in valid:
            state = self.tracker.states[row['track_id']]
            space = state['space']
            if space is None:
                status = 'OUTSIDE_SPACE'
            elif eligible_spaces is not None and space not in eligible_spaces:
                status = 'WAIT_OCCUPANCY'
            elif state['reviewed']:
                status = 'PLATE_CONFLICT'
            elif state['count'] == 0:
                status = 'AMBIGUOUS_SPACE'
            elif state['matched'] is not None:
                status = 'LOCAL_MATCH'
            elif seconds - state['since'] < self.tracker.dwell or state['count'] < self.tracker.minimum:
                status = 'WAIT_DWELL'
            else:
                status = 'WAIT_PLATE'
            latest = state['samples'][-1] if state['samples'] else {}
            progress.append({'track_id': row['track_id'], 'box': list(row['box']), 'space_id': space,
                             'status': status, 'plate_number': state['number'] or latest.get('plate_number', ''),
                             'plate_type': latest.get('plate_type'),
                             'video_seconds': seconds})
        return {'events': events, 'observations': valid, 'completed_samples': completed, 'progress': progress}

    def current_matches(self, occupancy, seconds):
        if self._closed or not self._current_observed or self.tracker.last_time != seconds:
            return []
        eligible = occupancy.matching_spaces(seconds)
        return [{'track_id': key, 'space_id': value['matched'], 'plate_number': value['number']}
                for key, value in self.tracker.states.items()
                if value['seen'] == seconds and value['matched'] in eligible]

    def summary(self):
        return {'ocr_submitted': self._submitted, 'ocr_completed': self._completed,
                'ocr_abandoned': self._abandoned, 'oversize_crops': self._oversize,
                'pending_ocr': self._pending is not None, 'peak_crop_bytes': self._peak,
                'duplicate_time_frames': self._duplicate_times,
                'closed': self._closed}

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=True)
        self._model = None
        self._track = None
        if self._pending is not None:
            future, self._pending = self._pending, None
            self._abandoned += 1
            if not future.cancelled() and future.exception() is not None:
                raise RuntimeError('종료 대기 중 번호판 인식 작업이 실패했습니다.')


def review_match_context(report, context, recording_started_at=None):
    """기존 Boot 조회 응답의 사본과 로컬 연결을 대조합니다. 예약 승인·전송 허용은 하지 않습니다."""
    # 6. 녹화 시각은 호출자가 실제 촬영 기록에서 제공해야 합니다. 분석 시각으로 대체하지 않습니다.
    def aware_time(value):
        if not isinstance(value, str):
            raise ValueError('타임존이 포함된 촬영·조회 시각이 필요합니다.')
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            raise ValueError('촬영·조회 시각의 타임존이 없습니다.')
        return parsed

    output = {'decision': 'HELD', 'http_enabled': False, 'reservation_checked': False,
              'camera_occupancy_checked': False, 'items': [], 'reason': None}
    if (not isinstance(report, dict) or report.get('record_type') != 'LOCAL_VEHICLE_SPACE_TRACKING'
            or report.get('status') not in ('COMPLETED', 'LIMIT_REACHED') or report.get('http_enabled') is not False):
        output['reason'] = 'INVALID_OR_FAILED_LOCAL_RUN'
        return output
    matches = report.get('current_matches')
    if not isinstance(matches, list) or len(matches) > 128:
        output['reason'] = 'INVALID_MATCH_LIST'
        return output
    if not matches:
        output['reason'] = 'NO_CURRENT_MATCH'
        return output
    # 6-1. 저장 결과를 다시 읽을 때도 번호판 형식을 검사합니다. 조회 사본의 같은 오독은 근거가 아닙니다.
    if any(not isinstance(row, dict) or not isinstance(row.get('plate_number'), str)
           or len(row['plate_number']) > 128 for row in matches):
        output['reason'] = 'INVALID_MATCH_LIST'
        return output
    matches = [{**row, 'plate_number': ''.join(unicodedata.normalize('NFC', row['plate_number']).split())}
               for row in matches]
    if any(not KOREAN_PLATE_PATTERN.fullmatch(row['plate_number']) for row in matches):
        output['reason'] = 'INVALID_MATCH_LIST'
        return output
    # 중복 ID·번호·구획은 사본을 손으로 편집했더라도 연결 근거로 인정하지 않습니다.
    for key in ('track_id', 'plate_number', 'space_id'):
        values = [row.get(key) for row in matches if isinstance(row, dict)]
        invalid_values = (any(type(v) is not int or v < 0 for v in values) if key == 'track_id'
                          else any(not isinstance(v, str) or not v for v in values))
        if len(values) != len(matches) or invalid_values:
            output['reason'] = 'INVALID_MATCH_LIST'
            return output
        if len(set(values)) != len(values):
            output['reason'] = 'AMBIGUOUS_MATCH_LIST'
            return output
    from ai_vision.parking.parking_event_sender import convert_space_code
    # 로컬 ID가 달라도 같은 DB 구획으로 변환되면 두 차량의 연결을 동시에 인정하지 않습니다.
    mapped = []
    for match in matches:
        try:
            mapped.append(convert_space_code(match['space_id']))
        except (ValueError, TypeError):
            continue  # 미등록 구획은 아래 개별 대조에서 보류합니다.
    if len(set(mapped)) != len(mapped):
        output['reason'] = 'AMBIGUOUS_MATCH_LIST'
        return output
    try:
        elapsed = report.get('last_video_seconds')
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError('영상 시각이 없습니다.')
        observed = aware_time(recording_started_at) + timedelta(seconds=elapsed)
    except (ValueError, TypeError, OverflowError):
        output['reason'] = 'OBSERVATION_TIME_UNKNOWN'
        return output
    try:
        if not isinstance(context, dict):
            raise ValueError('조회 사본 객체가 필요합니다.')
        fetched = aware_time(context.get('fetched_at'))
        usages, spaces = context.get('active_usages'), context.get('spaces')
        if (not isinstance(usages, list) or not isinstance(spaces, list) or
                len(usages) > 10000 or len(spaces) > 10000 or
                any(not isinstance(row, dict) for row in usages + spaces)):
            raise ValueError('조회 응답 목록이 올바르지 않습니다.')
    except (ValueError, TypeError):
        output['reason'] = 'BOOT_CONTEXT_INVALID'
        return output
    # 6-2. 실제 active 조회는 EXIT_AT IS NULL입니다. 빈 문자열·누락·과거 출차 행을 섞지 않습니다.
    if any('exitAt' not in row or row['exitAt'] is not None for row in usages):
        output['reason'] = 'BOOT_ACTIVE_USAGES_INVALID'
        return output
    # 응답 사본의 중복 PK·구획 코드는 어떤 행을 고를지 추측하지 않고 전체 보류합니다.
    for rows, key in ((usages, 'parkingUsageId'), (spaces, 'parkingSpaceId'), (spaces, 'spaceCode')):
        values = [row.get(key) for row in rows]
        # 누락·잘못된 값은 기존 개별 검증에 맡기고, 유효한 식별자의 중복부터 확인합니다.
        if key == 'spaceCode':
            valid = [v for v in values if isinstance(v, str) and v]
        else:
            valid = [v for v in values if type(v) is int and v > 0]
        if len(set(valid)) != len(valid):
            output['reason'] = 'AMBIGUOUS_BOOT_CONTEXT'
            return output
    # 이 사본은 관찰 후 15초 이내 조회여야 합니다. 과거 영상에 현재 DB를 끼워 맞추지 않습니다.
    if not 0 <= (fetched - observed).total_seconds() <= 15:
        output['reason'] = 'BOOT_CONTEXT_OUTSIDE_OBSERVATION_WINDOW'
        return output
    for match in matches:
        item = {'track_id': match.get('track_id') if isinstance(match, dict) else None,
                'decision': 'HELD', 'reason': None}
        output['items'].append(item)
        try:
            if not isinstance(match, dict) or not isinstance(match.get('plate_number'), str):
                raise ValueError('연결 근거가 없습니다.')
            code = convert_space_code(match.get('space_id'))
        except (ValueError, TypeError):
            item['reason'] = 'SPACE_MAPPING_OR_PLATE_INVALID'
            continue
        number = match['plate_number']
        found = [row for row in usages if row.get('vehicleNumber') == number and row.get('exitAt') is None]
        target = [row for row in spaces if row.get('spaceCode') == code]
        item.update(plate_number=number, space_code=code)
        if len(found) != 1:
            item['reason'] = 'ACTIVE_USAGE_MISSING_OR_AMBIGUOUS'
            continue
        if len(target) != 1:
            item['reason'] = 'SPACE_MISSING_OR_AMBIGUOUS'
            continue
        usage, space = found[0], target[0]
        if ('parkingSpaceId' not in usage or 'exitAt' not in usage
                or 'vehicleNumber' not in space
                or (usage.get('parkingSpaceId') is not None and
                    (type(usage['parkingSpaceId']) is not int or usage['parkingSpaceId'] <= 0))
                or type(usage.get('parkingUsageId')) is not int or usage['parkingUsageId'] <= 0
                or type(space.get('parkingSpaceId')) is not int or space['parkingSpaceId'] <= 0):
            item['reason'] = 'INVALID_DATABASE_IDENTIFIERS'
            continue
        try:
            # Boot entryAt은 KST의 타임존 없는 조회 문자열입니다. 촬영 시각과 비교할 때만 명시합니다.
            entered = datetime.fromisoformat(usage['entryAt'])
            if entered.utcoffset() is None:
                entered = entered.replace(tzinfo=timezone(timedelta(hours=9)))
        except (ValueError, KeyError, TypeError):
            item['reason'] = 'ENTRY_TIME_INVALID'
            continue
        if entered > observed:
            item['reason'] = 'OBSERVED_BEFORE_ENTRY'
        elif space.get('spaceStatusCode') != 'OCCUPIED':
            item['reason'] = 'SPACE_NOT_OCCUPIED_OR_PROTECTED'
        elif usage.get('parkingSpaceId') not in (None, space['parkingSpaceId']):
            item['reason'] = 'VEHICLE_ALREADY_LINKED_ELSEWHERE'
        elif any(row.get('parkingSpaceId') == space['parkingSpaceId'] and not row.get('exitAt')
                 and row.get('parkingUsageId') != usage['parkingUsageId'] for row in usages):
            item['reason'] = 'SPACE_LINKED_TO_OTHER_USAGE'
        elif space.get('vehicleNumber') not in (None, '', number):
            item['reason'] = 'SPACE_VEHICLE_CONFLICT'
        else:
            item.update(decision='CONTEXT_MATCHED_LOCAL_ONLY', reason='RESERVATION_AND_LIVE_EVIDENCE_REQUIRED',
                        parking_usage_id=usage['parkingUsageId'], parking_space_id=space['parkingSpaceId'])
    if output['items'] and all(item['decision'] == 'CONTEXT_MATCHED_LOCAL_ONLY' for item in output['items']):
        output['decision'] = 'CONTEXT_MATCHED_LOCAL_ONLY'
    else:
        output['reason'] = 'ITEMS_HELD'
    return output

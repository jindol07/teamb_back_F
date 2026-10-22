# D:/finalProjectB/back/apcms_ai/ai_vision/parking/parking_processor.py

"""동일 구도의 프레임을 분석하고 연속 관찰로 확정된 점유 변경만 이벤트로 만듭니다."""

import math
from copy import deepcopy

import cv2
import numpy as np

from ai_vision.parking.parking_validation import validate_spaces, validate_occupancy
from ai_vision.parking.parking_event_sender import create_occupancy_event, convert_space_code

MAX_MASK_BYTES = 64 * 1024 * 1024

class ParkingOccupancyProcessor:
    def __init__(self, reference, config, detector, stable_frames=5, minimum_interval=.5,
                 max_gap_seconds=2, max_mask_bytes=MAX_MASK_BYTES, emit_events=True):
        # 1. 카메라를 열기 전에 이미지·좌표·구획 매핑과 메모리 한도를 검사합니다.
        config = deepcopy(validate_spaces(config))
        if (not isinstance(reference, np.ndarray) or reference.dtype != np.uint8 or reference.ndim != 3 or
                reference.shape[2] != 3 or reference.shape[:2] != (config['image_height'], config['image_width'])):
            raise ValueError("기준 이미지와 주차면 좌표의 해상도가 일치해야 합니다.")
        if (type(stable_frames) is not int or not 2 <= stable_frames <= 120 or not callable(detector)
                or type(emit_events) is not bool):
            raise ValueError("연속 확정 횟수와 점유 분석 함수를 확인하세요.")
        if (any(type(value) not in (int, float) or not math.isfinite(value) for value in (minimum_interval, max_gap_seconds)) or
                not 0 < minimum_interval <= max_gap_seconds <= 300):
            raise ValueError("분석 간격과 관찰 공백 한도를 확인하세요.")
        required = config['image_width'] * config['image_height'] * len(config['spaces'])
        if type(max_mask_bytes) is not int or not 0 < required <= max_mask_bytes:
            raise ValueError("주차면 마스크 메모리 한도를 초과했습니다.")
        self.spaces = []
        for item in config['spaces']:
            convert_space_code(item['id'])
            points = np.array(item['points'], dtype=np.int32)
            mask = np.zeros(reference.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [points], 255)
            mask = cv2.erode(mask, np.ones((7, 7), dtype=np.uint8))
            if not cv2.countNonZero(mask):
                raise ValueError("축소 후 주차면 분석 영역이 남아 있지 않습니다.")
            self.spaces.append({'id': item['id'], 'points': points, 'mask': mask})
        self.reference_gray = cv2.GaussianBlur(cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        self._shape, self._detector = reference.shape, detector
        self._stable, self._interval, self._gap = stable_frames, minimum_interval, max_gap_seconds
        self._emit_events = emit_events
        self.states = {space['id']: {'previous': None, 'same_count': 0, 'confirmed': None, 'change_ratio': 0.0}
                       for space in self.spaces}
        self._last_call = self._last_sample = None
        self._samples = self._changes = self._gap_resets = 0

    def process(self, frame, seconds):
        # 2. 입력을 먼저 검증하고 유효한 관찰만 연속 횟수에 반영합니다.
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.shape != self._shape):
            raise ValueError("현재 프레임과 기준 사진의 해상도·색상 형식이 달라 비교할 수 없습니다.")
        if (type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0 or
                (self._last_call is not None and seconds < self._last_call)):
            raise ValueError("주차 관찰 시각이 유효하지 않거나 역행했습니다.")
        if self._last_sample is not None and seconds - self._last_sample < self._interval - 1e-9:
            self._last_call = seconds
            return {'sampled': False, 'changes': [], 'events': []}
        results = self._detector(self.reference_gray, frame, self.spaces)
        if not isinstance(results, list):
            raise ValueError("주차 분석 결과 목록이 필요합니다.")
        occupied = sum(row.get('status') == 'OCCUPIED' for row in results if isinstance(row, dict))
        validate_occupancy({'total_spaces': len(results), 'occupied_count': occupied,
                            'empty_count': len(results) - occupied, 'spaces': results})
        if {row['space_id'] for row in results} != set(self.states):
            raise ValueError("분석 결과의 주차면 목록이 설정과 다릅니다.")
        if self._last_sample is not None and seconds - self._last_sample > self._gap:
            # 긴 관찰 공백을 사이에 둔 프레임을 연속 관찰로 연결하지 않습니다.
            for state in self.states.values():
                state['previous'], state['same_count'] = None, 0
            self._gap_resets += 1
        changes, events = [], []
        for result in results:
            state = self.states[result['space_id']]
            status = result['status']
            state['same_count'] = min(self._stable, state['same_count'] + 1) if state['previous'] == status else 1
            state['previous'] = status
            if state['same_count'] < self._stable or status == state['confirmed']:
                continue
            old = state['confirmed']
            state['confirmed'], state['change_ratio'] = status, result['change_ratio']
            changes.append({**result, 'previous_status': old})
            # 3. 생성만 합니다. 네트워크 전송이나 대기 파일 등록은 호출자가 선택합니다.
            if self._emit_events:
                events.append(create_occupancy_event(result['space_id'], status, result['change_ratio']))
        self._last_call = self._last_sample = seconds
        self._samples += 1
        self._changes += len(changes)
        return {'sampled': True, 'changes': changes, 'events': events}

    def confirmed_results(self):
        if any(state['confirmed'] is None for state in self.states.values()):
            return None
        return [{'space_id': key, 'status': value['confirmed'], 'change_ratio': value['change_ratio']}
                for key, value in self.states.items()]

    def matching_spaces(self, seconds):
        # 4. 화면 표시용 마지막 확정값과 현재 차량 연결에 쓸 연속 근거를 구분합니다.
        if (type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0
                or (self._last_call is not None and seconds < self._last_call)):
            raise ValueError('점유 근거 조회 시각이 유효하지 않습니다.')
        if self._last_sample is None or seconds - self._last_sample > self._gap:
            return set()
        return {key for key, state in self.states.items()
                if state['confirmed'] == state['previous'] == 'OCCUPIED'
                and state['same_count'] >= self._stable}

    def occupancy(self):
        results = self.confirmed_results()
        if results is None:
            return None
        occupied = sum(row['status'] == 'OCCUPIED' for row in results)
        return validate_occupancy({'total_spaces': len(results), 'occupied_count': occupied,
                                   'empty_count': len(results) - occupied, 'spaces': results})

    def statistics(self):
        return {'analyzed_frames': self._samples, 'state_changes': self._changes, 'gap_resets': self._gap_resets,
                'unconfirmed_space_ids': [key for key, value in self.states.items() if value['confirmed'] is None]}

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/single_vehicle_handoff.py
"""한 대 시연 전용 입차 신원 전달. 한 A 실행만 파일을 쓰고 B는 읽기만 합니다."""

import json
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ai_vision.recognition.local_io import read_json, write_json_atomic
from ai_vision.recognition.vehicle_contract import parse_detected_at, validate_camera_id, validate_vehicle_payload


class SingleVehicleHandoff:
    def __init__(self, path, session_id, camera_id, at):
        validate_camera_id(camera_id)
        self.path = Path(path)
        self.state = {'record_type': 'SINGLE_VEHICLE_HANDOFF', 'owner_session_id': session_id,
                      'camera_id': camera_id, 'status': 'EMPTY', 'active': None,
                      'updated_at': at.isoformat(), 'reason': None, 'last_exit': None}
        # 1. 이전 실행의 파일을 덮어쓰거나 이전 차량을 자동 복원하지 않습니다.
        with self.path.open('x', encoding='utf-8') as stream:
            json.dump(self.state, stream, ensure_ascii=False)
        self._at = at

    def _save(self, at):
        # 비동기 OCR은 과거 수집 시각으로 완료될 수 있으므로 heartbeat 시각을 되돌리지 않습니다.
        at = max(at, self._at)
        self._at = at
        self.state['updated_at'] = at.isoformat()
        write_json_atomic(self.path, self.state)

    def heartbeat(self, at):
        if (at-self._at).total_seconds() >= .5:
            self._save(at)

    def allow(self, event, at):
        event = validate_vehicle_payload(event)
        active = self.state['active']
        if event['direction'] == 'ENTRY':
            if active is not None:
                if active['plate_number'] != event['plate_number']:
                    self.state.update(status='BLOCKED', reason='SECOND_VEHICLE_OBSERVED')
                    self._save(at)
                return False
            return self.state['status'] == 'EMPTY'
        # 다른 차량·이용의 출차로 현재 차량을 지우지 않습니다.
        return (self.state['status'] in ('ACTIVE', 'BLOCKED') and active is not None
                and active['plate_number'] == event['plate_number']
                and parse_detected_at(event['detected_at']) >= parse_detected_at(active['detected_at']))

    def record(self, event, receipt, at):
        active = self.state['active']
        usage = receipt.get('parking_usage_id')
        if (receipt.get('receipt_verified') is not True or receipt.get('request_attempted') is not True
                or receipt.get('event_id') != event['event_id']
                or receipt.get('event_type') != 'VEHICLE_PASSAGE'
                or receipt.get('state') not in ('APPLIED', 'UNCHANGED')
                or type(usage) is not int or usage < 1):
            self.state.update(status='BLOCKED', reason='PASSAGE_NOT_VERIFIED')
        elif event['direction'] == 'ENTRY' and active is None:
            self.state.update(status='ACTIVE', reason=None, active={
                'plate_number': event['plate_number'], 'parking_usage_id': usage,
                'event_id': event['event_id'], 'detected_at': event['detected_at'],
                'confidence': event['confidence']})
        elif (event['direction'] == 'EXIT' and receipt['state'] == 'APPLIED' and active is not None
              and active['plate_number'] == event['plate_number'] and active['parking_usage_id'] == usage):
            self.state.update(status='EMPTY', active=None, reason=None, last_exit={
                'plate_number': event['plate_number'], 'parking_usage_id': usage,
                'event_id': event['event_id'], 'detected_at': event['detected_at']})
        else:
            self.state.update(status='BLOCKED', reason='USAGE_ID_MISMATCH')
        self._save(at)

    def close(self, at):
        self.state.update(status='CLOSED', active=None, reason='SOURCE_STOPPED')
        self._save(at)


class SingleVehicleHandoffReader:
    def __init__(self, path, clock=None):
        self.path, self.clock = Path(path), clock or (lambda: datetime.now(timezone.utc))
        self.owner, self.last_at = None, None
        self.status = 'WAIT_ENTRY'
        self.last_exit = None

    def read(self):
        # 2. 손상·만료·출차·종료는 이전 번호를 반환하지 않습니다.
        self.status = 'WAIT_ENTRY'
        self.last_exit = None
        try:
            row = read_json(self.path, max_bytes=65536)
            at = parse_detected_at(row['updated_at'])
            owner = row['owner_session_id']
            validate_camera_id(row['camera_id'])
            if (row['record_type'] != 'SINGLE_VEHICLE_HANDOFF' or not isinstance(owner, str)
                    or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}', owner)
                    or not -1 <= (self.clock()-at).total_seconds() <= 5
                    or (self.owner is not None and owner != self.owner)
                    or (self.last_at is not None and at < self.last_at)):
                self.status = 'SOURCE_UNAVAILABLE'
                return None
            self.owner, self.last_at = owner, at
            exited = row.get('last_exit')
            if exited is not None:
                if (type(exited['parking_usage_id']) is not int or exited['parking_usage_id'] < 1
                        or not isinstance(exited['plate_number'], str)
                        or not re.fullmatch(r'[0-9]{2,3}[가-힣][0-9]{4}', exited['plate_number'])
                        or str(uuid.UUID(exited['event_id'])) != exited['event_id']
                        or parse_detected_at(exited['detected_at']) > at):
                    raise ValueError('Invalid verified exit')
                self.last_exit = dict(exited)
            if row['status'] != 'ACTIVE':
                self.status = row['status'] if row['status'] in ('EMPTY', 'CLOSED', 'BLOCKED') else 'INVALID'
                return None
            active = row['active']
            if (type(active['parking_usage_id']) is not int or active['parking_usage_id'] < 1
                    or not isinstance(active['plate_number'], str)
                    or not re.fullmatch(r'[0-9]{2,3}[가-힣][0-9]{4}', active['plate_number'])
                    or type(active['confidence']) not in (int, float)
                    or not math.isfinite(active['confidence']) or not 0 <= active['confidence'] <= 1
                    or parse_detected_at(active['detected_at']) > at
                    or str(uuid.UUID(active['event_id'])) != active['event_id']):
                raise ValueError('Invalid entry identity')
            self.status = 'ACTIVE'
            return dict(active, owner_session_id=owner)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
            self.status = 'SOURCE_UNAVAILABLE'
            self.last_exit = None
            return None

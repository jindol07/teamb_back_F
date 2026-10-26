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
                      'camera_id': camera_id, 'status': 'EMPTY', 'source_status': 'RUNNING', 'active': None,
                      'updated_at': at.isoformat(), 'reason': None, 'last_exit': None}
        # 1. 이전 실행의 파일을 덮어쓰거나 이전 차량을 자동 복원하지 않습니다.
        with self.path.open('x', encoding='utf-8') as stream:
            json.dump(self.state, stream, ensure_ascii=False)
        self._at = at
        self._closed = False

    def _save(self, at):
        # 비동기 OCR은 과거 수집 시각으로 완료될 수 있으므로 heartbeat 시각을 되돌리지 않습니다.
        at = max(at, self._at)
        self._at = at
        self.state['updated_at'] = at.isoformat()
        write_json_atomic(self.path, self.state)

    def heartbeat(self, at):
        if not self._closed and (at-self._at).total_seconds() >= .5:
            self._save(at)

    def allow(self, event, at):
        if self._closed:
            return False
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
        if self._closed:
            raise ValueError('종료된 입차 신원 기록은 재사용할 수 없습니다.')
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
              and active['plate_number'] == event['plate_number'] and active['parking_usage_id'] == usage
              and parse_detected_at(event['detected_at']) >= parse_detected_at(active['detected_at'])):
            self.state.update(status='EMPTY', active=None, reason=None, last_exit={
                'plate_number': event['plate_number'], 'parking_usage_id': usage,
                'event_id': event['event_id'], 'detected_at': event['detected_at']})
        else:
            self.state.update(status='BLOCKED', reason='USAGE_ID_MISMATCH')
        self._save(at)

    def close(self, at):
        # 3. 수집 종료는 출차가 아닙니다. 확인된 입차와 보류 사유를 그대로 보관합니다.
        if not self._closed:
            self.state['source_status'] = 'STOPPED'
            self._save(at)
            self._closed = True


class SingleVehicleHandoffReader:
    def __init__(self, path, clock=None):
        self.path, self.clock = Path(path), clock or (lambda: datetime.now(timezone.utc))
        self.owner, self.last_at = None, None
        self.status = 'WAIT_ENTRY'
        self.last_exit = None
        self._retained = None

    def snapshot(self):
        # 보관된 신원은 진단용입니다. read()가 반환한 현재 신원만 신규 연결에 사용합니다.
        return {'status': self.status, 'usable_for_matching': self.status == 'ACTIVE',
                'retained_identity': dict(self._retained) if self._retained is not None else None}

    def read(self):
        # 2. 신원 보관과 신규 전송 허용을 분리합니다. 만료·종료는 출차 근거가 아닙니다.
        self.status = 'WAIT_ENTRY'
        self.last_exit = None
        try:
            row = read_json(self.path, max_bytes=65536)
            at = parse_detected_at(row['updated_at'])
            owner = row['owner_session_id']
            validate_camera_id(row['camera_id'])
            if (row['record_type'] != 'SINGLE_VEHICLE_HANDOFF' or not isinstance(owner, str)
                    or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}', owner)
                    or (self.clock()-at).total_seconds() < -1
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
            fresh = (self.clock()-at).total_seconds() <= 5
            if row['status'] == 'EMPTY':
                if row['active'] is not None:
                    raise ValueError('Empty state contains active identity')
                # 다른 이용의 출차나 단순 EMPTY 파일로 이미 보관한 차량을 지우지 않습니다.
                if self._retained is not None:
                    if (exited is None or any(exited[k] != self._retained[k]
                            for k in ('parking_usage_id', 'plate_number'))
                            or parse_detected_at(exited['detected_at']) < parse_detected_at(self._retained['detected_at'])):
                        raise ValueError('Retained identity requires matching verified exit')
                    self._retained = None
                if not fresh:
                    self.last_exit = None
                self.status = 'EMPTY' if fresh else 'SOURCE_UNAVAILABLE'
                return None
            if row['status'] not in ('ACTIVE', 'BLOCKED'):
                self.status = 'CLOSED' if row['status'] == 'CLOSED' else 'INVALID'
                return None
            active = row['active']
            if active is None and row['status'] == 'BLOCKED':
                self.status = 'BLOCKED'
                return None
            if (type(active['parking_usage_id']) is not int or active['parking_usage_id'] < 1
                    or not isinstance(active['plate_number'], str)
                    or not re.fullmatch(r'[0-9]{2,3}[가-힣][0-9]{4}', active['plate_number'])
                    or type(active['confidence']) not in (int, float)
                    or not math.isfinite(active['confidence']) or not 0 <= active['confidence'] <= 1
                    or parse_detected_at(active['detected_at']) > at
                    or str(uuid.UUID(active['event_id'])) != active['event_id']):
                raise ValueError('Invalid entry identity')
            identity = dict(active, owner_session_id=owner)
            if self._retained is not None and identity != self._retained:
                # 1. B가 중간 EMPTY를 읽지 못했어도 이전 이용의 검증 출차가 있어야 전환합니다.
                previous = self._retained
                if (row['status'] != 'ACTIVE' or exited is None
                        or any(exited[k] != previous[k] for k in ('parking_usage_id', 'plate_number'))
                        or parse_detected_at(exited['detected_at']) < parse_detected_at(previous['detected_at'])
                        or active['parking_usage_id'] == previous['parking_usage_id']
                        or active['event_id'] == previous['event_id']
                        or parse_detected_at(active['detected_at']) < parse_detected_at(exited['detected_at'])):
                    raise ValueError('Active identity changed without verified exit')
            self._retained = identity
            # 유효 신원을 저장해도 A의 신호가 끊기면 새 구획 연결에는 사용하지 않습니다.
            if not fresh:
                self.status = 'SOURCE_UNAVAILABLE'
            elif row.get('source_status', 'RUNNING') != 'RUNNING':
                self.status = 'SOURCE_STOPPED'
            else:
                self.status = row['status']
            if self.status != 'ACTIVE':
                self.last_exit = None
                return None
            return dict(identity)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
            self.status = 'SOURCE_UNAVAILABLE'
            self.last_exit = None
            return None

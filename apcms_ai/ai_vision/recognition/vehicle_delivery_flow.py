# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/vehicle_delivery_flow.py
"""실시간 차량 이벤트 후보의 중복을 검사한 뒤 전송 결과를 기록합니다.

중요: 기본 VehicleHTTPClient는 비활성화 상태입니다. 실제 송신은 외부에서
활성화된 클라이언트를 명시적으로 주입한 경우에만 시도합니다.
"""

# 1. 외부 모듈
# 1-1. 정규식으로 session_id 형식을 엄격하게 검사합니다.
import re
# 1-2. payload 규격 검사, 중복 방지 상태 관리, HTTP 전송을 담당하는 기능입니다.
from ai_vision.recognition.vehicle_contract import validate_vehicle_payload
from ai_vision.recognition.vehicle_event_guard import VehicleEventGuard
from ai_vision.recognition.vehicle_http import VehicleHTTPClient


# 2. 한 실행 동안 사용할 전송 흐름
class VehicleDeliveryFlow:
    # 2-1. client/guard를 주입하지 않으면 각각 기본 객체를 생성합니다.
    # 2-2. 같은 실행 내에서 guard를 유지해야 이미 처리한 ID를 기억할 수 있습니다.
    def __init__(self, client=None, guard=None):
        self.client = VehicleHTTPClient() if client is None else client
        self.guard = VehicleEventGuard() if guard is None else guard

    # 3. 후보를 받아 '차단 → 비활성화 → 중복 확인 → 1회 전송' 순서로 처리합니다.
    def process(self, session_id, candidate):
        # 3-1. 세션 ID는 영문/숫자로 시작하며 이후 영문, 숫자, _, -만 허용합니다.
        # 3-2. 추적 ID가 음수이거나 정수가 아니면 유효한 차량으로 보지 않습니다.
        if (not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", session_id) or
                not isinstance(candidate, dict) or candidate.get("origin") != "LIVE" or
                type(candidate.get("track_id")) is not int or candidate["track_id"] < 0):
            raise ValueError("실시간 출처·실행 ID·차량 ID를 확인해 주세요.")
        track = candidate["track_id"]
        # 3-3. 공통 결과: 요청 여부와 자동 재시도 금지는 초기 상태에서 명확히 표시합니다.
        base = {"track_id": track, "request_attempted": False, "receipt": None, "automatic_retry_allowed": False,
                "http_enabled": self.client.enabled}

        # 4. 인식 조건을 통과하지 못한 후보는 보내지 않습니다.
        # 4-1. payload가 없는 BLOCKED 후보는 정상적인 '전송 보류' 결과입니다.
        if candidate.get("status") == "BLOCKED" and candidate.get("payload") is None:
            return {**base, "decision": "BLOCKED", "receipt_state": None}
        # 4-2. 허용된 상태는 CANDIDATE_ONLY이며 차단 이유가 없어야 합니다.
        if candidate.get("status") != "CANDIDATE_ONLY" or candidate.get("reasons") != []:
            raise ValueError("실시간 후보 상태를 확인해 주세요.")
        event = validate_vehicle_payload(candidate["payload"])

        # 5. HTTP가 비활성화되어 있다면 Guard에도 후보를 예약하지 않습니다.
        # 이후 명시적으로 활성화했을 때 최초 요청이 막히지 않도록 하는 규칙입니다.
        if not self.client.enabled:
            return {**base, "decision": "DISABLED", "receipt_state": None}

        # 6. 같은 세션의 중복 이벤트인지 확인하고 새 후보를 예약합니다.
        decision = self.guard.consider(session_id, track, event)
        result = {**base, "event_id": decision["event_id"], "decision": decision["decision"],
                  "receipt_state": decision["receipt_state"]}
        # 6-1. 이미 처리/보류된 차량이면 더 전송하지 않습니다.
        if decision["decision"] != "NEW_CANDIDATE":
            return result

        # 7. 신규 후보에 대해서만 단 한 번 전송을 시도합니다.
        try:
            receipt = self.client.send(decision["payload"])
            # 7-1. 전송 계층이 결과 구조를 제대로 반환했는지 검사합니다.
            if not isinstance(receipt, dict) or type(receipt.get("request_attempted")) is not bool:
                raise ValueError("요청 시도 여부를 확인할 수 없는 전송 결과입니다.")
            # 7-2. 응답 분류를 같은 Guard에 기록해 향후 중복 요청에 사용합니다.
            recorded = self.guard.record_result(session_id, track, event["camera_id"], receipt)
        except Exception:
            # 7-3. 오류 시 실제 서버 처리 여부가 불확실할 수 있으므로 DELIVERY_UNKNOWN.
            # 이미 예약한 이벤트를 다시 열거나 자동 재전송하지 않습니다.
            receipt = {"event_id": event["event_id"], "event_type": "VEHICLE_PASSAGE", "http_status": None,
                       "state": "DELIVERY_UNKNOWN", "reason_code": "LOCAL_DELIVERY_PROCESSING_FAILED",
                       "receipt_verified": False, "automatic_retry_allowed": False, "request_attempted": None}
            recorded = self.guard.record_result(session_id, track, event["camera_id"], receipt)
        # 8. 요청 시도와 Guard의 최신 상태를 합쳐 호출자에게 반환합니다.
        return {**result, "request_attempted": receipt["request_attempted"], "receipt": receipt,
                "receipt_state": recorded["receipt_state"]}


class SpaceMatchDeliveryFlow:
    """대기열 없이 현재 후보 한 건을 비동기로 보내고 결과를 회수합니다."""

    def __init__(self, client=None, release_client=None):
        from concurrent.futures import ThreadPoolExecutor
        from ai_vision.recognition.vehicle_http import SpaceMatchHTTPClient
        self.client = SpaceMatchHTTPClient() if client is None else client
        from ai_vision.recognition.vehicle_http import SpaceReleaseHTTPClient
        self.release_client = SpaceReleaseHTTPClient() if release_client is None else release_client
        self._links = {}
        self._release_seen = set()
        self.blocked = False
        self.records = []
        self._seen = set()
        self._plates = set()
        self._future = self._record = None
        self._closed = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='space-match-http')

    def poll(self, persist):
        if self._future is not None and self._future.done():
            try:
                receipt = self._future.result()
                if (not isinstance(receipt, dict) or
                        receipt.get('event_id') != self._record['payload']['event_id'] or
                        receipt.get('event_type') != self._record['payload']['event_type'] or
                        type(receipt.get('request_attempted')) is not bool or
                        receipt.get('state') not in {'APPLIED', 'UNCHANGED', 'HELD', 'REJECTED', 'AUTH_REQUIRED', 'DELIVERY_UNKNOWN'}):
                    raise ValueError('구획 응답 형식을 확인하세요.')
                self._record.update(status=receipt['state'], receipt=receipt)
                event = self._record['payload']
                plate = event['plate_number']
                expected_usage = self._record.get('expected_parking_usage_id')
                if (expected_usage is not None and receipt['state'] in ('APPLIED', 'UNCHANGED')
                        and (receipt.get('receipt_verified') is not True
                             or receipt.get('parking_usage_id') != expected_usage)):
                    self.blocked = True
                    self._record['blocking_reason'] = 'ENTRY_USAGE_CHANGED'
                # 연결 반영 성공과 자동 해제 준비 상태를 구분합니다.
                # 버전 없는 구형/비활성 Boot 응답을 성공으로만 남기면 이동 후 영구 대기합니다.
                if (self.release_client.enabled and event['event_type'] == 'VEHICLE_SPACE_MATCH'
                        and receipt['state'] in ('APPLIED', 'UNCHANGED')):
                    usage, version = receipt.get('parking_usage_id'), receipt.get('link_version')
                    if (receipt.get('receipt_verified') is not True or type(usage) is not int or usage < 1
                            or type(version) is not int or not 0 <= version < 10**18 - 1):
                        self.blocked = True
                        self._record['blocking_reason'] = 'SPACE_RELEASE_VERSION_UNAVAILABLE'
                if receipt.get('receipt_verified') and receipt['state'] in ('APPLIED', 'UNCHANGED'):
                    if event['event_type'] == 'VEHICLE_SPACE_MATCH':
                        usage, version = receipt.get('parking_usage_id'), receipt.get('link_version')
                        if type(usage) is int and usage > 0 and type(version) is int and 0 <= version < 10**18:
                            self._links[plate] = {'event': event, 'usage': usage, 'version': version,
                                                  'track_id': self._record['track_id']}
                    elif (receipt['state'] == 'APPLIED' and receipt.get('parking_usage_id') == event['parking_usage_id']
                          and receipt.get('link_version') == event['link_version'] + 1):
                        self._links.pop(plate, None)
                        self._plates.discard(plate)
            except Exception:
                self._record.update(status='DELIVERY_UNKNOWN', receipt=None)
            finally:
                if self._record['status'] in ('DELIVERY_UNKNOWN', 'AUTH_REQUIRED', 'REJECTED'):
                    self.blocked = True
                self._future = self._record = None
            persist()

    def submit(self, candidate, observation_key, persist):
        from copy import deepcopy
        from ai_vision.recognition.vehicle_contract import validate_space_match_payload
        if self._closed:
            raise RuntimeError('종료한 연결 전송 흐름입니다.')
        if candidate.get('origin') != 'LIVE':
            raise ValueError('실시간 후보만 허용합니다.')
        if candidate.get('status') == 'BLOCKED':
            return 'BLOCKED'
        if candidate.get('status') != 'CANDIDATE_ONLY' or candidate.get('reasons') != []:
            raise ValueError('후보 상태를 확인하세요.')
        event = validate_space_match_payload(candidate['payload'])
        expected_usage = candidate.get('expected_parking_usage_id')
        if expected_usage is not None and (type(expected_usage) is not int or expected_usage < 1):
            raise ValueError('입차 근거의 이용 ID를 확인하세요.')
        if self.blocked:
            return 'BLOCKED'
        if observation_key in self._seen:
            return 'DUPLICATE'
        # 1. 다른 요청을 기다리는 후보는 보관하지 않습니다. 다음 프레임에서 다시 관찰합니다.
        if self.client.enabled and self._future is not None:
            return 'BUSY'
        if len(self.records) >= 10000:
            raise ValueError('구획 연결 기록 한도를 초과했습니다.')
        if (self.client.enabled and self.release_client.enabled and event['plate_number'] in self._links):
            return 'BUSY'
        status = ('DISABLED' if not self.client.enabled else
                  'HELD_RELEASE_REQUIRED' if event['plate_number'] in self._plates else 'IN_FLIGHT')
        record = {'track_id': candidate['track_id'], 'status': status,
                  'payload': deepcopy(event), 'receipt': None, 'automatic_retry_allowed': False}
        if expected_usage is not None:
            record['expected_parking_usage_id'] = expected_usage
        if 'identity_verification' in candidate:
            record['identity_verification'] = deepcopy(candidate['identity_verification'])
        self.records.append(record)
        self._seen.add(observation_key)
        # 2. 저장에 실패하면 전송하지 않습니다. 같은 후보도 자동 재시도하지 않습니다.
        persist()
        if status == 'IN_FLIGHT':
            self._plates.add(event['plate_number'])
            self._record = record
            try:
                self._future = self._executor.submit(self.client.send, deepcopy(event))
            except Exception:
                record['status'] = 'DELIVERY_UNKNOWN'
                self._record = None
                persist()
                raise
        return status

    def acknowledge_gate_exit(self, plate, usage_id):
        """A가 같은 이용의 출차 성공을 확인한 경우에만 B의 이전 연결 억제를 풉니다."""
        if self._closed or self.blocked or type(usage_id) is not int or usage_id < 1:
            return False
        if self._record is not None and self._record['payload']['plate_number'] == plate:
            return False
        for record in reversed(self.records):
            if record['payload']['plate_number'] != plate:
                continue
            receipt = record.get('receipt') or {}
            if (receipt.get('receipt_verified') is not True or receipt.get('parking_usage_id') != usage_id
                    or record['status'] not in ('APPLIED', 'UNCHANGED')):
                return False
            self._links.pop(plate, None)
            self._plates.discard(plate)
            return True
        return False

    def release_empty(self, empty_codes, camera_id, detected_at, persist):
        # 3. 추적 소실만으로 해제하지 않는다. 최신 연속 EMPTY와 서버 연결 버전이 필요하다.
        import uuid
        from copy import deepcopy
        from ai_vision.recognition.vehicle_contract import validate_space_release_payload
        if self._closed:
            raise RuntimeError('종료한 연결 전송 흐름입니다.')
        if self.blocked or not self.release_client.enabled or self._future is not None:
            return False
        for plate, link in self._links.items():
            key = (link['usage'], link['version'])
            if link['event']['space_code'] not in empty_codes or key in self._release_seen:
                continue
            if len(self.records) >= 10000:
                raise ValueError('구획 전송 기록 한도를 초과했습니다.')
            event = validate_space_release_payload({'event_id': str(uuid.uuid4()),
                'event_type': 'VEHICLE_SPACE_RELEASE', 'camera_id': camera_id, 'detected_at': detected_at,
                'plate_number': plate, 'space_code': link['event']['space_code'],
                'parking_usage_id': link['usage'], 'link_version': link['version'], 'reason': 'CONFIRMED_EMPTY'})
            record = {'track_id': link['track_id'], 'status': 'IN_FLIGHT', 'payload': event,
                      'receipt': None, 'automatic_retry_allowed': False}
            self.records.append(record)
            self._release_seen.add(key)
            persist()
            self._record = record
            try:
                self._future = self._executor.submit(self.release_client.send, deepcopy(event))
            except Exception:
                record['status'] = 'DELIVERY_UNKNOWN'
                self._record = None
                persist()
                raise
            return True
        return False

    def close(self, persist):
        if self._closed:
            return
        self._closed = True
        self._executor.shutdown(wait=True)
        self.poll(persist)

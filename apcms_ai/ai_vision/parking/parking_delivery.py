# D:/finalProjectB/back/apcms_ai/ai_vision/parking/parking_delivery.py
"""전송 설정을 확인하고 웹캠 점유 이벤트를 한 번만 보냅니다."""

import requests
from collections import deque
from concurrent.futures import ThreadPoolExecutor, wait
from ai_vision.parking.occupancy_response import validate_occupancy_response
from ai_vision.parking.parking_event_sender import _build_event_urls, _configured_api_key, convert_space_code


class ParkingDelivery:
    def __init__(self, settings):
        self.settings = settings
        self.attempts = 0
        self.blocked = False
        self._seen = set()
        self.session = requests.Session()
        # 1. 현장 PC의 프록시 설정으로 관리자 요청이 우회되지 않게 합니다.
        self.session.trust_env = False

    def send(self, event):
        if event['space_code'] not in self.settings['allowed_codes']:
            return {'event_id': event['event_id'], 'status': 'NOT_ALLOWED'}
        if self.blocked or event['event_id'] in self._seen:
            raise RuntimeError('중단되었거나 이미 시도한 점유 이벤트입니다.')
        self._seen.add(event['event_id'])
        self.attempts += 1
        result = {'event_id': event['event_id'], 'status': 'DELIVERY_UNKNOWN'}
        # 2. 자동 재시도·주소 이동을 하지 않습니다. 불명확한 응답은 운영자가 확인합니다.
        try:
            with self.session.post(self.settings['url'], json=event,
                                   headers={'X-AI-API-Key': self.settings['key']},
                                   timeout=(3, 15), allow_redirects=False, stream=True) as response:
                result['http_status'] = response.status_code
                if response.status_code != 200:
                    self.blocked = True
                    result['status'] = 'REJECTED' if 400 <= response.status_code < 500 and response.status_code not in (408, 429) else 'DELIVERY_UNKNOWN'
                    result['reason'] = 'HTTP_STATUS'
                    return result
                raw = bytearray()
                for chunk in response.iter_content(4096):
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        raise ValueError('점유 응답 크기 한도를 초과했습니다.')
                from ai_vision.recognition.local_io import decode_object
                body = decode_object(raw.decode('utf-8'))
                outcome = validate_occupancy_response(event, body)
                # 계약에 있는 필드만 보고서로 전달하고 임의 응답 필드는 제외합니다.
                safe_body = {name: body.get(name) for name in ('eventId', 'spaceCode', 'outcome',
                             'previousStatus', 'currentStatus', 'aiDetectionEventId')}
                result.update(status=outcome, response=safe_body)
                # 보호 구획이나 관리자 보정이 발견되면 다음 상태를 무작정 전송하지 않습니다.
                self.blocked = outcome.startswith('SKIPPED_')
        except requests.RequestException:
            result['reason'] = 'TRANSPORT_ERROR'
            self.blocked = True
        except (ValueError, UnicodeError):
            result['reason'] = 'INVALID_RESPONSE'
            self.blocked = True
        return result

    def close(self):
        self.session.close()


class ParkingDeliveryWorker:
    """메인 스레드가 전송 순서를 제어하고 작업자 하나가 HTTP만 처리합니다."""

    def __init__(self, client, max_pending=8):
        if type(max_pending) is not int or not 1 <= max_pending <= 16:
            raise ValueError('점유 전송 대기 한도는 1~16 정수여야 합니다.')
        self.client = client
        self.limit = max_pending
        self.queue = deque()
        self.future = None
        self.receipt = None
        self.aborted = False
        self.closed = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='parking-http')

    @property
    def pending(self):
        return len(self.queue) + int(self.future is not None)

    @property
    def blocked(self):
        return self.aborted or self.client.blocked

    def enqueue(self, event, receipt):
        # 1. 실행 중인 요청도 포함하여 메모리 대기열 크기를 제한합니다.
        if self.closed:
            raise RuntimeError('종료한 점유 전송 작업자에는 등록할 수 없습니다.')
        if self.blocked or self.pending >= self.limit:
            self.aborted = True
            return False
        self.queue.append((event, receipt))
        return True

    def cancel_queued(self):
        while self.queue:
            _, receipt = self.queue.popleft()
            receipt['status'] = 'CANCELLED_BEFORE_SEND'
            self.aborted = True

    def _complete(self):
        try:
            self.receipt.update(self.future.result())
        except (Exception, KeyboardInterrupt):
            self.receipt.update(status='DELIVERY_UNKNOWN', reason='WORKER_ERROR')
            self.aborted = True
        finally:
            self.future = self.receipt = None

    def poll(self, persist):
        # 2. 완료 기록 저장과 다음 요청 시작은 카메라 스레드에서만 수행합니다.
        if self.future is not None and self.future.done():
            self._complete()
            persist()
        if self.blocked:
            self.cancel_queued()
            persist()
            return False
        if self.future is None and self.queue:
            event, receipt = self.queue.popleft()
            receipt['status'] = 'IN_FLIGHT'
            persist()  # 기록을 저장하지 못하면 HTTP 작업을 제출하지 않습니다.
            self.receipt = receipt
            self.future = self.executor.submit(self.client.send, event)
        return True

    def close(self):
        # 3. 종료 후 새 요청은 시작하지 않습니다. 이미 시작한 요청만 결과를 회수합니다.
        if self.closed:
            return
        self.closed = True
        self.cancel_queued()
        try:
            if self.future is not None:
                wait([self.future])
                self._complete()
        finally:
            self.executor.shutdown(wait=True)



def check_previous_report(path, enabled):
    # 이전 실행 파일을 지정하면 확인이 필요한 기록을 무시하고 새 전송을 시작하지 않습니다.
    if path is None:
        return
    from ai_vision.parking.inspect_parking_camera import inspect_report
    summary = inspect_report(path)
    if enabled and summary['requires_review']:
        raise ValueError('이전 점유 실행에 확인이 필요한 기록이 있습니다. 보고서를 먼저 확인하세요.')


def delivery_settings(config, enabled, allowed_codes, environment):
    # 1. 시험 모드에서는 환경변수만으로 실제 전송이 활성화되지 않습니다.
    if not enabled:
        if allowed_codes:
            raise ValueError('허용 구획은 --enable-http와 함께 지정하세요.')
        return None
    codes = frozenset(allowed_codes)
    configured = {convert_space_code(row['id']) for row in config['spaces']}
    if not codes or not codes <= configured:
        raise ValueError('전송 허용 구획은 좌표 파일에 포함된 DB 구획 코드로 지정하세요.')
    key = _configured_api_key(environment)
    if not isinstance(key, str) or not key.strip() or any(ord(char) < 32 or ord(char) == 127 for char in key):
        raise ValueError('점유 전송 인증키를 환경변수에 설정하세요.')
    # 2. 키와 주소는 보고서에 넣지 않고 전송 객체에만 전달합니다.
    base = environment.get('PARKING_AI_BASE_URL', 'http://127.0.0.1:81/alpharking/admin')
    url = _build_event_urls(base, environment.get('PARKING_AI_API_URL'))['PARKING_OCCUPANCY']
    return {'url': url, 'key': key, 'allowed_codes': codes}

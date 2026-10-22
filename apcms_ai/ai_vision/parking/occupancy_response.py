# D:/finalProjectB/back/apcms_ai/ai_vision/parking/occupancy_response.py
"""관리자 Boot의 점유 응답과 요청의 일치 여부를 확인합니다."""

OCCUPANCY_OUTCOMES = frozenset({
    'UPDATED', 'UNCHANGED', 'DUPLICATE', 'SKIPPED_PROTECTED', 'SKIPPED_BEFORE_CORRECTION'
})
SPACE_STATUSES = frozenset({'AVAILABLE', 'OCCUPIED', 'RESERVED', 'DISABLED'})


def validate_occupancy_response(event, response):
    # 1. 다른 이벤트나 다른 구획의 응답을 현재 요청의 완료로 처리하지 않습니다.
    if not isinstance(response, dict):
        raise ValueError('점유 응답은 객체여야 합니다.')
    if response.get('eventId') != event['event_id'] or response.get('spaceCode') != event['space_code']:
        raise ValueError('점유 응답의 이벤트 ID 또는 구획 코드가 요청과 다릅니다.')
    outcome = response.get('outcome')
    if not isinstance(outcome, str) or outcome not in OCCUPANCY_OUTCOMES:
        raise ValueError('알 수 없는 점유 처리 결과입니다.')
    previous, current = response.get('previousStatus'), response.get('currentStatus')
    if not isinstance(previous, str) or previous not in SPACE_STATUSES or not isinstance(current, str) or current not in SPACE_STATUSES:
        raise ValueError('점유 응답의 상태 코드가 올바르지 않습니다.')
    # 2. 중복 응답은 이력 ID가 없고, 새로 기록된 응답은 양의 정수 ID를 가집니다.
    identifier = response.get('aiDetectionEventId')
    if outcome == 'DUPLICATE':
        if identifier is not None:
            raise ValueError('중복 응답의 이력 ID가 올바르지 않습니다.')
    elif type(identifier) is not int or identifier <= 0:
        raise ValueError('점유 응답의 이력 ID가 올바르지 않습니다.')
    # 3. 건너뛴 처리는 상태 변경 성공과 구분하고 자동 재전송하지 않습니다.
    if outcome == 'UPDATED':
        if previous not in {'AVAILABLE', 'OCCUPIED'} or previous == current or current != event['status']:
            raise ValueError('점유 변경 결과가 요청과 다릅니다.')
    elif previous != current:
        raise ValueError('변경하지 않은 응답에서 구획 상태가 달라졌습니다.')
    if outcome == 'UNCHANGED' and current != event['status']:
        raise ValueError('유지된 구획 상태가 요청과 다릅니다.')
    if outcome == 'SKIPPED_PROTECTED' and current not in {'RESERVED', 'DISABLED'}:
        raise ValueError('보호 대상이 아닌 구획의 보호 응답입니다.')
    return outcome

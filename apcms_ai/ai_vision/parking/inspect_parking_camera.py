# D:/finalProjectB/back/apcms_ai/ai_vision/parking/inspect_parking_camera.py
"""점유 보고서를 기록하고 재실행 전에 확인할 사항을 안내합니다."""

import argparse
from pathlib import Path
from datetime import datetime, timezone
from ai_vision.recognition.local_io import read_json, write_json_atomic

RECEIPTS = frozenset({'IN_FLIGHT', 'NOT_ALLOWED', 'UPDATED', 'UNCHANGED', 'DUPLICATE',
                     'SKIPPED_PROTECTED', 'SKIPPED_BEFORE_CORRECTION', 'REJECTED', 'DELIVERY_UNKNOWN',
                     'QUEUED', 'CANCELLED_BEFORE_SEND', 'NOT_SENT_QUEUE_FULL'})
STATUSES = frozenset({'RUNNING', 'COMPLETED', 'INCOMPLETE', 'STOPPED', 'CANCELLED', 'FAILED', 'DELIVERY_STOPPED'})


WITHDRAWAL_REASONS = frozenset({'OBSERVATION_GAP', 'TRACK_NOT_OBSERVED', 'OUTSIDE_SPACE',
    'SPACE_CHANGED', 'POSITION_MOVED', 'MULTIPLE_TRACKS_IN_SPACE', 'OCCUPANCY_NOT_CONTINUOUS',
    'PLATE_CONFLICT', 'DUPLICATE_PLATE'})


def summarize_connection_reviews(events):
    # 예전 보고서에 없는 원인을 현재 상황으로 추측해 채우지 않습니다.
    if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
        raise ValueError('연결 관찰 이벤트 목록을 확인하세요.')
    counts = {}
    for event in events:
        if event.get('kind') not in ('MATCH_REVIEW', 'TRACK_LOST'):
            continue
        reason = event.get('reason')
        reason = reason if isinstance(reason, str) and reason in WITHDRAWAL_REASONS else 'UNKNOWN_LEGACY'
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def inspect_report(path):
    # 1. 손상되거나 다른 종류인 파일을 정상 종료 보고서로 해석하지 않습니다.
    report = read_json(path, max_bytes=16 * 1024 * 1024)
    if not isinstance(report.get('status'), str) or report['status'] not in STATUSES or type(report.get('dry_run')) is not bool:
        raise ValueError('주차 카메라 보고서의 상태 또는 시험 모드가 올바르지 않습니다.')
    if report.get('record_type', 'PARKING_CAMERA_SESSION') != 'PARKING_CAMERA_SESSION':
        raise ValueError('주차 카메라 보고서가 아닙니다.')
    attempts = report.get('http_requests')
    if type(attempts) is not int or attempts < 0 or (report['dry_run'] and attempts):
        raise ValueError('HTTP 요청 횟수가 올바르지 않습니다.')
    events, deliveries = report.get('events'), report.get('deliveries', [])
    if not isinstance(events, list) or not isinstance(deliveries, list):
        raise ValueError('보고서의 이벤트와 전송 목록을 확인하세요.')
    identifiers = set()
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get('event_id'), str) or not event['event_id'] or event['event_id'] in identifiers:
            raise ValueError('이벤트 ID가 누락되었거나 중복되었습니다.')
        identifiers.add(event['event_id'])
    counts = {}
    seen = set()
    for receipt in deliveries:
        if not isinstance(receipt, dict):
            raise ValueError('전송 기록이 객체가 아닙니다.')
        status, identifier = receipt.get('status'), receipt.get('event_id')
        if not isinstance(status, str) or status not in RECEIPTS or not isinstance(identifier, str) or identifier not in identifiers or identifier in seen:
            raise ValueError('전송 기록의 상태 또는 이벤트 연결이 올바르지 않습니다.')
        seen.add(identifier)
        counts[status] = counts.get(status, 0) + 1
    if report['dry_run'] and any(key != 'NOT_ALLOWED' for key in counts):
        raise ValueError('시험 모드 보고서에 실제 전송 기록이 있습니다.')
    # 2. 프로세스가 끝났어도 서버 반영 여부가 불명확한 요청은 따로 안내합니다.
    uncertain = sum(counts.get(key, 0) for key in ('IN_FLIGHT', 'DELIVERY_UNKNOWN'))
    # 이벤트만 저장되고 전송 기록을 남기기 전에 종료된 실행도 확인 대상으로 둡니다.
    allowed = report.get('allowed_space_codes')
    if allowed is not None and (not isinstance(allowed, list) or any(not isinstance(code, str) for code in allowed)):
        raise ValueError('허용 구획 목록이 올바르지 않습니다.')
    unrecorded = sum(event['event_id'] not in seen and
                     (allowed is None or event.get('space_code') in allowed) for event in events)
    review = uncertain > 0 or (not report['dry_run'] and report['status'] in ('RUNNING', 'FAILED', 'DELIVERY_STOPPED'))
    review = review or (not report['dry_run'] and (unrecorded > 0 or attempts > len(deliveries)))
    review = review or any(counts.get(key, 0) for key in ('REJECTED', 'SKIPPED_PROTECTED', 'SKIPPED_BEFORE_CORRECTION'))
    review = review or any(counts.get(key, 0) for key in ('QUEUED', 'CANCELLED_BEFORE_SEND', 'NOT_SENT_QUEUE_FULL'))
    # 3. 차량 연결 요청도 같은 보고서에서 재시작 전 확인합니다.
    vehicle = report.get('vehicle_space', {})
    if not isinstance(vehicle, dict):
        raise ValueError('구획 연결 기록은 객체여야 합니다.')
    withdrawal_counts = summarize_connection_reviews(vehicle.get('events', []))
    matches = vehicle.get('deliveries', [])
    if not isinstance(matches, list) or type(vehicle.get('http_enabled', False)) is not bool:
        raise ValueError('구획 연결 기록을 확인하세요.')
    if type(vehicle.get('release_http_enabled', False)) is not bool:
        raise ValueError('구획 해제 활성화 상태를 확인하세요.')
    match_counts = {}
    blocking_reasons = {}
    for row in matches:
        if not isinstance(row, dict) or row.get('status') not in {
                'DISABLED', 'IN_FLIGHT', 'APPLIED', 'UNCHANGED', 'HELD', 'REJECTED',
                'AUTH_REQUIRED', 'DELIVERY_UNKNOWN', 'HELD_RELEASE_REQUIRED'}:
            raise ValueError('구획 연결 결과 상태를 확인하세요.')
        payload = row.get('payload', {})
        if isinstance(payload, dict) and payload.get('event_type') == 'VEHICLE_SPACE_RELEASE' and not vehicle.get('release_http_enabled', False):
            raise ValueError('비활성 해제 모드에 해제 요청 기록이 있습니다.')
        state = row['status']
        reason = row.get('blocking_reason')
        if reason is not None:
            if not isinstance(reason, str) or not reason or len(reason) > 128:
                raise ValueError('구획 전송 중단 이유를 확인하세요.')
            blocking_reasons[reason] = blocking_reasons.get(reason, 0) + 1
            review = True
        if not vehicle.get('http_enabled', False) and state != 'DISABLED':
            raise ValueError('비활성 연결 기록에 전송 결과가 있습니다.')
        match_counts[state] = match_counts.get(state, 0) + 1
        if state not in ('DISABLED', 'APPLIED', 'UNCHANGED'):
            review = True
        if state in ('IN_FLIGHT', 'DELIVERY_UNKNOWN'):
            uncertain += 1
    action = '서버 반영 여부·구획 보호·오류 원인을 확인한 뒤 새 세션을 시작하세요.' if review else '자동 재전송은 없습니다. 현재 구도와 구획 상태를 확인한 뒤 새 세션을 시작하세요.'
    if 'SPACE_RELEASE_VERSION_UNAVAILABLE' in blocking_reasons:
        action = '구획 연결 성공 기록은 보존하세요. Boot 해제 활성화·연결 버전 DB 준비 상태를 확인하기 전에는 재전송하지 마세요.'
    return {'status': report['status'], 'dry_run': report['dry_run'], 'event_count': len(events),
            'receipt_counts': counts, 'space_match_receipt_counts': match_counts, 'uncertain_count': uncertain, 'unrecorded_count': unrecorded,
            'requires_review': bool(review), 'connection_withdrawal_counts': withdrawal_counts,
            'space_delivery_blocking_reasons': blocking_reasons,
            'next_action': action}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args(argv)
    try:
        summary = inspect_report(args.report)
    except (OSError, ValueError, TypeError):
        print('보고서를 읽을 수 없거나 내용이 올바르지 않습니다.')
        return 1
    print(f"상태: {summary['status']} / 이벤트 {summary['event_count']} / 반영 불명확 {summary['uncertain_count']}")
    if not summary['dry_run'] and summary['unrecorded_count']:
        print(f"전송 기록 누락 이벤트: {summary['unrecorded_count']}")
    for status, count in sorted(summary['receipt_counts'].items()):
        print(f'{status}: {count}')
    for reason, count in sorted(summary['connection_withdrawal_counts'].items()):
        print(f'연결 철회·소실: {reason} {count}건')
    for reason, count in sorted(summary['space_delivery_blocking_reasons'].items()):
        print(f'구획 전송 중단: {reason} {count}건')
    print(summary['next_action'])
    return 2 if summary['requires_review'] else 0




def checkpoint(output_dir, report, processor, delivery=None):
    # 1. 전송 직전에도 호출하여 응답을 받기 전 종료된 시도를 확인할 수 있게 합니다.
    report['statistics'] = processor.statistics()
    report['occupancy'] = processor.occupancy()
    report['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    if delivery is not None:
        report['http_requests'] = delivery.attempts
    write_json_atomic(output_dir / 'parking_camera_check.json', report)


def deliver_changes(output_dir, report, processor, delivery, events, worker=None):
    # 2. HTTP 호출 전 시도 예정 이벤트를 기록하며, 재시작 후 자동 재생하지 않습니다.
    for event in events:
        if event['space_code'] not in delivery.settings['allowed_codes']:
            report['deliveries'].append({'event_id': event['event_id'], 'status': 'NOT_ALLOWED'})
            continue
        receipt = {'event_id': event['event_id'], 'status': 'QUEUED' if worker is not None else 'IN_FLIGHT'}
        report['deliveries'].append(receipt)
        checkpoint(output_dir, report, processor, delivery)
        if worker is not None:
            if not worker.enqueue(event, receipt):
                receipt['status'] = 'NOT_SENT_QUEUE_FULL'
                worker.cancel_queued()
                report['status'] = 'DELIVERY_STOPPED'
                checkpoint(output_dir, report, processor, delivery)
                return False
            continue
        receipt.update(delivery.send(event))
        checkpoint(output_dir, report, processor, delivery)
        if delivery.blocked:
            report['status'] = 'DELIVERY_STOPPED'
            checkpoint(output_dir, report, processor, delivery)
            return False
    if worker is not None:
        active = worker.poll(lambda: checkpoint(output_dir, report, processor, delivery))
        if not active:
            report['status'] = 'DELIVERY_STOPPED'
            checkpoint(output_dir, report, processor, delivery)
        return active
    return True


if __name__ == '__main__':
    raise SystemExit(main())

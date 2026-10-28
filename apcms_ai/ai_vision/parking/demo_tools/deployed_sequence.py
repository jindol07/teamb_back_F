"""A02 오주차→A01 정상 주차→동일 이용 출차의 검증된 단계만 허용합니다."""
PLATE='91소6408'


def trial_config(config, source, root):
    """예약 유무와 관계없이 네 구획의 전송을 허용하는 시험 설정을 만듭니다."""
    result=dict(config)
    for key in ('gate_config','spaces_config','reference'):
        result[key]=str((source.parent/config[key]).resolve())
    result.update(output_dir=str(root/'parking_runs'),frame_export_dir=str(root/'shared_frames'),
                  allowed_codes=[config['space_code_map'][f'A-{i:02d}'] for i in range(1,5)],
                  delivery_enabled=True,preview=True,enable_space_release_http=True)
    return result


def empty_ready(report):
    occupancy=(report or {}).get('occupancy') or {}
    rows=occupancy.get('spaces') or []
    return len(rows)==4 and all(row.get('status')=='EMPTY' for row in rows)


def active_usage(handoff):
    active=(handoff or {}).get('active') or {}
    usage=active.get('parking_usage_id')
    return usage if ((handoff or {}).get('status')=='ACTIVE' and active.get('plate_number')==PLATE
                     and type(usage) is int and usage>0) else None


def decision(deliveries, usage, code, expected, *, require_link=False):
    for row in deliveries:
        payload=row.get('payload') or {};receipt=row.get('receipt') or {}
        if (payload.get('event_type')=='VEHICLE_SPACE_MATCH' and payload.get('plate_number')==PLATE
            and payload.get('space_code')==code and payload.get('expected_parking_usage_id')==usage
            and receipt.get('parking_usage_id')==usage and receipt.get('parking_decision')==expected
            and receipt.get('receipt_verified') is True and receipt.get('request_attempted') is True
            and receipt.get('event_id')==payload.get('event_id')):
            if require_link and receipt.get('state') not in ('APPLIED','UNCHANGED'):continue
            return True
    return False


def exited(handoff, usage):
    last=(handoff or {}).get('last_exit') or {}
    return ((handoff or {}).get('status')=='EMPTY' and last.get('parking_usage_id')==usage
            and last.get('plate_number')==PLATE)


def acknowledged_fire(output, excluded=()):
    """전송 성공한 FIRE 의심 전이를 정규화된 원본 이력과 대조합니다."""
    from ai_vision.safety.fire_alert_live import load_live_payloads
    from ai_vision.recognition.local_io import read_json
    try:
        sent=set(read_json(output/'fire_alert_sent_state.json')['acknowledged_transition_ids'])
        payloads=load_live_payloads(output)
        return any(p['hazard_type']=='FIRE' and p['status']=='SUSPECTED' and p['transition_id'] in sent
                   and p['transition_id'] not in excluded for p in payloads)
    except (OSError,ValueError,KeyError,TypeError):return False

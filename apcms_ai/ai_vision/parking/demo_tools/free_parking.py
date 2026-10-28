"""자유 순서 시험의 점유 관찰과 실제 예약 연결 결과를 구분합니다."""
CODES=tuple(f'3F-A{i:02d}' for i in range(1,5))


def update_free_observation(state, snapshot, usage):
    occupied=state.setdefault('observed_occupied_codes',[])
    for row in snapshot.get('occupancy',{}).get('spaces',[]):
        key=row.get('space_id','')
        code='3F-A'+key[-2:] if key in ('A-01','A-02','A-03','A-04') else None
        if code in CODES and row.get('status')=='OCCUPIED' and code not in occupied:
            occupied.append(code)
    state.setdefault('a01_link_confirmed',False)
    state['current_linked_space']=None
    state['current_parking_decision']=None
    state['confirmed_position_events']=[]
    for row in snapshot.get('vehicle_space',{}).get('deliveries',[]):
        payload=row.get('payload') or {};receipt=row.get('receipt') or {}
        event_type=payload.get('event_type')
        expected=payload.get('expected_parking_usage_id') if event_type=='VEHICLE_SPACE_MATCH' else payload.get('parking_usage_id')
        if (event_type not in ('VEHICLE_SPACE_MATCH','VEHICLE_SPACE_RELEASE') or receipt.get('event_type')!=event_type
            or expected!=usage or payload.get('plate_number')!='91소6408'
            or receipt.get('parking_usage_id')!=usage or receipt.get('receipt_verified') is not True
            or receipt.get('request_attempted') is not True or receipt.get('event_id')!=payload.get('event_id')):
            continue
        if event_type=='VEHICLE_SPACE_RELEASE':
            version=payload.get('link_version')
            if receipt.get('state')=='APPLIED' and type(version) is int and receipt.get('link_version')==version+1:
                if state['current_linked_space']==payload.get('space_code'):
                    state['current_linked_space']=None;state['current_parking_decision']=None
            continue
        verdict=receipt.get('parking_decision');code=payload.get('space_code')
        if receipt.get('state') in ('APPLIED','UNCHANGED') and code in CODES and verdict in ('MATCHED','WRONG_SPACE','NO_VALID_RESERVATION'):
            if verdict=='MATCHED' and code!='3F-A01':raise RuntimeError('예약 자리와 정상 판정 불일치')
            state['current_linked_space']=code;state['current_parking_decision']=verdict
            state['confirmed_position_events'].append({'event_id':payload['event_id'],'space_code':code,'parking_decision':verdict})
            if verdict=='MATCHED':state['a01_link_confirmed']=True
    # 점유 관찰은 차량 신원·서버 판정 성공을 뜻하지 않습니다.
    return state

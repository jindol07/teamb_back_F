"""한 대 시연의 종료·정리 판정. 카메라/DB는 직접 열지 않고 호출자가 제공한 정리 함수만 사용합니다."""

import json
import re
from pathlib import Path

from ai_vision.recognition.local_io import read_json, write_json_atomic


def read_live_journal(path):
    """확정된 줄만 엄격히 읽습니다. 쓰는 중인 마지막 줄은 완료 근거로 사용하지 않습니다."""
    from ai_vision.recognition.local_io import decode_object
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(4*1024*1024+1)
    except FileNotFoundError:
        return []
    if len(raw) > 4*1024*1024:
        raise ValueError('Live journal is oversized')
    if raw and not raw.endswith(b'\n'):
        return None
    return [decode_object(line.decode('utf-8')) for line in raw.splitlines() if line.strip()]


def read_demo_phase(directory):
    """정지 신호를 우선하고 손상·빈 안내로 이전 DONE을 유지하지 않습니다."""
    root = Path(directory)
    if (root/'stop_requested.flag').exists():
        return 'STOP: SESSION ABORTED / NO RETRY'
    try:
        with (root/'phase.txt').open('rb') as stream:
            text = stream.read(1025).decode('utf-8').strip()
        if not text or len(text) > 1024 or '\n' in text or '\r' in text:
            return 'WAIT: SESSION STATUS UNAVAILABLE'
        return text
    except (OSError, UnicodeError):
        return 'WAIT: SESSION STATUS UNAVAILABLE'


def demo_guidance(phase, *, auto_stop=False):
    """두 미리보기에서 공유하는 회차별 행동 안내(한글/글꼴 없을 때 영문)입니다."""
    cycle=re.match(r'^CYCLE ([12])/2 - (.*)$',phase)
    current=cycle.group(2) if cycle else phase
    title=(f'{cycle.group(1)}회차 / 2회' if cycle else '시험 진행 안내',
           f'CYCLE {cycle.group(1)} OF 2' if cycle else 'TEST INSTRUCTIONS')
    if current.startswith('1 ENTRY'):
        action=('사진을 화면 밖으로 뺐다가 A 위쪽 2초 → 천천히 아래쪽 2초',
                'Remove photo, then A: hold ABOVE line 2s, move DOWN, hold 2s')
        stop=('아직 종료하지 마세요. 입차 확인 뒤 A-01 주차 안내를 기다리세요.',
              'Keep both windows open. Wait for PARK instruction.')
    elif current.startswith('2 PARK'):
        action=('B 왼쪽 아래 A-01에 놓고 손을 치운 뒤 정상 주차까지 기다리세요.',
                'B: place photo in lower-left A-01, remove hands, wait for MATCHED')
        stop=('아직 종료하지 마세요. 출차 안내가 나올 때까지 유지하세요.',
              'Keep photo still. Wait for EXIT instruction. Do not press Q.')
    elif current.startswith('3 REMOVE'):
        action=('사진을 화면 밖으로 2초 → A 아래쪽 2초 → 천천히 위쪽 2초',
                'Remove photo 2s, then A: hold BELOW line 2s, move UP, hold 2s')
        stop=(('첫 출차 뒤 종료하지 마세요. 2회차 입차 안내를 기다리세요.'
               if cycle and cycle.group(1)=='1' else '완료 안내가 나올 때까지 기다리세요. 아직 Q를 누르지 마세요.'),
              'Do NOT press Q after first exit. Wait for cycle 2.' if cycle and cycle.group(1)=='1'
              else 'Wait for DONE before pressing Q.')
    elif current.startswith('AUTO:'):
        action=('서버가 카메라와 빈자리를 확인 중입니다. SPACE를 누르지 마세요.',
                'AUTO START: checking cameras and empty spaces. Do not press SPACE.')
        stop=('두 화면을 비우고 입차 안내까지 기다리세요.',
              'Keep both views empty until ENTRY instruction.')
    elif current.startswith('4 DONE') and auto_stop:
        action=('시험 완료입니다. 5초 뒤 서버와 두 카메라가 자동 종료됩니다.',
                'DONE. Server and cameras will stop automatically in 5 seconds.')
        stop=('Q를 누르지 말고 자동 종료를 기다리세요.', 'Wait for automatic shutdown. Do not press Q.')
    elif current.startswith('4 DONE'):
        action=('시험 완료입니다. 5초 기다린 뒤 두 창에서 각각 Q를 누르세요.',
                'DONE. Wait 5 seconds, then press Q in EACH window.')
        stop=('이제 종료해도 됩니다. 종료 후 시험 기록을 정리합니다.',
              'You may close now. Test records will be cleaned after both windows stop.')
    elif current.startswith('2A'):
        action=('B 왼쪽 위 A-02에 놓고 손을 치운 뒤 2B 안내를 기다리세요.',
                'Place photo in upper-left A-02. Remove hands and wait for 2B.')
        stop=('아직 A-01로 옮기거나 종료하지 마세요.', 'Do not move to A-01 or press Q yet.')
    elif current.startswith('2B'):
        action=('B 왼쪽 아래 A-01로 옮기고 손을 치운 뒤 정상 주차까지 기다리세요.',
                'Move photo to lower-left A-01. Remove hands and wait for MATCHED.')
        stop=('출차 안내가 나올 때까지 유지하세요.', 'Keep still until EXIT instruction.')
    elif current.startswith('STOP:'):
        action=('시험이 중단됐습니다. 사진 이동을 멈추고 두 창을 Q로 종료하세요.',
                'TEST STOPPED. Stop moving the photo; press Q in each window.')
        stop=('다시 시작하지 마세요. 결과와 시험 기록 정리를 먼저 확인합니다.',
              'Do not restart until result and cleanup have been checked.')
    elif current.startswith('WAIT:') and 'EMPTY' in current:
        action=('아직 시작하지 않은 창에서만 SPACE를 누르고 두 화면을 비워주세요.',
                'Press SPACE only in a window not started yet. Keep BOTH views empty.')
        stop=('두 창 시작과 빈자리 확인이 끝나면 입차 안내로 바뀝니다.',
              'Wait for both start buttons and empty-space verification.')
    elif current.startswith('WAIT:'):
        action=('처리 결과를 확인 중입니다. 사진을 움직이지 말고 기다리세요.',
                'WAIT. Keep the photo still while the current step is verified.')
        stop=('새 단계 안내가 나오기 전에는 다음 동작을 하지 마세요.',
              'Do not repeat a crossing or start the next step yet.')
    else:
        action=('두 화면을 비우고 각 창에서 SPACE를 눌러 시작하세요.',
                'Keep both views empty and press SPACE in EACH window.')
        stop=('SPACE 전 Q는 준비 취소입니다.', 'Before SPACE, Q cancels preparation.')
    return (title,action,stop)


def load_demo_profile(directory):
    """카메라 배치·시험 대상을 로컬 파일에서 읽고 실행 전에 검증합니다."""
    from urllib.parse import urlsplit
    from ai_vision.recognition.tracking_config import validate_config
    from ai_vision.parking.parking_validation import validate_spaces
    root = Path(directory).resolve()
    config = read_json(root/'demo.local.json')
    required = {'version', 'gate_camera', 'parking_camera', 'seconds', 'plate_number',
                'expected_db_url', 'boot_context_url', 'gate_config', 'spaces_config', 'reference'}
    if (not required <= set(config) or set(config) - required - {'camera_backend', 'scenario', 'cycles', 'create_fixture_vehicle', 'fixture_office_id'}
            or type(config['version']) is not int or config['version'] != 1):
        raise ValueError('Unsupported or incomplete demo profile')
    # 1. 기존 로컬 프로필에 저장한 읽기 방식도 검증합니다. 장치는 열지 않습니다.
    backend = config.get('camera_backend', 'msmf')
    if not isinstance(backend, str) or backend not in ('msmf', 'dshow'):
        raise ValueError('Invalid camera backend')
    config['camera_backend'] = backend
    scenario = config.get('scenario', 'normal')
    if scenario not in ('normal', 'wrong_space_correction'):
        raise ValueError('Invalid demo scenario')
    config['scenario'] = scenario
    cycles = config.get('cycles', 1)
    if type(cycles) is not int or cycles not in (1, 2) or (cycles == 2 and scenario != 'normal'):
        raise ValueError('Repeat demo supports exactly two normal parking cycles')
    config['cycles'] = cycles
    # 3. 승인된 시험 차량 생성은 명시한 프로필에서만 허용합니다.
    create_vehicle = config.get('create_fixture_vehicle', False)
    office = config.get('fixture_office_id')
    if type(create_vehicle) is not bool or (create_vehicle and (type(office) is not int or office <= 0)):
        raise ValueError('Explicit positive fixture office is required for synthetic vehicle')
    if not create_vehicle and office is not None:
        raise ValueError('Fixture office requires synthetic vehicle scope')
    config['create_fixture_vehicle'] = create_vehicle
    for key in ('gate_camera', 'parking_camera'):
        if type(config[key]) is not int or not 0 <= config[key] <= 32:
            raise ValueError('Invalid camera index')
    if config['gate_camera'] == config['parking_camera']:
        raise ValueError('Two different cameras are required')
    if type(config['seconds']) not in (int, float) or not 0 < config['seconds'] <= 300:
        raise ValueError('Invalid demo duration')
    if not isinstance(config['plate_number'], str) or not re.fullmatch(r'[0-9]{2,3}[가-힣][0-9]{4}', config['plate_number']):
        raise ValueError('Explicit test vehicle number is required')
    if not isinstance(config['expected_db_url'], str) or not re.fullmatch(r'jdbc:oracle:thin:@[A-Za-z0-9.-]+:[0-9]{1,5}:[A-Za-z0-9_]+', config['expected_db_url']):
        raise ValueError('Explicit Oracle SID target is required')
    if not isinstance(config['boot_context_url'], str) or not config['boot_context_url']:
        raise ValueError('Explicit Boot context URL is required')
    url = urlsplit(config['boot_context_url'])
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Invalid Boot context URL')
    for key in ('gate_config', 'spaces_config', 'reference'):
        value = config[key]
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise ValueError('Profile assets must use relative paths')
        path = (root/value).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Profile asset is missing or outside the profile')
        config[key] = path
    gate = validate_config(read_json(config['gate_config']))
    if gate['tracker'] != 'botsort':
        raise ValueError('This demo uses BoT-SORT')
    spaces = validate_spaces(read_json(config['spaces_config']))
    if scenario == 'wrong_space_correction' and not {'A-01', 'A-02'} <= {row['id'] for row in spaces['spaces']}:
        raise ValueError('Correction demo requires both A-01 and A-02')
    # 2. 빈 기준 사진이 실제로 읽히고 좌표의 해상도와 맞는지 장치를 열기 전에 확인합니다.
    from PIL import Image
    try:
        with Image.open(config['reference']) as reference:
            if reference.size != (spaces['image_width'], spaces['image_height']):
                raise ValueError('Reference image dimensions do not match parking spaces')
            reference.load()
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError('Reference image is invalid or cannot be read') from error
    config['root'] = root
    return config


def read_fixture(path):
    """Java Properties 시험 매니페스트의 단순 key=value 항목만 엄격하게 읽습니다."""
    path = Path(path)
    if not path.exists():
        return None
    if path.stat().st_size > 65536:
        raise ValueError('Fixture manifest is oversized')
    values = {}
    for line in path.read_text(encoding='ascii').splitlines():
        if not line.strip() or line.lstrip().startswith(('#', '!')):
            continue
        key, sep, value = line.partition('=')
        if not sep or not key or key in values:
            raise ValueError('Invalid or duplicate fixture field')
        values[key] = value
    return values


def fixture_pending(path):
    # COMMIT 직후 표시 저장 전에 중단된 매니페스트도 미정리로 취급합니다.
    try:
        values = read_fixture(path)
        return values is not None and values.get('cleaned') != 'true'
    except (OSError, ValueError, UnicodeError):
        return True


def _verified_passages(path, expected_plate, cycles=1):
    path = Path(path)
    rows = []
    if path.exists():
        if path.stat().st_size > 4*1024*1024:
            raise ValueError('Journal is oversized')
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('Invalid journal row')
                rows.append(row)
    return _verified_passage_rows(rows, expected_plate, cycles)


def _verified_passage_rows(rows, expected_plate, cycles=1):
    if type(cycles) is not int or cycles not in (1, 2):
        raise ValueError('Invalid cycle count')
    sent = {}; received = {}; entries = []; exits = []
    for row in rows:
        event = row.get('payload', {})
        if (event.get('event_type') != 'VEHICLE_PASSAGE' or event.get('plate_number') != expected_plate
                or event.get('direction') not in ('ENTRY', 'EXIT') or not isinstance(event.get('event_id'), str)):
            raise ValueError('Journal scope mismatch')
        key = event['event_id']
        if row.get('stage') == 'BEFORE_SEND':
            if key in sent:
                raise ValueError('Duplicate send requires review')
            sent[key] = event
        elif row.get('stage') == 'RECEIPT':
            receipt = row.get('receipt', {})
            if (key not in sent or sent[key] != event or key in received
                    or receipt.get('event_id') != key or receipt.get('event_type') != 'VEHICLE_PASSAGE'
                    or receipt.get('receipt_verified') is not True
                    or receipt.get('request_attempted') is not True or receipt.get('state') != 'APPLIED'
                    or type(receipt.get('parking_usage_id')) is not int or receipt['parking_usage_id'] < 1):
                raise ValueError('Unknown or non-applied passage requires review')
            received[key] = receipt
            usage = receipt['parking_usage_id']
            if event['direction'] == 'ENTRY':
                if len(entries) != len(exits) or usage in entries or len(entries) >= cycles:
                    raise ValueError('Overlapping or repeated entry usage')
                entries.append(usage)
            else:
                if len(entries) != len(exits)+1 or entries[-1] != usage:
                    raise ValueError('Exit sequence or usage mismatch')
                exits.append(usage)
        else:
            raise ValueError('Invalid journal stage')
    if set(sent) != set(received):
        raise ValueError('Unresolved request or usage mismatch')
    return entries, exits


def evaluate_success(report):
 # 응답 성공과 실제 종료상태를 함께 검사합니다. 조회 실패는 성공으로 추정하지 않습니다.
 checks={}
 checks['both_processes_normal']=report.get('process_exit_codes')==[0,0] and not report.get('controller_error_type')
 checks['entry_exit_same_usage']=report.get('entry_exit_same_usage') is True
 checks['match_same_usage']=report.get('actual_match_same_usage') is True
 checks['b_normal']=report.get('b_status') in ('STOPPED','COMPLETED')
 if report.get('identity_verification_required'):
  checks['b_plate_identity_verified']=(report.get('b_identity_mode')=='ENTRY_AND_B_PLATE_OCR'
      and type(report.get('b_ocr_submitted')) is int and report['b_ocr_submitted']>0
      and report.get('actual_match_same_usage') is True)
 else:
  checks['handoff_without_b_ocr']=report.get('b_ocr_submitted')==0
 identity=report.get('b_identity') or {}
 checks['verified_identity_cleared']=identity.get('status')=='EMPTY' and identity.get('retained_identity') is None
 fields={}
 for line in report.get('database_before_cleanup','').splitlines():
  key,sep,value=line.partition('=')
  if sep:
   try:fields[key]=int(value)
   except ValueError:pass
 entries=report.get('verified_entry_usage_ids',[])
 cycles=report.get('cycles',1)
 cycles_valid=type(cycles) is int and cycles in (1,2)
 all_entries=cycles_valid and len(entries)==cycles and len(set(entries))==cycles
 # 이 테스트는 인쇄차량의 기존4건이 모두출차상태인 조건에서 새이용1건만 생성합니다.
 checks['database_exit_confirmed']=(all_entries and fields.get('USAGE_ROWS',0)>0
     and fields.get('OPEN_ROWS')==0 and fields.get('EXITED_ROWS')==fields.get('USAGE_ROWS'))
 checks['fixture_cleaned']='REMAINING_SYNTHETIC_ROWS=0' in report.get('cleanup','')
 # 1. 새 실행은 명시적 정상 주차와 요청·입차 이용 ID의 일치를 확인합니다.
 # 기존 버전 기록은 당시 성공 조건으로 읽으며 새 실행과 구분합니다.
 if report.get('match_contract_version', 1) == 2:
  checks['session_not_aborted']=not report.get('stop_reason')
  checks['space_requests_resolved']=all(resolved_demo_delivery(row) for row in report.get('space_deliveries', []))
  checks['normal_parking_verified']=(all_entries and all(any(
      verified_demo_match(row, usage, report.get('expected_plate_number', '91소6408'),
                          report.get('identity_verification_required', False))
      for row in report.get('space_deliveries', [])) for usage in entries))
 if cycles == 2:
  checks['two_distinct_complete_cycles']=(all_entries and report.get('verified_exit_usage_ids')==entries)
  checks['two_database_links']=(fields.get('LINKED_ROWS')==2
      and type(report.get('baseline_usage_count')) is int
      and fields.get('USAGE_ROWS')==report['baseline_usage_count']+2)
 if report.get('scenario') == 'wrong_space_correction':
  checks['wrong_space_then_matched']=(len(set(entries))==1 and verified_demo_correction(
      report.get('space_deliveries', []), entries[0], report.get('expected_plate_number', '91소6408'),
      report.get('identity_verification_required', False)))
  checked=report.get('wrong_space_checked_event_id')
  checks['wrong_space_db_unlinked']=(report.get('wrong_space_unlinked_verified') is True
      and isinstance(checked,str) and any(row.get('correction_of_event_id')==checked
          and verified_demo_match(row,entries[0],report.get('expected_plate_number','91소6408'),
              report.get('identity_verification_required',False))
          for row in report.get('space_deliveries',[]))) if len(set(entries))==1 else False
  checks['wrong_space_unlinked_at_exit']=fields.get('WRONG_SPACE_LINKED_ROWS')==0
 return checks


def valid_demo_delivery_shape(row):
    """미전송 억제·대기 기록의 null 응답과 실제 응답 객체를 구분합니다."""
    if not isinstance(row, dict) or not isinstance(row.get('payload'), dict):
        return False
    receipt = row.get('receipt')
    return (isinstance(receipt, dict) or ('receipt' in row and receipt is None
            and row.get('status') in ('HELD_RELEASE_REQUIRED', 'DISABLED', 'IN_FLIGHT', 'DELIVERY_UNKNOWN')))


def resolved_demo_delivery(row):
    if not valid_demo_delivery_shape(row) or row.get('blocking_reason'):
        return False
    receipt = row.get('receipt')
    if row.get('status') == 'HELD_RELEASE_REQUIRED':
        return receipt is None
    return (row.get('status') in ('APPLIED', 'UNCHANGED', 'HELD') and isinstance(receipt, dict)
            and receipt.get('state') == row['status']
            and receipt.get('receipt_verified') is True and receipt.get('request_attempted') is True)


def _parking_summary(path):
    # 유효한 JSON이라도 내부자료형이 손상됐으면 진단정보로만 취급합니다.
    parking = read_json(path)
    vehicle = parking.get('vehicle_space')
    if not isinstance(vehicle, dict) or not isinstance(vehicle.get('statistics'), dict):
        raise ValueError('Invalid parking snapshot structure')
    deliveries = vehicle.get('deliveries', [])
    if (not isinstance(deliveries, list) or any(not valid_demo_delivery_shape(row) for row in deliveries)):
        raise ValueError('Invalid parking delivery structure')
    identity = vehicle.get('entry_handoff')
    if identity is not None and not isinstance(identity, dict):
        raise ValueError('Invalid identity snapshot')
    return dict(b_status=parking.get('status'), occupancy_http_requests=parking.get('http_requests'),
                b_identity_status=vehicle.get('entry_handoff_status'), b_identity=identity,
                b_ocr_submitted=vehicle['statistics'].get('ocr_submitted'),
                b_identity_mode=vehicle['statistics'].get('identity_mode'), space_deliveries=deliveries)


def verified_demo_match(row, usage, plate, require_identity_verification=False):
    """같은 차량·이용·시험 구획의 검증된 연결 응답만 인정합니다."""
    if not isinstance(row, dict):
        return False
    if row.get('blocking_reason'):
        return False
    payload, receipt = row.get('payload'), row.get('receipt')
    if not isinstance(payload, dict) or not isinstance(receipt, dict):
        return False
    if require_identity_verification:
        proof = row.get('identity_verification')
        consensus = proof.get('plate_consensus') if isinstance(proof, dict) else None
        if (not isinstance(proof, dict) or proof.get('basis') != 'ENTRY_AND_B_PLATE_OCR'
                or proof.get('plate_number') != plate or not isinstance(proof.get('entry_event_id'), str)
                or not isinstance(consensus, dict) or consensus.get('status') != 'CONFIRMED'
                or consensus.get('plate_number') != plate
                or type(row.get('expected_parking_usage_id')) is not int
                or row['expected_parking_usage_id'] != usage):
            return False
    return (type(usage) is int and usage > 0
            and payload.get('event_type') == 'VEHICLE_SPACE_MATCH'
            and payload.get('plate_number') == plate and payload.get('space_code') == '999F-Z01'
            and type(payload.get('expected_parking_usage_id')) is int
            and payload['expected_parking_usage_id'] == usage
            and type(row.get('expected_parking_usage_id')) is int
            and row['expected_parking_usage_id'] == usage
            and isinstance(payload.get('event_id'), str) and bool(payload['event_id'])
            and receipt.get('event_id') == payload['event_id']
            and receipt.get('event_type') == payload['event_type']
            and receipt.get('receipt_verified') is True and receipt.get('request_attempted') is True
            and receipt.get('parking_decision') == 'MATCHED'
            and row.get('status') in ('APPLIED', 'UNCHANGED')
            and receipt.get('state') == row['status']
            and type(receipt.get('parking_usage_id')) is int and receipt['parking_usage_id'] == usage)


def demo_space_mapping(profile):
    """시험 프로세스 안에서만 사용할 허용 매핑입니다."""
    return ({'A-01': '999F-Z01', 'A-02': '999F-Z02'}
            if profile.get('scenario') == 'wrong_space_correction' else {'A-01': '999F-Z01'})


def verified_demo_wrong_space(row, usage, plate):
    if not isinstance(row, dict) or row.get('blocking_reason'):
        return False
    payload, receipt = row.get('payload'), row.get('receipt')
    if not isinstance(payload, dict) or not isinstance(receipt, dict):
        return False
    return (type(usage) is int and usage > 0 and row.get('status') == 'HELD'
            and payload.get('event_type') == 'VEHICLE_SPACE_MATCH'
            and payload.get('plate_number') == plate and payload.get('space_code') == '999F-Z02'
            and type(payload.get('expected_parking_usage_id')) is int
            and payload['expected_parking_usage_id'] == usage
            and type(row.get('expected_parking_usage_id')) is int
            and row['expected_parking_usage_id'] == usage
            and isinstance(payload.get('event_id'), str) and bool(payload['event_id'])
            and receipt.get('event_id') == payload['event_id']
            and receipt.get('event_type') == payload['event_type']
            and receipt.get('state') == 'HELD' and receipt.get('parking_decision') == 'WRONG_SPACE'
            and receipt.get('receipt_verified') is True and receipt.get('request_attempted') is True
            and type(receipt.get('parking_usage_id')) is int and receipt['parking_usage_id'] == usage)


def verified_demo_correction(deliveries, usage, plate, require_identity_verification=False):
    from ai_vision.recognition.vehicle_contract import parse_detected_at
    wrong = {row['payload']['event_id']: row for row in deliveries
             if verified_demo_wrong_space(row, usage, plate)}
    for row in deliveries:
        if not verified_demo_match(row, usage, plate, require_identity_verification):
            continue
        previous = wrong.get(row.get('correction_of_event_id'))
        if previous is None:
            continue
        try:
            if (parse_detected_at(row['payload']['detected_at']) >
                    parse_detected_at(previous['payload']['detected_at'])):
                return True
        except (KeyError, ValueError, TypeError):
            continue
    return False


def demo_phase(journal_rows, parking, plate, require_identity_verification=False, *,
               correction_required=False, wrong_space_unlinked=False, cycles=1):
    """화면 안내도 최종 판정과 같은 차량·이용의 응답을 근거로 합니다."""
    if cycles != 1:
        return _repeat_demo_phase(journal_rows, parking, plate, require_identity_verification, cycles)
    sent, received, entries, exits = {}, set(), set(), set()
    for row in journal_rows:
        if not isinstance(row, dict) or not isinstance(row.get('payload'), dict):
            continue
        event, receipt = row['payload'], row.get('receipt')
        event_id = event.get('event_id')
        if (event.get('event_type') != 'VEHICLE_PASSAGE' or event.get('plate_number') != plate
                or not isinstance(event_id, str) or not event_id):
            continue
        if row.get('stage') == 'BEFORE_SEND':
            sent[event_id] = event
            continue
        # 1. 이전 성공 기록이 있더라도 불명확한 새 전송을 성공 안내로 덮지 않습니다.
        if (row.get('stage') == 'RECEIPT' and sent.get(event_id) == event
                and isinstance(receipt, dict)
                and receipt.get('state') in ('DELIVERY_UNKNOWN', 'AUTH_REQUIRED', 'REJECTED')):
            return 'STOP: DELIVERY FAILED / NO RETRY'
        if (row.get('stage') != 'RECEIPT' or sent.get(event_id) != event
                or not isinstance(receipt, dict) or receipt.get('event_id') != event_id
                or receipt.get('event_type') != 'VEHICLE_PASSAGE'
                or receipt.get('state') != 'APPLIED' or receipt.get('receipt_verified') is not True
                or receipt.get('request_attempted') is not True
                or type(receipt.get('parking_usage_id')) is not int or receipt['parking_usage_id'] < 1):
            continue
        if event.get('direction') == 'ENTRY':
            entries.add(receipt['parking_usage_id'])
        elif event.get('direction') == 'EXIT':
            exits.add(receipt['parking_usage_id'])
        received.add(event_id)
    if len(entries) > 1 or (exits and exits != entries):
        return 'STOP: USAGE ID MISMATCH / NO RETRY'
    vehicle = parking.get('vehicle_space') if isinstance(parking, dict) else None
    deliveries = vehicle.get('deliveries') if isinstance(vehicle, dict) else None
    if isinstance(parking, dict) and (parking.get('status') == 'FAILED' or parking.get('error_type')):
        return 'STOP: B CAMERA FAILED / NO RETRY'
    if isinstance(deliveries, list) and any(
            isinstance(row, dict) and (row.get('blocking_reason')
                or row.get('status') in ('DELIVERY_UNKNOWN', 'AUTH_REQUIRED', 'REJECTED'))
            for row in deliveries):
        return 'STOP: SPACE DELIVERY FAILED / NO RETRY'
    if isinstance(deliveries, list) and any(
            isinstance(row, dict) and row.get('status') == 'IN_FLIGHT' for row in deliveries):
        return 'WAIT: SPACE RESPONSE PENDING / NO RETRY'
    if set(sent) != received:
        return 'WAIT: HTTP RESPONSE PENDING / NO RETRY'
    if not entries:
        return '1 ENTRY: NUMBER PLATE DOWN'
    matched = isinstance(deliveries, list) and any(
        verified_demo_match(row, next(iter(entries)), plate, require_identity_verification) for row in deliveries)
    if correction_required:
        wrong = [row for row in (deliveries or []) if verified_demo_wrong_space(row, next(iter(entries)), plate)]
        if matched and not verified_demo_correction(deliveries or [], next(iter(entries)), plate, require_identity_verification):
            return 'STOP: WRONG SPACE STEP NOT VERIFIED'
        if not wrong:
            return '2A PARK IN B A-02 / WAIT WRONG SPACE'
        if not wrong_space_unlinked:
            return 'WAIT: VERIFY WRONG SPACE UNLINKED IN DB'
        if not matched:
            return '2B MOVE TO B A-01 / WAIT MATCHED'
    if not matched:
        return '2 PARK IN B A-01 / HAND OFF'
    if exits:
        return '4 DONE / WAIT 5s THEN Q BOTH'
    return '3 REMOVE PHOTO / EXIT UP IN A'


def _repeat_demo_phase(rows, parking, plate, verify, cycles):
    """두 회차를 같은 프로세스에서 관찰하되 완료·신원·전송 근거는 회차별로 확인합니다."""
    if type(cycles) is not int or cycles != 2:
        return 'STOP: INVALID CYCLE COUNT'
    health = demo_phase([], parking, plate, verify)
    if health.startswith(('STOP:', 'WAIT:')):
        return health
    sent = {row['payload'].get('event_id') for row in rows if isinstance(row,dict)
            and isinstance(row.get('payload'),dict) and row.get('stage')=='BEFORE_SEND'}
    received = {row['payload'].get('event_id') for row in rows if isinstance(row,dict)
                and isinstance(row.get('payload'),dict) and row.get('stage')=='RECEIPT'}
    if any(isinstance(row.get('receipt'),dict) and row['receipt'].get('state') in
           ('DELIVERY_UNKNOWN','AUTH_REQUIRED','REJECTED') for row in rows):
        return 'STOP: DELIVERY FAILED / NO RETRY'
    if sent != received:
        return 'WAIT: HTTP RESPONSE PENDING / NO RETRY'
    try:
        entries, exits = _verified_passage_rows(rows,plate,cycles)
    except (ValueError,KeyError,TypeError,AttributeError):
        return 'STOP: REPEAT PASSAGE SEQUENCE REQUIRES REVIEW'
    vehicle=(parking or {}).get('vehicle_space') or {}
    deliveries=vehicle.get('deliveries',[])
    for usage in exits:
        if not any(verified_demo_match(row,usage,plate,verify) for row in deliveries):
            return 'STOP: EXIT WITHOUT VERIFIED PARKING'
    if len(entries)==len(exits):
        if entries and (vehicle.get('entry_handoff') or {}).get('status')!='EMPTY':
            return 'WAIT: B EXIT IDENTITY CLEAR'
        if len(exits)==cycles:
            return '4 DONE / WAIT 5s THEN Q BOTH'
        return f'CYCLE {len(entries)+1}/2 - 1 ENTRY: NUMBER PLATE DOWN'
    usage=entries[-1]
    current=[row for row in rows if (row.get('receipt') or {}).get('parking_usage_id')==usage]
    event_ids={row['payload']['event_id'] for row in current}
    current=[row for row in rows if row['payload']['event_id'] in event_ids]
    phase=demo_phase(current,parking,plate,verify)
    return f'CYCLE {len(entries)}/2 - '+phase


def finalize_trial(run_dir, report, *, children_stopped, fixture_prepared, db, expected_plate='91소6408'):
    """중단·정리 오류도 결과에 남깁니다. 불명확한 이용은 추정해 삭제하지 않습니다."""
    run_dir = Path(run_dir)
    manifest = run_dir / 'camera_e2e_fixture.properties'
    report = dict(report)
    report['match_contract_version'] = 2
    report['expected_plate_number'] = expected_plate
    report['success'] = False
    report['cleanup'] = 'NOT_EXECUTED: recovery review required'
    try:
        if not children_stopped:
            report['cleanup'] = 'NOT_EXECUTED: camera processes still active'
            return report
        values = read_fixture(manifest)
        if values is None:
            report['cleanup'] = ('NOT_EXECUTED: prepared fixture has no manifest' if fixture_prepared
                                 else 'NO_DB_FIXTURE_CREATED')
            return report
        if 'wrong_space' in values:
            report['scenario'] = 'wrong_space_correction'
        if values.get('cleaned') == 'true':
            # 이미 검증된 성공기록을 재점검 때문에 실패로 덮어쓰지 않습니다.
            try:
                previous = read_json(run_dir/'http_e2e_result.json')
                if previous.get('success') is True and all(evaluate_success(previous).values()):
                    report = previous
                    report['recovery_no_database_action'] = True
                    return report
            except (OSError, ValueError, UnicodeError):
                pass
            report['cleanup'] = 'ALREADY_CLEANED: no database action'
            return report
        for key in ('floor', 'zone', 'space', 'reservation', 'baseline_usage_count'):
            if not re.fullmatch(r'[0-9]+', values.get(key, '')):
                raise ValueError('Incomplete fixture ownership')
        if 'wrong_space' in values and (not re.fullmatch(r'[1-9][0-9]*', values['wrong_space'])
                or values['wrong_space'] == values['space']):
            raise ValueError('Invalid correction fixture ownership')
        if not re.fullmatch(r'AI_HTTP_TEST_[0-9a-f]{8}', values.get('marker', '')):
            raise ValueError('Unknown fixture marker')
        cycles=int(values.get('cycles','1'))
        if cycles not in (1,2) or (cycles==2 and 'wrong_space' in values):
            raise ValueError('Invalid fixture cycles')
        report['cycles']=cycles
        report['baseline_usage_count']=int(values['baseline_usage_count'])
        entries, exits = _verified_passages(run_dir/'gate_http_journal.jsonl', expected_plate, cycles)
        owned = set(entries)
        recorded = values.get('usage_ids') if cycles==2 else values.get('usage_id')
        expected_ids=','.join(str(value) for value in sorted(owned))
        if ('usage_ids' in values and cycles!=2) or ('usage_id' in values and cycles==2):
            raise ValueError('Mixed fixture usage formats')
        if recorded is not None and (not owned or recorded != expected_ids):
            raise ValueError('Recorded usage does not match verified journal')
        if owned and recorded is None:
            # 카메라 종료 후에만 소유가 검증된 이용 ID 목록을 기록합니다.
            with manifest.open('a', encoding='ascii') as stream:
                stream.write('\n'+('usage_ids' if cycles==2 else 'usage_id')+'='+expected_ids+'\n')
        report['verified_entry_usage_ids'] = entries
        report['verified_exit_usage_ids'] = exits
        try:
            report['database_before_cleanup'] = db('inspect')
        except Exception as error:
            report['inspection_error_type'] = type(error).__name__
        try:
            report.update(_parking_summary(run_dir/'parking/parking_camera_check.json'))
        except (OSError, ValueError, UnicodeError) as error:
            report['parking_snapshot_error_type'] = type(error).__name__
        # 선택적인 조회·결과파일 오류 때문에 소유권검증된 시험행 정리를 건너뛰지 않습니다.
        report['cleanup'] = db('cleanup')
        if 'REMAINING_SYNTHETIC_ROWS=0' not in report['cleanup']:
            raise RuntimeError('Cleanup confirmation is missing')
        report['entry_exit_same_usage'] = len(entries) == cycles and len(owned) == cycles and exits == entries
        report['actual_match_same_usage'] = len(owned) == cycles and all(any(
            verified_demo_match(row, usage, expected_plate, report.get('identity_verification_required',False))
            for row in report.get('space_deliveries', [])) for usage in owned)
        report['completion_checks'] = evaluate_success(report)
        report['success'] = all(report['completion_checks'].values())
        return report
    except Exception as error:
        report['recovery_error_type'] = type(error).__name__
        report['cleanup'] = 'NOT_EXECUTED_OR_UNCONFIRMED: recovery review required'
        return report
    finally:
        report['incomplete_reasons'] = [key for key, value in report.get('completion_checks', {}).items() if not value]
        if not report['success'] and not report['incomplete_reasons']:
            report['incomplete_reasons'] = [report.get('recovery_error_type') or report['cleanup']]
        # 저장 자체가 불가능하면 예외를 숨기지 않습니다. DB 소유권 정보는 별도 보존됩니다.
        write_json_atomic(run_dir/'http_e2e_result.json', report)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='시험 결과·미정리 매니페스트 읽기 전용 점검')
    parser.add_argument('--check-profile', action='store_true', help='로컬 실행 프로필도 검증')
    parser.add_argument('--status', type=Path, required=True, help='회차 폴더들이 있는 시험 프로필 경로')
    args = parser.parse_args(argv)
    if not args.status.is_dir():
        parser.error('시험 프로필 폴더가 없습니다.')
    if args.check_profile:
        load_demo_profile(args.status)
    pending = [str(path) for path in sorted(args.status.rglob('camera_e2e_fixture.properties')) if fixture_pending(path)]
    print(json.dumps({'read_only':True,'pending_count':len(pending),'pending_manifests':pending},ensure_ascii=False))
    return 2 if pending else 0


if __name__ == '__main__':
    raise SystemExit(main())

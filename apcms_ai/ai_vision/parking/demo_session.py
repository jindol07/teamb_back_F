"""한 대 시연의 종료·정리 판정. 카메라/DB는 직접 열지 않고 호출자가 제공한 정리 함수만 사용합니다."""

import json
import re
from pathlib import Path

from ai_vision.recognition.local_io import read_json, write_json_atomic


def load_demo_profile(directory):
    """카메라 배치·시험 대상을 로컬 파일에서 읽고 실행 전에 검증합니다."""
    from urllib.parse import urlsplit
    from ai_vision.recognition.tracking_config import validate_config
    from ai_vision.parking.parking_validation import validate_spaces
    root = Path(directory).resolve()
    config = read_json(root/'demo.local.json')
    required = {'version', 'gate_camera', 'parking_camera', 'seconds', 'plate_number',
                'expected_db_url', 'boot_context_url', 'gate_config', 'spaces_config', 'reference'}
    if set(config) != required or type(config['version']) is not int or config['version'] != 1:
        raise ValueError('Unsupported or incomplete demo profile')
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
    validate_spaces(read_json(config['spaces_config']))
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


def _verified_passages(path, expected_plate):
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
            (entries if event['direction'] == 'ENTRY' else exits).append(receipt['parking_usage_id'])
        else:
            raise ValueError('Invalid journal stage')
    if set(sent) != set(received) or len(set(entries)) > 1 or (exits and set(exits) != set(entries)):
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
 # 이 테스트는 인쇄차량의 기존4건이 모두출차상태인 조건에서 새이용1건만 생성합니다.
 checks['database_exit_confirmed']=(len(set(entries))==1 and fields.get('USAGE_ROWS',0)>0
     and fields.get('OPEN_ROWS')==0 and fields.get('EXITED_ROWS')==fields.get('USAGE_ROWS'))
 checks['fixture_cleaned']='REMAINING_SYNTHETIC_ROWS=0' in report.get('cleanup','')
 return checks


def _parking_summary(path):
    # 유효한 JSON이라도 내부자료형이 손상됐으면 진단정보로만 취급합니다.
    parking = read_json(path)
    vehicle = parking.get('vehicle_space')
    if not isinstance(vehicle, dict) or not isinstance(vehicle.get('statistics'), dict):
        raise ValueError('Invalid parking snapshot structure')
    deliveries = vehicle.get('deliveries', [])
    if (not isinstance(deliveries, list) or any(not isinstance(row, dict)
            or not isinstance(row.get('payload'), dict) or not isinstance(row.get('receipt'), dict)
            for row in deliveries)):
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
            and isinstance(payload.get('event_id'), str) and bool(payload['event_id'])
            and receipt.get('event_id') == payload['event_id']
            and receipt.get('event_type') == payload['event_type']
            and receipt.get('receipt_verified') is True and receipt.get('request_attempted') is True
            and row.get('status') in ('APPLIED', 'UNCHANGED')
            and receipt.get('state') == row['status']
            and type(receipt.get('parking_usage_id')) is int and receipt['parking_usage_id'] == usage)


def demo_phase(journal_rows, parking, plate, require_identity_verification=False):
    """화면 안내도 최종 판정과 같은 차량·이용의 응답을 근거로 합니다."""
    sent, entries, exits = {}, set(), set()
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
    if len(entries) > 1 or (exits and exits != entries):
        return 'STOP: USAGE ID MISMATCH / NO RETRY'
    if not entries:
        return '1 ENTRY: NUMBER PLATE DOWN'
    vehicle = parking.get('vehicle_space') if isinstance(parking, dict) else None
    deliveries = vehicle.get('deliveries') if isinstance(vehicle, dict) else None
    matched = isinstance(deliveries, list) and any(
        verified_demo_match(row, next(iter(entries)), plate, require_identity_verification) for row in deliveries)
    if not matched:
        return '2 PARK IN B A-01 / HAND OFF'
    if exits:
        return '4 DONE / WAIT 5s THEN Q BOTH'
    return '3 REMOVE PHOTO / EXIT UP IN A'


def finalize_trial(run_dir, report, *, children_stopped, fixture_prepared, db, expected_plate='91소6408'):
    """중단·정리 오류도 결과에 남깁니다. 불명확한 이용은 추정해 삭제하지 않습니다."""
    run_dir = Path(run_dir)
    manifest = run_dir / 'camera_e2e_fixture.properties'
    report = dict(report)
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
        if not re.fullmatch(r'AI_HTTP_TEST_[0-9a-f]{8}', values.get('marker', '')):
            raise ValueError('Unknown fixture marker')
        entries, exits = _verified_passages(run_dir/'gate_http_journal.jsonl', expected_plate)
        owned = set(entries)
        recorded = values.get('usage_id')
        if recorded is not None and (not owned or recorded != str(next(iter(owned)))):
            raise ValueError('Recorded usage does not match verified journal')
        if owned and recorded is None:
            # 카메라 종료 후에만 소유가 검증된 이용ID를 기록합니다.
            with manifest.open('a', encoding='ascii') as stream:
                stream.write('\nusage_id='+str(next(iter(owned)))+'\n')
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
        report['entry_exit_same_usage'] = len(owned) == 1 and exits == entries
        report['actual_match_same_usage'] = len(owned) == 1 and any(
            verified_demo_match(row, next(iter(owned)), expected_plate, report.get('identity_verification_required',False))
            for row in report.get('space_deliveries', []))
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

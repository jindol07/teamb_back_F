"""시험 오류의 원인과 사용자 중단을 비밀 정보 없이 구분합니다."""
MESSAGES={
    'SPACE_RELEASE_DISABLED':'배포 관리자 Boot에서 --parking.ai.space-release-enabled=true 활성화와 재시작이 필요합니다. 예약·카메라는 시작하지 않았습니다.',
    'RELEASE_CHECK_FAILED':'배포 해제 API의 인증·연결·호환성을 확인하지 못해 시작을 보류합니다.',
    'BACKEND_POLICY_CHANGED':'배포 서버의 주차 연결 정책이 기존 시험 계약과 달라 시작을 보류합니다. 정책을 맞춘 뒤 실행하세요.',
    'ACTIVE_USAGE_EXISTS':'미출차 이용 기록이 남아 있어 시작하지 않았습니다. 기존 시험 이용을 확인해야 합니다.',
    'RESERVATION_CONFLICT':'다른 예약과 겹쳐 시작하지 않았습니다.',
    'SPACE_UNAVAILABLE':'네 구획의 상태 또는 매핑이 달라 시작하지 않았습니다.',
    'DB_OPERATION_FAILED':'DB 작업에 실패했습니다. 실행 폴더의 해당 DB 로그를 확인하세요.',
}


class FixtureFailure(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(MESSAGES[code])


def fixture_failure(stderr):
    for needle,code in (('Active usage exists','ACTIVE_USAGE_EXISTS'),
                        ('Reservation conflict','RESERVATION_CONFLICT'),
                        ('Spaces unavailable or mapping changed','SPACE_UNAVAILABLE')):
        if needle in stderr:
            error=FixtureFailure(code)
            if code=='ACTIVE_USAGE_EXISTS':
                import re
                found=re.search(r'ACTIVE_USAGE_IDS=([0-9,]{1,256})(?:\s|$)',stderr)
                if found:
                    error.args=(str(error)+' (이용 ID: '+found.group(1)+')',)
            return error
    return FixtureFailure('DB_OPERATION_FAILED')


def result_exit_code(report):
    if report.get('success'):
        report['status']='COMPLETED';return 0
    if report.get('cancelled'):
        bad_cleanup=(report.get('reservation_cleanup_error') or report.get('automatic_cleanup_error') or
                     report.get('runtime_final',{}).get('state')=='FAILED' or
                     report.get('fire_final',{}).get('state')=='FAILED')
        report['status']='CANCELLED_WITH_CLEANUP_ERROR' if bad_cleanup else 'CANCELLED'
        return 1 if bad_cleanup else 130
    if report.get('error_code') in ('ACTIVE_USAGE_EXISTS','RESERVATION_CONFLICT','SPACE_UNAVAILABLE','BACKEND_POLICY_CHANGED','SPACE_RELEASE_DISABLED','RELEASE_CHECK_FAILED'):
        report['status']='BLOCKED';return 2
    report['status']='FAILED';return 1


def final_completion_checks(report, parking_report, gate_report):
    """업무 단계 완료와 네 작업자의 정상 종료를 별도로 검사합니다."""
    def workers(state):
        rows=state.get('processes',[])
        return len(rows)==2 and all(row.get('alive') is False and type(row.get('exit_code')) is int
                                   and row['exit_code']==0 for row in rows)
    runtime=report.get('runtime_final') or {};fire=report.get('fire_final') or {}
    return {
        'sequence_complete':report.get('sequence_complete') is True,
        'no_execution_error':not report.get('error_type'),
        'camera_continuity':report.get('camera_continuity_verified') is True,
        'parking_delivery_paused':report.get('parking_delivery_paused') is True,
        'fire_ack_both':report.get('gate_fire_ack') is True and report.get('parking_fire_ack') is True,
        'exit_database_verified':report.get('exit_db',{}).get('USAGE_ROWS')=='1' and report.get('exit_db',{}).get('EXITED_ROWS')=='1',
        'runtime_stopped':runtime.get('state')=='STOPPED' and not runtime.get('reason'),
        'camera_workers_exit_zero':workers(runtime),
        'fire_stopped':fire.get('state')=='STOPPED' and not fire.get('reason'),
        'fire_workers_exit_zero':workers(fire),
        'parking_report_clean':parking_report.get('status')=='STOPPED' and not parking_report.get('error_type'),
        'gate_report_clean':gate_report.get('status')=='STOPPED' and not gate_report.get('error_type')
                            and gate_report.get('cleanup_errors')==0,
        'cleanup_confirmed':not report.get('reservation_cleanup_error') and not report.get('automatic_cleanup_error'),
    }

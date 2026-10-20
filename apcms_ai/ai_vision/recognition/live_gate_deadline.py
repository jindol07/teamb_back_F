# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/live_gate_deadline.py

"""새 카메라 읽기를 시작하기 전에 실행 시간 한도를 검사합니다."""

# 1. 시간 측정에 사용할 표준 라이브러리
# 1-1. math: NaN(숫자가 아님), 무한대 등 잘못된 시간 입력을 걸러냅니다.
# 1-2. time: 운영체제 시계가 조정되어도 시간 간격 측정에 적합한 monotonic()을 제공합니다.
import math
import time


# 2. 시계 값과 실행 시간 설정을 검증하는 공통 함수
# 2-1. _number(value): 숫자 타입이며 유한하고 0 이상 1조 미만인지 검사합니다.
# bool은 int의 하위 클래스이지만 시간 입력으로 인정하지 않습니다.
# 함수 설명: _number() — 시간 관련 값이 실수/정수이면서 유한하고 정해진 범위인지 검사합니다.
def _number(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
            not math.isfinite(value) or not 0 <= value < 1e12):
        raise ValueError("시간 제한 시계 값이 올바르지 않습니다.")
    return value


# 3. 카메라 read()를 새로 호출해도 되는지 판단하는 시간 제한 관리자
# 이 클래스는 읽기 '시작 전'에 시간을 검사합니다. 이미 진행 중인 카메라 읽기를 강제로 중단하지는 않습니다.
class LiveGateDeadline:
    # 3-1. 실행 허용 시간과 시계 함수를 저장하고 시작 시각을 기록합니다.
    # reader를 주입하면 테스트에서 가짜 시계를 사용하여 경과 시간을 재현할 수 있습니다.
    # 함수 설명: __init__() — 시간 제한, 단조 시계 함수, 시작 시각 및 집계 상태를 초기화합니다.
    def __init__(self, seconds, reader=None):
        # 허용 시간은 0초보다 크고 300초 이하여야 합니다.
        if not 0 < _number(seconds) <= 300:
            raise ValueError("실행 제한은 0초 초과 300초 이하여야 합니다.")
        self.seconds = seconds
        self.reader = time.monotonic if reader is None else reader
        self.start = _number(self.reader())
        # last: 직전 검사 시각 / checks: 검사 횟수 / expired: 마지막 검사에서 만료되었는지
        self.last, self.checks, self.expired = self.start, 0, False

    # 3-2. 다음 카메라 프레임을 읽기 직전에 호출합니다.
    # 반환값이 True이면 제한 시간이 지났으므로 새 read()를 시작하지 않아야 합니다.
    # 함수 설명: before_read() — 새 프레임 read 이전에 제한 시간을 초과했는지 반환합니다.
    def before_read(self):
        # 수집 시각·성능 측정과 분리된 시계이므로 프레임 타임스탬프를 변경하지 않습니다.
        current = _number(self.reader())
        # 시간이 뒤로 이동하면 경과 시간의 신뢰성이 사라져 오류를 발생시킵니다.
        if current < self.last:
            raise ValueError("시간 제한 시계가 역행했습니다.")
        self.last = current
        self.checks += 1
        # 경과 시간이 설정한 seconds 이상이면 만료(True)입니다.
        self.expired = current - self.start >= self.seconds
        return self.expired

    # 3-3. 몇 번 검사했으며 언제 만료되었는지 결과 파일용 딕셔너리를 만듭니다.
    # 함수 설명: summary() — 읽기 경계에서 수행한 검사 횟수와 마지막 경과 시각을 보고합니다.
    def summary(self):
        # 마지막 '읽기 전' 검사까지만 측정합니다. 저장·종료까지 포함한 전체 실행 시간은 아닙니다.
        return {"scope": "READ_BOUNDARY_CHECKS_ONLY", "seconds": self.seconds, "checks": self.checks,
                "last_checked_elapsed_seconds": self.last - self.start, "expired_before_read": self.expired}


# 4. 저장된 시간 제한 결과의 형식 및 수치 일관성 검사
# 4-1. validate_deadline(value): summary()와 같은 다섯 필드가 정확히 들어 있는지 검사합니다.
# 함수 설명: validate_deadline() — 저장된 기한 진단 정보의 필드와 수치의 일치 여부를 검사합니다.
def validate_deadline(value):
    keys = {"scope", "seconds", "checks", "last_checked_elapsed_seconds", "expired_before_read"}
    # 필드의 누락·추가와 다른 측정 범위(scope)를 허용하지 않습니다.
    if not isinstance(value, dict) or set(value) != keys or value["scope"] != "READ_BOUNDARY_CHECKS_ONLY":
        raise ValueError("읽기 전 시간 제한 검사 형식이 올바르지 않습니다.")
    # 4-2. 저장된 제한 시간과 마지막 경과 시간을 숫자로 검증합니다.
    seconds, elapsed = _number(value["seconds"]), _number(value["last_checked_elapsed_seconds"])
    # 4-3. 검사 횟수, 만료 여부와 경과 시간의 관계가 모순되지 않는지 확인합니다.
    # 예: elapsed >= seconds이면 만료값도 반드시 True여야 합니다.
    if (not 0 < seconds <= 300 or type(value["checks"]) is not int or not 0 <= value["checks"] <= 100000 or
            type(value["expired_before_read"]) is not bool or
            value["expired_before_read"] != (elapsed >= seconds) or (value["checks"] == 0 and elapsed != 0)):
        raise ValueError("읽기 전 시간 제한 검사 수치가 일치하지 않습니다.")
    # 반환값은 호출자가 원본 딕셔너리를 수정하지 않도록 얕게 복사합니다.
    return dict(value)

"""공유 감시의 알림 처리. 네트워크 장애 동안 감지는 유지하고 미전송 근거를 보존합니다."""
import time
from ai_vision.safety.fire_alert_live import delivery_cycle


def process_alerts(output,finished,errors,delivery=None,*,cycle=None,clock=None):
    cycle=delivery_cycle if cycle is None else cycle
    clock=time.monotonic if clock is None else clock
    seen=set();next_try=0
    options=dict(preview_ids=seen)
    if delivery:
        options.update(send=True,url=delivery['url'],token=delivery['token'],
                       allow_test_records=True,timeout=3,max_retries=1)
    while not finished.wait(.25):
        if clock()<next_try:continue
        try:cycle(output,**options)
        except (OSError,ValueError,RuntimeError) as error:
            # 1. 오류 본문에 인증정보가 포함될 가능성을 피하고 종류만 기록합니다.
            print('[공유 알림 재시도] '+type(error).__name__,flush=True)
            next_try=clock()+2
    try:cycle(output,**options)
    except (OSError,ValueError,RuntimeError) as error:errors.append(type(error).__name__)

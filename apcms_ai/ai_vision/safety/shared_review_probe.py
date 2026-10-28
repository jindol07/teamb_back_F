"""공유 프레임 시험 감시의 일시적인 읽기 잠금만 제한 재시도합니다."""
import time
from ai_vision.parking.frame_exchange import read_latest


def probe_latest(path, *, reader=None, pause=None, attempts=5):
    reader=read_latest if reader is None else reader
    pause=time.sleep if pause is None else pause
    if type(attempts) is not int or not 1 <= attempts <= 10:
        raise ValueError('再試行回数は1~10回です。')
    for index in range(attempts):
        try:
            return reader(path)
        except PermissionError:
            if index+1 < attempts:
                pause(.05)
    # 1. 古い画像を再使用せず、この標本を未取得として記録します。
    return None

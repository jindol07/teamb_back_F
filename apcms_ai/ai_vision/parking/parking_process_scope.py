"""주차 런타임이 직접 생성한 작업 트리만 격리·정리합니다."""
import os
import signal
import subprocess


def isolate_worker():
    # 1. Linux에서는 OCR 하위 프로세스도 같은 전용 그룹을 상속합니다.
    if os.name != "nt":
        os.setsid()


def terminate_worker_tree(process, *, platform=None):
    if not process.is_alive():
        return True
    platform = os.name if platform is None else platform
    pid = process.pid
    if type(pid) is not int or pid <= 0:
        raise ValueError("직접 생성한 작업의 PID가 필요합니다.")
    tree_signal_sent = False
    try:
        if platform == "nt":
            # 2. 전체 python/콘솔에 신호를 보내지 않고 소유한 PID 트리만 종료합니다.
            result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                timeout=5, capture_output=True, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            tree_signal_sent = result.returncode == 0
        elif os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGTERM)
            tree_signal_sent = True
    except (OSError, subprocess.SubprocessError):
        pass
    if not tree_signal_sent and process.is_alive():
        process.terminate()
    process.join(timeout=3)
    if process.is_alive():
        return False
    if platform != "nt" and tree_signal_sent:
        try:
            os.killpg(pid, 0)
            return False
        except ProcessLookupError:
            return True
        except OSError:
            return False
    # 트리 종료가 확인되지 않은 단일 프로세스 fallback은 정상으로 숨기지 않습니다.
    return tree_signal_sent

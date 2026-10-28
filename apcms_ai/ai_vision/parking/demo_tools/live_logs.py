"""작업자 로그 파일을 유지하면서 터미널에도 새 줄을 즉시 전달합니다."""
import codecs
import re


class LiveLogTail:
    def __init__(self, path, label, emit=print, *, concise=False):
        self.stream = path.open('rb')
        self.label = label
        self.emit = emit
        self.concise = concise
        self.in_traceback = False
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.pending = ''

    def drain(self, final=False):
        self.pending += self.decoder.decode(self.stream.read(), final=final)
        lines = self.pending.split('\n')
        self.pending = lines.pop()
        for line in lines:
            self._emit_line(line.rstrip(chr(13)))
        if final and self.pending:
            self._emit_line(self.pending)
            self.pending = ''

    def _emit_line(self, line):
        # 1. 원본 파일은 유지하고 콘솔에만 업무 상태와 실제 오류를 전달합니다.
        if self.concise:
            if line.startswith('Traceback (most recent call last):'):
                self.in_traceback = True
            error = bool(re.search(r'(?:[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception):|ORA-\d{5}|HTTP[^\n]*[45][0-9]{2})', line))
            status = line.startswith(('[상태 확정]', '통과 차량 ', '실행 실패:', '오류 종류:', '세션 종료:', '주차면 검사:', 'A_CAMERA_RELEASED', 'B_CAMERA_RELEASED'))
            if not (self.in_traceback or error or status):
                return
        self.emit(f'[{self.label}] {line}', flush=True)

    def close(self):
        self.stream.close()

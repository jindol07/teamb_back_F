import tempfile
import unittest
from pathlib import Path
from ai_vision.parking.demo_tools.live_logs import LiveLogTail


class LiveDemoLogTests(unittest.TestCase):
    def test_incremental_korean_lines_are_not_lost_or_duplicated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'worker.log'
            path.write_bytes(b'')
            output = []
            tail = LiveLogTail(path, 'GATE', lambda text, **kw: output.append(text))
            raw = '입차 완료\n종료'.encode('utf-8')
            with path.open('ab', buffering=0) as stream:
                stream.write(raw[:2]); tail.drain()
                self.assertEqual(output, [])
                stream.write(raw[2:]); tail.drain(); tail.drain()
            self.assertEqual(output, ['[GATE] 입차 완료'])
            tail.drain(final=True)
            self.assertEqual(output, ['[GATE] 입차 완료', '[GATE] 종료'])
            tail.close()

    def test_worker_labels_and_crlf_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'worker.log'
            path.write_bytes(b'EMPTY\r\nOCCUPIED\n')
            output = []
            tail = LiveLogTail(path, 'PARKING', lambda text, **kw: output.append(text))
            try: tail.drain(final=True)
            finally: tail.close()
            self.assertEqual(output, ['[PARKING] EMPTY', '[PARKING] OCCUPIED'])

    def test_concise_output_keeps_events_and_errors_but_hides_model_noise(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'worker.log'
            lines = ['Creating model: example', 'Model files already exist.',
                     'UserWarning: No ccache found.', '\ufffd Windows message',
                     '[상태 확정] A-01: OCCUPIED', '통과 차량 1 / 번호판 91소6408',
                     'RuntimeError: camera failed', 'HTTP status 503']
            path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
            output = []
            tail = LiveLogTail(path, 'GATE', lambda text, **kw: output.append(text), concise=True)
            try: tail.drain(final=True)
            finally: tail.close()
            self.assertEqual(output, ['[GATE] '+line for line in lines[4:]])

    def test_concise_output_preserves_full_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'worker.log'
            lines = ['Traceback (most recent call last):', '  File demo.py, line 1', 'ValueError: invalid']
            path.write_text('\n'.join(lines), encoding='utf-8')
            output = []
            tail = LiveLogTail(path, 'PARKING', lambda text, **kw: output.append(text), concise=True)
            try: tail.drain(final=True)
            finally: tail.close()
            self.assertEqual(output, ['[PARKING] '+line for line in lines])

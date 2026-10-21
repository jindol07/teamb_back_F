# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/local_io.py

"""로컬 결과를 엄격하게 읽고 JSON 저장 중 파일 손상을 줄이는 공통 함수."""

import json
import os
import tempfile
import math
import time
from pathlib import Path


def _reject_constant(value):
    raise ValueError(f"JSON에 유효하지 않은 숫자가 있습니다: {value}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON 항목이 중복되었습니다: {key}")
        result[key] = value
    return result


def decode_object(text):
    # 1. NaN/무한대와 중복 키를 허용하지 않아 손상된 결과를 정상으로 읽지 않음
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("JSON 숫자가 표현 가능한 범위를 초과했습니다.")
        return number
    try:
        value = json.loads(text, parse_constant=_reject_constant, parse_float=finite_float,
                           object_pairs_hook=_unique_object)
    except RecursionError as error:
        raise ValueError("JSON의 중첩 깊이가 처리 한도를 초과했습니다.") from error
    if not isinstance(value, dict):
        raise ValueError("JSON 최상위 값은 객체여야 합니다.")
    # 외부 라이브러리가 Python 재귀 한도를 바꿔도 허용 깊이는 일정하게 유지합니다.
    stack = [(iter((value,)), 0)]
    while stack:
        iterator, depth = stack[-1]
        try:
            item = next(iterator)
        except StopIteration:
            stack.pop()
            continue
        if isinstance(item, (dict, list)):
            if depth >= 128:
                raise ValueError("JSON의 중첩 깊이가 처리 한도를 초과했습니다.")
            stack.append((iter(item.values() if isinstance(item, dict) else item), depth + 1))
    return value


def read_json(path, max_bytes=4 * 1024 * 1024):
    path = Path(path)
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("JSON 읽기 한도는 양의 정수여야 합니다.")
    # 1-1. 크기 확인 후 파일이 커지더라도 실제 읽기는 상한+1바이트로 제한합니다.
    with path.open("rb") as handle:
        content = handle.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ValueError("JSON 파일이 허용 크기를 초과했습니다.")
    return decode_object(content.decode("utf-8-sig"))


def iter_jsonl(path, max_rows=200000, max_line_bytes=1024 * 1024):
    # 2. 전체 관찰 로그를 한꺼번에 문자열로 올리지 않고 한 줄씩 읽습니다.
    with Path(path).open("rb") as handle:
        count, line_number = 0, 0
        while True:
            line = handle.readline(max_line_bytes + 1)
            if not line:
                break
            line_number += 1
            if len(line) > max_line_bytes:
                raise ValueError(f"JSONL {line_number}번째 줄이 너무 큽니다.")
            if not line.strip():
                continue
            count += 1
            if count > max_rows:
                raise ValueError("JSONL 기록 수가 허용 범위를 초과했습니다.")
            try:
                yield decode_object(line.decode("utf-8-sig"))
            except (ValueError, UnicodeError) as error:
                raise ValueError(f"JSONL {line_number}번째 줄을 확인해 주세요: {error}") from error


def write_json_atomic(path, value):
    # 3. 같은 폴더의 임시 파일에 먼저 완성하고 교체해 반쪽짜리 JSON 노출을 줄임
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".json-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        # Windows에서 백신·인덱서가 파일을 잠깐 열어 둔 경우에만 짧게 재시도
        for attempt in range(4):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(.025 * (attempt + 1))
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

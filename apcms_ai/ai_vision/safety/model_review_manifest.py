"""모델 비교 자료를 해시·장면 단위로 고정합니다. 학습 라벨 형식이 아닙니다."""
import hashlib
import json
import re
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_case(case):
    if file_sha256(case['path']) != case['sha256']:
        raise ValueError('고정 이후 평가 자료가 변경됐습니다: ' + case['case_id'])


def load_review_manifest(path):
    # 1. 정답 박스가 없는 진단 자료를 학습셋·정확도 평가셋으로 혼동하지 않습니다.
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if (not isinstance(data, dict) or data.get('purpose') != 'diagnostic_review'
            or not isinstance(data.get('cases'), list) or not data['cases']):
        raise ValueError('비어 있지 않은 diagnostic_review 자료 목록이 필요합니다.')
    seen_ids, seen_hashes, cases = set(), set(), []
    for source in data['cases']:
        if not isinstance(source, dict):
            raise ValueError('평가 항목은 사전이어야 합니다.')
        case = dict(source)
        case_id, group = case.get('case_id'), case.get('source_group')
        if (not isinstance(case_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', case_id)
                or case_id in seen_ids or not isinstance(group, str) or not group.strip()):
            raise ValueError('평가 ID 중복·경로 문자 또는 원본 장면 정보를 확인하세요.')
        expected = case.get('expected')
        if (not isinstance(expected, list) or any(k not in ('FIRE', 'SMOKE') for k in expected)
                or len(expected) != len(set(expected))):
            raise ValueError('예상 클래스는 FIRE/SMOKE의 중복 없는 목록입니다. 정상은 빈 목록입니다.')
        media = case.get('media_type')
        raw_path = case.get('path')
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError('평가 파일 경로가 필요합니다.')
        case['path'] = (path.parent / raw_path).resolve()
        extensions = {'image': {'.jpg', '.jpeg', '.png'}, 'video': {'.mp4'}}
        if media not in extensions or case['path'].suffix.lower() not in extensions[media]:
            raise ValueError('평가 미디어 형식을 확인하세요.')
        sha = case.get('sha256')
        if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha) or sha in seen_hashes:
            raise ValueError('자료 해시가 잘못됐거나 같은 파일이 중복됐습니다.')
        verify_case(case)
        seen_ids.add(case_id)
        seen_hashes.add(sha)
        cases.append(case)
    return cases

"""고정된 원본과 수동 검토 영역만 읽습니다. 학습·일반 정확도 자료가 아닙니다."""
import json
from pathlib import Path
from ai_vision.safety.model_review_manifest import file_sha256
from ai_vision.safety.region_review import valid_box


def load_regions(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('purpose')!='manual_smoke_region_diagnostic' or not data.get('cases'):
        raise ValueError('명시적인 연기 영역 진단 목록이 필요합니다.')
    seen=set()
    for case in data['cases']:
        if case['id'] in seen:raise ValueError('중복 자료 ID')
        seen.add(case['id'])
        image=Path(case['path'])
        if not image.is_file() or file_sha256(image)!=case['sha256']:raise ValueError('원본 변경 또는 누락')
        for box in case['positives']+case['negatives']:
            if not valid_box(box):raise ValueError('잘못된 검토 영역')
    return data['cases']

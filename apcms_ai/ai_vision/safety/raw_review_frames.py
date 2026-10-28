"""사용자가 켠 제한된 시험에서만 분석 원본 프레임을 보존합니다."""
import json
from pathlib import Path
import cv2


class RawReviewFrames:
    def __init__(self, directory, limit=600):
        if type(limit) is not int or not 1 <= limit <= 600:
            raise ValueError('원본 저장 한도는 1~600장이어야 합니다.')
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=False)
        self.limit=limit
        self.count=0

    def __call__(self, frame):
        if self.count >= self.limit:
            return
        path=self.directory/f'frame_{self.count+1:05d}.png'
        if not cv2.imwrite(str(path),frame):
            raise OSError('분석 원본 저장 실패')
        self.count+=1
        (self.directory/'index.json').write_text(json.dumps({
            'count':self.count,'limit':self.limit,'format':'PNG_BGR_SOURCE_BEFORE_OVERLAY',
            'limit_reached':self.count==self.limit}),encoding='utf-8')

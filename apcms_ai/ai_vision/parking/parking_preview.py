# D:/finalProjectB/back/apcms_ai/ai_vision/parking/parking_preview.py
"""주차 카메라 구도 확인과 수동 시작 화면입니다."""

import cv2
import numpy as np
from ai_vision.camera_runtime import require_display


class ParkingPreview:
    def __init__(self, config=None, enable_http=False, source_label=None):
        require_display()
        self.config = config
        self.name = 'APCMS Parking Camera'
        self.enable_http = enable_http
        self.source_label = source_label

    def show(self, frame, preparing=False):
        # 1. 원본 영상은 변경하지 않고 좌표와 조작 안내만 덧그립니다.
        image = frame.copy()
        if self.config is not None:
            expected = (self.config['image_height'], self.config['image_width'])
            if frame.shape[:2] != expected:
                raise ValueError('웹캠과 주차면 좌표의 해상도가 다릅니다.')
            for space in self.config['spaces']:
                points = np.asarray(space['points'], dtype=np.int32)
                cv2.polylines(image, [points], True, (0, 255, 255), 2)
        text = 'SPACE: start / Q: cancel' if preparing else 'Q: stop'
        if self.enable_http:
            text = 'LIVE HTTP | ' + text
        cv2.putText(image, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 0), 2)
        if self.source_label:
            cv2.putText(image, self.source_label, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 2)
        cv2.imshow(self.name, image)
        key = cv2.waitKey(1) & 0xff
        if cv2.getWindowProperty(self.name, cv2.WND_PROP_VISIBLE) < 1:
            return ord('q')
        return key

    def wait_until_ready(self, capture):
        # 2. 준비 시간은 측정 시간에 포함하지 않습니다.
        print('카메라를 고정하고 구도를 맞추세요. 스페이스바: 시작 / Q: 취소')
        while True:
            ok, frame = capture.read()
            if not ok:
                raise OSError('준비 화면을 읽을 수 없습니다.')
            key = self.show(frame, preparing=True)
            if key == ord('q'):
                return None
            if key == ord(' '):
                return frame

    def close(self):
        # 3. 다른 카메라 프로그램의 창은 닫지 않습니다.
        try:
            cv2.destroyWindow(self.name)
        except cv2.error:
            pass

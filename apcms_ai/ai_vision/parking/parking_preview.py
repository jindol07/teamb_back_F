# D:/finalProjectB/back/apcms_ai/ai_vision/parking/parking_preview.py
"""주차 카메라 구도 확인과 수동 시작 화면입니다."""

import cv2
import numpy as np
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
from ai_vision.camera_runtime import require_display


@lru_cache(maxsize=16)
def _guidance_font(size):
    for path in (Path('C:/Windows/Fonts/malgun.ttf'),
                 Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')):
        if path.is_file():
            try:
                return ImageFont.truetype(str(path),size)
            except OSError:
                continue
    return None


@lru_cache(maxsize=32)
def _guidance_panel(width,height,guidance):
    """같은 단계의 글꼴 측정·문자 렌더링을 매 프레임 반복하지 않습니다."""
    size=max(14,min(36,width//32))
    font=_guidance_font(size)
    scale=size/30
    measure=(lambda value:font.getlength(value)) if font else (lambda value:cv2.getTextSize(value,cv2.FONT_HERSHEY_SIMPLEX,scale,1)[0][0])
    lines=[]
    for korean,english in guidance:
        value=korean if font else english
        line=''
        for character in value:
            if line and measure(line+character)>max(20,width-32):
                lines.append(line);line=''
            line+=character
        if line:lines.append(line)
    spacing=size+10
    panel_height=min(height,len(lines)*spacing+16)
    image=np.full((panel_height,width,3),16,dtype=np.uint8)
    top=0
    if font:
        canvas=Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGR2RGB))
        draw=ImageDraw.Draw(canvas)
        for index,line in enumerate(lines):draw.text((12,top+6+index*spacing),line,font=font,fill=(255,255,0))
        panel=cv2.cvtColor(np.asarray(canvas),cv2.COLOR_RGB2BGR)
        panel.setflags(write=False)
        return panel
    for index,line in enumerate(lines):
        cv2.putText(image,line,(12,top+size+index*spacing),cv2.FONT_HERSHEY_SIMPLEX,scale,(0,255,255),1)
    image.setflags(write=False)
    return image


def draw_demo_guidance(frame, guidance):
    """원본을 보존하고 화면 폭에 맞춘 안내판을 아래쪽에 표시합니다."""
    image=frame.copy()
    height,width=image.shape[:2]
    panel=_guidance_panel(width,height,tuple(guidance))
    image[height-panel.shape[0]:,:]=panel
    return image


class ParkingPreview:
    def __init__(self, config=None, enable_http=False, source_label=None):
        require_display()
        self.config = config
        self.name = 'APCMS Parking Camera'
        self.enable_http = enable_http
        self.source_label = source_label
        self.reference = None
        self.compare_reference = False
        self.vehicle_progress = []
        self._font = None
        self._font_checked = False

    def show(self, frame, preparing=False, pending_http=0):
        # 1. 원본 영상은 변경하지 않고 좌표와 조작 안내만 덧그립니다.
        image = frame.copy()
        if preparing and self.reference is not None:
            if self.reference.shape != frame.shape:
                raise ValueError('기준 사진과 현재 카메라 화면의 해상도가 다릅니다.')
            if self.compare_reference:
                image = cv2.addWeighted(image, .5, self.reference, .5, 0)
        if self.config is not None:
            expected = (self.config['image_height'], self.config['image_width'])
            if frame.shape[:2] != expected:
                raise ValueError('웹캠과 주차면 좌표의 해상도가 다릅니다.')
            for space in self.config['spaces']:
                points = np.asarray(space['points'], dtype=np.int32)
                cv2.polylines(image, [points], True, (0, 255, 255), 2)
        text = 'SPACE: start / Q: cancel' if preparing else 'Q: stop'
        if preparing and self.reference is not None:
            text += ' / R: reference overlay ' + ('ON' if self.compare_reference else 'OFF')
        if self.enable_http:
            text = f'LIVE HTTP pending={pending_http} | ' + text
        cv2.putText(image, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 0), 2)
        if self.source_label:
            cv2.putText(image, self.source_label, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 2)
        if not preparing and self.vehicle_progress:
            image = self._draw_vehicles(image)
        if getattr(self,'guidance',None):
            image=draw_demo_guidance(image,self.guidance)
        cv2.imshow(self.name, image)
        key = cv2.waitKey(1) & 0xff
        if preparing and key == ord('r') and self.reference is not None:
            self.compare_reference = not self.compare_reference
        if cv2.getWindowProperty(self.name, cv2.WND_PROP_VISIBLE) < 1:
            return ord('q')
        return key

    def _draw_vehicles(self, image):
        # 한글 번호판은 OpenCV 기본 글꼴 대신 기존 Pillow로 표시합니다.
        if not self._font_checked:
            self._font_checked = True
            for path in (Path('C:/Windows/Fonts/malgun.ttf'),
                         Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')):
                if path.is_file():
                    try:
                        self._font = ImageFont.truetype(str(path), 18)
                        break
                    except OSError:
                        continue
        labels = []
        statuses = {'OUTSIDE_SPACE': '구획 경계 확인', 'WAIT_OCCUPANCY': '점유 확인 대기',
                    'PLATE_CONFLICT': '번호 충돌 확인', 'AMBIGUOUS_SPACE': '다중 차량 확인',
                    'LOCAL_MATCH': '로컬 연결', 'WAIT_DWELL': '정차 확인 중', 'WAIT_PLATE': '번호판 확인 필요',
                    'WAIT_IDENTITY': '입차 차량 번호 대조 중', 'IDENTITY_MISMATCH': '입차 차량 번호 불일치'}
        for row in self.vehicle_progress:
            x1, y1, x2, y2 = row['box']
            decision = row.get('parking_decision')
            decisions = {'MATCHED':'정상 주차', 'WRONG_SPACE':'다른 자리 주차',
                         'NO_VALID_RESERVATION':'유효 예약 없음', 'UNDETERMINED':'주차 판정 불가'}
            color = (0, 220, 0) if (decision == 'MATCHED' or (decision is None and row['status'] == 'LOCAL_MATCH')) else (0, 180, 255)
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            status = statuses.get(row['status'], row['status']) if self._font is not None else row['status']
            if decision in decisions:
                status = decisions[decision] if self._font is not None else decision
            label = f"ID {row['track_id']} | {row['space_id'] or '-'} | {status}"
            if row['plate_number']:
                label += ' | ' + row['plate_number']
            labels.append((label, (max(0, x1), max(55, y1 - 24)), color))
        if self._font is None:
            # 한글 글꼴 없는 환경에서도 카메라를 중단하지 않습니다. 원문은 결과 JSON에 남습니다.
            for label, point, color in labels:
                safe = label if label.isascii() else label.rsplit(' | ', 1)[0] + ' | OCR: see JSON'
                cv2.putText(image, safe, point, cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1)
            return image
        canvas = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(canvas)
        for label, point, color in labels:
            bounds = draw.textbbox((0, 0), label, font=self._font, stroke_width=1)
            point = (max(0, min(point[0], canvas.width - (bounds[2] - bounds[0]) - 4)),
                     max(0, min(point[1], canvas.height - (bounds[3] - bounds[1]) - 6)))
            draw.text(point, label, font=self._font, fill=color[::-1], stroke_width=1, stroke_fill=(0, 0, 0))
        return cv2.cvtColor(np.asarray(canvas), cv2.COLOR_RGB2BGR)

    def wait_until_ready(self, capture, check_ready=None):
        # 2. 준비 시간은 측정 시간에 포함하지 않습니다.
        print('카메라를 고정하고 구도를 맞추세요. 스페이스바: 시작 / Q: 취소')
        while True:
            ok, frame = capture.read()
            if not ok:
                raise OSError('준비 화면을 읽을 수 없습니다.')
            if check_ready is not None:
                check_ready(frame)
            key = self.show(frame, preparing=True)
            if key == ord('q'):
                return None
            if key == ord(' '):
                # 탐지 표시는 참고 정보입니다. 시험 영상 수집을 가로막지 않습니다.
                return frame

    def close(self):
        # 3. 다른 카메라 프로그램의 창은 닫지 않습니다.
        try:
            cv2.destroyWindow(self.name)
        except cv2.error:
            pass

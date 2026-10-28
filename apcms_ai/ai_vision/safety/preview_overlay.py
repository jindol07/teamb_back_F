"""공유 화재의 최신 분석 결과만 주차 화면에 전달합니다. 원본·판정은 바꾸지 않습니다."""
import json,math,time
from pathlib import Path
import cv2
from ai_vision.recognition.local_io import write_json_atomic


def publish_overlay(path,frame,detections,*,role,camera_id,run_id,captured_monotonic):
    write_json_atomic(Path(path),{'version':1,'role':role,'camera_id':camera_id,'run_id':run_id,
        'captured_monotonic':captured_monotonic,'shape':list(frame.shape),'detections':detections})


def draw_overlay(frame,*,path,role,camera_id,run_id,clock=None,max_age=2):
    now=(clock or time.monotonic)()
    try:
        with Path(path).open('rb') as stream:raw=stream.read(65537)
        if len(raw)>65536:return frame
        data=json.loads(raw)
        if not isinstance(data,dict):return frame
        if data.get('version')!=1 or (data.get('role'),data.get('camera_id'),data.get('run_id'))!=(role,camera_id,run_id):return frame
        age=now-data['captured_monotonic']
        if not math.isfinite(age) or not 0<=age<=max_age or data['shape']!=list(frame.shape):return frame
        detections=data['detections']
        if not isinstance(detections,list) or len(detections)>100:return frame
        h,w=frame.shape[:2]
        for item in detections:
            box=item['bbox'];score=item['confidence']
            if item['class_name'] not in ('FIRE','SMOKE') or len(box)!=4 or not all(type(v) is int for v in box):return frame
            if not (0<=box[0]<box[2]<=w and 0<=box[1]<box[3]<=h):return frame
            if type(score) not in (int,float) or not math.isfinite(score) or not 0<=score<=1:return frame
        result=frame.copy()
        for item in detections:
            x1,y1,x2,y2=item['bbox'];kind=item['class_name'];color=(0,0,255) if kind=='FIRE' else (0,255,255)
            cv2.rectangle(result,(x1,y1),(x2,y2),color,2)
            cv2.putText(result,f"{kind} {item['confidence']:.2f}",(x1,max(15,y1-6)),cv2.FONT_HERSHEY_SIMPLEX,.55,color,2)
        cv2.putText(result,f'FIRE/SMOKE sample age {age:.1f}s',(10,h-12),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,255),1)
        return result
    except (OSError,ValueError,KeyError,TypeError,OverflowError):return frame


def draw_configured_overlay(frame):
    import os
    path=os.environ.get('VISION_SAFETY_OVERLAY_PATH')
    if not path:return frame
    result=draw_overlay(frame,path=path,role=os.environ.get('VISION_SAFETY_OVERLAY_ROLE'),
        camera_id=os.environ.get('VISION_SAFETY_OVERLAY_CAMERA'),run_id=os.environ.get('VISION_SAFETY_OVERLAY_RUN'))
    if result is frame:
        result=frame.copy()
        cv2.putText(result,'FIRE/SMOKE: WAITING OR STALE',(10,frame.shape[0]-12),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,165,255),1)
    return result

"""사람이 검토한 연기 영역의 위치 일치와 명시적 오탐 영역을 진단합니다."""
import math


def valid_box(box):
    return (isinstance(box,list) and len(box)==4 and
            all(type(v) in (int,float) and math.isfinite(v) for v in box) and
            0 <= box[0] < box[2] and 0 <= box[1] < box[3])


def overlap(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    area_a=(a[2]-a[0])*(a[3]-a[1]);area_b=(b[2]-b[0])*(b[3]-b[1])
    return intersection/(area_a+area_b-intersection),intersection/area_a


def evaluate_regions(detections, positives, negatives, *, iou=.3):
    if not 0 < iou <= 1:raise ValueError('IoU 기준은 0 초과 1 이하입니다.')
    for box in positives+negatives+[d['bbox'] for d in detections]:
        if not valid_box(box):raise ValueError('평가 영역 좌표가 올바르지 않습니다.')
    smoke=[d for d in detections if d['class_name']=='SMOKE']
    matched=set();extra=[];negative_hits=[]
    # 1. 한 탐지로 여러 정답을 중복 충족시키지 않습니다.
    for detection in sorted(smoke,key=lambda d:d['confidence'],reverse=True):
        box=detection['bbox']
        options=[(overlap(box,target)[0],index) for index,target in enumerate(positives) if index not in matched]
        best=max(options,default=(0,-1))
        if best[0]>=iou:matched.add(best[1])
        else:extra.append(detection)
        if any(overlap(box,target)[1]>=.5 for target in negatives):negative_hits.append(detection)
    return {'matched_positive_regions':len(matched),'missing_positive_regions':len(positives)-len(matched),
            'unmatched_smoke_detections':extra,'negative_region_detections':negative_hits,
            'scope':'MANUALLY_REVIEWED_SMOKE_REGIONS_ONLY'}

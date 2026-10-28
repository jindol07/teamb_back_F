"""로컬 두 모델을 동일 원본·수동 검토 영역으로 실제 비교합니다."""
import argparse,json,os
from pathlib import Path
import cv2
from ai_vision.safety.region_review_manifest import load_regions
from ai_vision.safety.region_review import evaluate_regions
from ai_vision.safety.live_fire_smoke import detect_frame
from ai_vision.safety.model_review_manifest import file_sha256
from ai_vision.recognition.local_io import write_json_atomic


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    cases=load_regions(args.manifest)
    if not args.model.is_file():raise FileNotFoundError('로컬 모델 필요')
    args.output.mkdir(parents=True,exist_ok=False)
    os.environ['YOLO_AUTOINSTALL']='false'
    from ultralytics import YOLO
    model=YOLO(str(args.model))
    report={'status':'RUNNING','model_sha256':file_sha256(args.model),'iou_threshold':.3,
            'not_independent_accuracy':True,'cases':[]}
    for case in cases:
        frame=cv2.imread(case['path'])
        if frame is None:raise ValueError('원본 이미지 읽기 실패')
        detections,ms=detect_frame(model,frame,conf=.3)
        result=evaluate_regions(detections,case['positives'],case['negatives'])
        report['cases'].append(dict(id=case['id'],detections=detections,inference_ms=ms,**result))
        write_json_atomic(args.output/'review.json',report)
    report['status']='COMPLETED';write_json_atomic(args.output/'review.json',report)
    return report


if __name__=='__main__':main()

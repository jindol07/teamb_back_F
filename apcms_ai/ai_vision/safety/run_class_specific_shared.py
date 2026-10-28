"""공유 프레임 전용 이중 모델 DRY-RUN. 직접 카메라 개방·AWS 전송 옵션이 없습니다."""
import argparse
import os
from pathlib import Path
from ai_vision.safety.class_specific_model import ClassSpecificModel
from ai_vision.safety.live_fire_smoke import LiveConfig, run_live
from ai_vision.safety.model_review_manifest import file_sha256
from ai_vision.recognition.local_io import write_json_atomic


def parse_config(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shared-run-dir',type=Path,required=True)
    parser.add_argument('--shared-role',choices=('gate','parking'),required=True)
    parser.add_argument('--shared-camera-id',required=True)
    parser.add_argument('--fire-model',type=Path,required=True)
    parser.add_argument('--smoke-model',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-seconds',type=float,default=60)
    parser.add_argument('--show',action='store_true')
    parser.add_argument('--save-raw-review',action='store_true')
    args=parser.parse_args(argv)
    if not 0 < args.max_seconds <= 300:
        raise ValueError('시험 시간은 0초 초과 300초 이하여야 합니다.')
    if not args.shared_run_dir.is_dir():
        raise FileNotFoundError('실행 중인 공유 폴더가 필요합니다.')
    for path in (args.fire_model,args.smoke_model):
        if not path.is_file():raise FileNotFoundError('로컬 모델 파일이 필요합니다.')
    if args.output.exists():raise FileExistsError('기존 결과는 덮어쓰지 않습니다.')
    config=LiveConfig(shared_run_dir=args.shared_run_dir,shared_role=args.shared_role,
        shared_camera_id=args.shared_camera_id,conf=.30,max_seconds=args.max_seconds,
        show=args.show,save_candidates=True,save_evidence=True,output_dir=args.output,warmup=True)
    return args,config


def main(argv=None):
    args,config=parse_config(argv)
    os.environ['YOLO_AUTOINSTALL']='false'
    from ultralytics import YOLO
    from ai_vision.safety.raw_review_frames import RawReviewFrames
    writer=RawReviewFrames(args.output/'raw_review') if args.save_raw_review else None
    model=ClassSpecificModel(YOLO(str(args.fire_model)),YOLO(str(args.smoke_model)),raw_writer=writer)
    summary=run_live(config,model=model)
    write_json_atomic(args.output/'class_specific_models.json',{
        'mode':'SHARED_DRY_RUN','aws_send_enabled':False,
        'models':{kind:{'path':str(path),'sha256':file_sha256(path)} for kind,path in
                  (('FIRE',args.fire_model),('SMOKE',args.smoke_model))}})
    return summary


if __name__=='__main__':main()

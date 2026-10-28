"""고정된 로컬 자료·로컬 가중치로 모델을 비교하는 명시적 실행 도구."""
import argparse
import os
from pathlib import Path

from ai_vision.safety.model_review import review_model
from ai_vision.safety.model_review_manifest import load_review_manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--conf', type=float, default=.3)
    args = parser.parse_args(argv)
    cases = load_review_manifest(args.manifest)
    if not args.model.is_file():
        raise FileNotFoundError('로컬 모델 파일이 필요합니다. 자동 다운로드하지 않습니다.')
    # 1. 후보 모델의 누락 패키지를 운영 가상환경에 자동 설치하지 않습니다.
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    from ultralytics import YOLO
    review_model(YOLO(str(args.model)), cases, args.output, model_path=args.model,
                 imgsz=args.imgsz, conf=args.conf)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

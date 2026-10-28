"""FIRE 기존 모델·SMOKE 후보 모델을 로컬 자료에서 직접 추론합니다."""
import argparse
import os
from pathlib import Path
from ai_vision.safety.class_specific_model import ClassSpecificModel
from ai_vision.safety.model_review import review_model
from ai_vision.safety.model_review_manifest import load_review_manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--fire-model', type=Path, required=True)
    parser.add_argument('--smoke-model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    cases = load_review_manifest(args.manifest)
    for path in (args.fire_model, args.smoke_model):
        if not path.is_file():
            raise FileNotFoundError('로컬 모델 파일이 필요합니다: '+str(path))
    if args.output.exists():
        raise FileExistsError('결과 폴더를 덮어쓰지 않습니다.')
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    from ultralytics import YOLO
    model = ClassSpecificModel(YOLO(str(args.fire_model)), YOLO(str(args.smoke_model)))
    return review_model(model, cases, args.output, model_path=args.fire_model,
                        model_sources={'FIRE': args.fire_model, 'SMOKE': args.smoke_model})


if __name__ == '__main__':
    main()

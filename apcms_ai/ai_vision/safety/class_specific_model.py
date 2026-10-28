"""명시한 두 모델의 FIRE/SMOKE만 조합합니다. 운영 기본값은 변경하지 않습니다."""
import numpy as np


class ClassSpecificModel:
    names = {0: 'FIRE', 1: 'SMOKE'}

    def __init__(self, fire_model, smoke_model, *, raw_writer=None):
        self.models = (fire_model, smoke_model)
        self.raw_writer = raw_writer
        self.class_ids = []
        for model, kind in zip(self.models, ('FIRE', 'SMOKE')):
            matches = [key for key, value in model.names.items() if str(value).upper() == kind]
            if len(matches) != 1:
                raise ValueError('모델의 대상 클래스가 유일하지 않습니다: '+kind)
            self.class_ids.append(matches[0])

    def predict(self, *, source, **kwargs):
        from ultralytics.engine.results import Results
        if self.raw_writer is not None:
            self.raw_writer(source)
        rows = []
        for output_id, (model, class_id) in enumerate(zip(self.models, self.class_ids)):
            # 1. 모델마다 클래스 번호가 다르므로 이름으로 찾은 번호만 추론합니다.
            options = dict(kwargs, classes=[class_id])
            result = model.predict(source=source, **options)
            if len(result) != 1 or result[0].boxes is None:
                raise RuntimeError('클래스별 모델 추론 결과가 올바르지 않습니다.')
            for box in result[0].boxes:
                if int(box.cls[0].item()) != class_id:
                    continue
                rows.append(box.xyxy[0].tolist()+[float(box.conf[0].item()), output_id])
        boxes = np.asarray(rows, dtype=np.float32).reshape(-1, 6)
        return [Results(orig_img=source, path='', names=self.names, boxes=boxes)]

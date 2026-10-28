"""정상·양성 진단 자료를 같은 추론·사건 조건으로 비교합니다."""
import json
from pathlib import Path

import cv2

from ai_vision.recognition.local_io import write_json_atomic
from ai_vision.safety.live_fire_smoke import LiveConfig, detect_frame, draw_detections, run_live
from ai_vision.safety.model_review_manifest import file_sha256, verify_case


def compare_expected(expected, observed):
    # 1. 정답 박스가 없으므로 IoU 정확도나 일반적인 재현율을 계산하지 않습니다.
    return {'missing_classes': sorted(set(expected) - set(observed)),
            'unexpected_classes': sorted(set(observed) - set(expected))}


def review_model(model, cases, output, *, model_path, imgsz=640, conf=.3, model_sources=None):
    if not cases:
        raise ValueError('평가 자료가 비어 있습니다.')
    if {str(value).upper() for value in model.names.values()} != {'FIRE', 'SMOKE'}:
        raise ValueError('비교 모델은 FIRE·SMOKE 두 클래스여야 합니다.')
    # 2. 기존 설정 검증을 재사용하고 모델·자료 해시를 실행 결과에 함께 남깁니다.
    config = LiveConfig(image_size=imgsz, conf=conf)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {'purpose': 'diagnostic_review', 'status': 'RUNNING', 'expected_case_count': len(cases),
              'model_sha256': file_sha256(model_path),
              'imgsz': config.image_size, 'conf': config.conf, 'interval': .5,
              'smoke_confirm_conf': None, 'cases': []}
    if model_sources is not None:
        report['inference_mode'] = 'ACTUAL_CLASS_SPECIFIC_INFERENCE'
        report['model_sources'] = {kind: {'path': str(path), 'sha256': file_sha256(path)}
                                   for kind, path in model_sources.items()}
    for case in cases:
        verify_case(case)
        target = output / case['case_id']
        result = {key: case[key] for key in ('case_id', 'source_group', 'media_type', 'sha256', 'expected')}
        if case['media_type'] == 'image':
            frame = cv2.imread(str(case['path']))
            if frame is None:
                raise ValueError('평가 이미지를 읽지 못했습니다: ' + case['case_id'])
            detections, ms = detect_frame(model, frame, conf=conf, image_size=imgsz)
            result.update(detections=detections, inference_ms=ms,
                          observed_classes=sorted({d['class_name'] for d in detections}))
            target.mkdir()
            if not cv2.imwrite(str(target / 'annotated.jpg'), draw_detections(frame, detections)):
                raise OSError('평가 이미지 저장 실패')
        else:
            # 3. 실제 운영 분석·사건 관리 코드를 호출합니다. 카메라·HTTP 전송은 없습니다.
            summary = run_live(LiveConfig(video_path=str(case['path']), output_dir=target,
                image_size=imgsz, conf=conf, max_seconds=0, interval=.5, save_candidates=True,
                warmup=False), model=model)
            if summary['status'] != 'VIDEO_END':
                raise RuntimeError('평가 영상이 정상 완료되지 않았습니다: ' + summary['status'])
            events = json.loads((target / 'events.json').read_text(encoding='utf-8'))['events']
            result.update(summary=summary, observed_classes=sorted({e['type'] for e in events
                                                                   if e['status'] == 'SUSPECTED'}))
        result.update(compare_expected(case['expected'], result['observed_classes']))
        report['cases'].append(result)
        write_json_atomic(output / 'review.json', report)
        print('REVIEW_CASE', case['case_id'], result['observed_classes'], flush=True)
    report['status'] = 'COMPLETED'
    write_json_atomic(output / 'review.json', report)
    return report

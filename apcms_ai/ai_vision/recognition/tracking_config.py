# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/tracking_config.py

"""추적 도구와 통합 실행 도구가 함께 사용하는 영상 설정 검사."""

import argparse
import json
import math
from pathlib import Path


def validate_config(config):
    # 1. 철자가 틀린 설정을 조용히 무시하지 않고 오류로 알려 줍니다.
    keys = {"tracker", "line_y", "line_x", "roi"}
    if not isinstance(config, dict) or set(config) != keys:
        raise ValueError("설정에는 tracker, line_y, line_x, roi 네 항목이 필요합니다.")
    if not isinstance(config["tracker"], str) or config["tracker"] not in {"bytetrack", "botsort"}:
        raise ValueError("tracker는 bytetrack 또는 botsort여야 합니다.")

    def ratio(value):
        # True/False와 NaN/무한대는 좌표로 사용하지 않음
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and 0 <= value <= 1)

    line_x, roi = config["line_x"], config["roi"]
    if not ratio(config["line_y"]) or not 0 < config["line_y"] < 1:
        raise ValueError("line_y는 0 초과 1 미만의 높이 비율이어야 합니다.")
    if (not isinstance(line_x, (list, tuple)) or len(line_x) != 2 or
            not all(ratio(value) for value in line_x) or line_x[0] >= line_x[1]):
        raise ValueError("line_x는 왼쪽부터 증가하는 0~1 좌표 두 개여야 합니다.")
    if (not isinstance(roi, (list, tuple)) or len(roi) != 8 or
            not all(ratio(value) for value in roi)):
        raise ValueError("roi는 꼭짓점 네 개의 x/y 비율 총 8개여야 합니다.")
    # 2. 꼭짓점이 겹치거나 넓이가 없는 영역은 분석에 사용할 수 없습니다.
    points = list(zip(roi[::2], roi[1::2]))
    # 비인접 변이 만나면 순서가 꼬인 사각형이므로 ROI로 사용하지 않음
    def orientation(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def intersects(a, b, c, d):
        first, second = orientation(a, b, c), orientation(a, b, d)
        third, fourth = orientation(c, d, a), orientation(c, d, b)
        if first * second < 0 and third * fourth < 0:
            return True
        for start, end, point, cross in [(a, b, c, first), (a, b, d, second),
                                          (c, d, a, third), (c, d, b, fourth)]:
            if abs(cross) <= 1e-12 and all(min(start[i], end[i]) <= point[i] <= max(start[i], end[i]) for i in (0, 1)):
                return True
        return False

    if intersects(points[0], points[1], points[2], points[3]) or intersects(points[1], points[2], points[3], points[0]):
        raise ValueError("ROI 변이 교차합니다. 꼭짓점을 테두리 순서로 지정해 주세요.")
    area = abs(sum(points[i][0] * points[(i + 1) % 4][1] -
                   points[(i + 1) % 4][0] * points[i][1] for i in range(4))) / 2
    if len(set(points)) != 4 or area <= 1e-8:
        raise ValueError("ROI 꼭짓점이 중복되거나 영역의 넓이가 없습니다.")
    # 선분과 ROI의 내부가 겹치지 않으면 차량 중심점이 선을 지날 수 없음
    cuts = []
    y = config["line_y"]
    for a, b in zip(points, points[1:] + points[:1]):
        if (a[1] <= y < b[1]) or (b[1] <= y < a[1]):
            cuts.append(a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]))
    cuts.sort()
    if not any(max(cuts[i], line_x[0]) < min(cuts[i + 1], line_x[1]) for i in range(0, len(cuts) - 1, 2)):
        raise ValueError("기준선 선분이 ROI 내부와 겹치지 않습니다.")
    return dict(config)


def parse_with_config(parser, argv=None):
    # 3. 설정 파일로 기본값을 바꾼 뒤 명령 옵션을 읽습니다.
    # 우선순위: 직접 지정한 명령 옵션 > 설정 파일 > 기존 프로그램 기본값
    probe = argparse.ArgumentParser(add_help=False)
    probe.add_argument("--config", type=Path)
    known, _ = probe.parse_known_args(argv)
    parser.add_argument("--config", type=Path, help="ROI·기준선·추적기를 저장한 JSON 설정")
    if known.config:
        try:
            config = json.loads(known.config.read_text(encoding="utf-8"))
            parser.set_defaults(**validate_config(config))
        except (OSError, ValueError, TypeError) as error:
            parser.error(f"설정 파일 오류: {error}")
    args = parser.parse_args(argv)
    # 4. 명령으로 덮어쓴 좌표도 같은 규칙으로 검사합니다.
    try:
        validate_config({key: getattr(args, key) for key in ("tracker", "line_y", "line_x", "roi")})
    except (ValueError, TypeError) as error:
        parser.error(str(error))
    return args

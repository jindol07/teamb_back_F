# D:/finalProjectB/back/apcms_ai/ai_vision/parking/parking_validation.py

"""주차면 설정과 저장 결과를 OpenCV 처리·API 응답 전에 검사합니다."""

import math


def _identifier(value):
    return isinstance(value, str) and 1 <= len(value) <= 96 and not any(ord(c) < 32 for c in value)


def validate_spaces(data):
    if not isinstance(data, dict):
        raise ValueError("주차면 설정 객체가 필요합니다.")
    width, height, spaces = data.get("image_width"), data.get("image_height"), data.get("spaces")
    if (type(width) is not int or type(height) is not int or not 1 <= width <= 32768 or
            not 1 <= height <= 32768 or not isinstance(spaces, list) or not 1 <= len(spaces) <= 10000):
        raise ValueError("주차면 설정의 해상도·목록을 확인해 주세요.")
    seen = set()
    # 1. 중복 ID·퇴화 좌표·화면 밖 좌표를 배열 생성 전에 거부합니다.
    for space in spaces:
        if not isinstance(space, dict) or not _identifier(space.get("id")) or space["id"] in seen:
            raise ValueError("주차면 ID가 없거나 중복됐습니다.")
        seen.add(space["id"])
        points = space.get("points")
        if (not isinstance(points, list) or len(points) != 4 or
                any(not isinstance(p, list) or len(p) != 2 or
                    type(p[0]) is not int or type(p[1]) is not int or
                    not 0 <= p[0] <= width or not 0 <= p[1] <= height for p in points)):
            raise ValueError("주차면 꼭짓점은 화면 안의 정수 좌표 네 개여야 합니다.")
        area = sum(points[i][0] * points[(i + 1) % 4][1] - points[(i + 1) % 4][0] * points[i][1]
                   for i in range(4))
        if len({tuple(p) for p in points}) != 4 or area == 0:
            raise ValueError("주차면 다각형의 넓이가 없거나 좌표가 중복됐습니다.")
    return data


def validate_occupancy(data):
    if not isinstance(data, dict):
        raise ValueError("주차 점유 결과 객체가 필요합니다.")
    counts = [data.get(key) for key in ("total_spaces", "occupied_count", "empty_count")]
    spaces = data.get("spaces")
    if (any(type(n) is not int or not 0 <= n <= 10000 for n in counts) or
            not isinstance(spaces, list) or len(spaces) != counts[0] or counts[1] + counts[2] != counts[0]):
        raise ValueError("주차 점유 결과의 건수가 일치하지 않습니다.")
    seen, occupied = set(), 0
    for space in spaces:
        if not isinstance(space, dict) or not _identifier(space.get("space_id")) or space["space_id"] in seen:
            raise ValueError("점유 결과의 주차면 ID를 확인해 주세요.")
        seen.add(space["space_id"])
        ratio, status = space.get("change_ratio"), space.get("status")
        if (status not in ("EMPTY", "OCCUPIED") or type(ratio) not in (int, float) or
                not math.isfinite(ratio) or not 0 <= ratio <= 1):
            raise ValueError("점유 상태·변화율이 유효하지 않습니다.")
        occupied += status == "OCCUPIED"
    if occupied != counts[1]:
        raise ValueError("점유 상태별 합계가 일치하지 않습니다.")
    return data

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/plate_consensus.py

"""서로 다른 프레임의 번호판 인식 결과를 모아 확정 여부를 판단합니다."""

import re
import unicodedata
import math
from collections import Counter


# 역할: OCR 표본을 시간순으로 검사해 번호판 확정 상태와 표 수를 반환합니다.
def summarize_plate_samples(samples, minimum_votes=2, minimum_spacing=.25):
    # 1. 같은 프레임 반복 인식은 표 수를 늘리지 않습니다.
    # 1-1. 인접한 거의 같은 화면만으로 확정하지 않도록 영상 시각 간격도 확인
    if (type(minimum_votes) is not int or minimum_votes < 2 or
            isinstance(minimum_spacing, bool) or not isinstance(minimum_spacing, (int, float)) or
            not math.isfinite(minimum_spacing) or minimum_spacing < .25):
        raise ValueError("확정에는 최소 2회와 양수인 프레임 간격이 필요합니다.")
    for sample in samples:
        if (type(sample.get("frame_index")) is not int or sample["frame_index"] < 0 or
                isinstance(sample.get("video_seconds"), bool) or
                not isinstance(sample.get("video_seconds"), (int, float)) or
                not math.isfinite(sample["video_seconds"]) or sample["video_seconds"] < 0):
            raise ValueError("OCR 표본의 프레임 번호와 영상 시각이 유효하지 않습니다.")
    seen_frames, accepted_times, valid_numbers, observed_numbers = set(), [], [], set()
    frame_values = {}
    # 1-2. 정렬의 key 함수는 표본의 영상 시각을 기준으로 삼습니다.
    for sample in sorted(samples, key=lambda item: item["video_seconds"]):
        frame_index, timestamp = sample["frame_index"], sample["video_seconds"]
        text = sample.get("plate_number", "")
        if not isinstance(text, str):
            continue
        # 1-4. NFC는 한글 조합을 정규화하고 정규식의 공백 패턴은 띄어쓰기를 제거합니다.
        text = re.sub(r"\s+", "", unicodedata.normalize("NFC", text))
        # 2. 기존 인식기가 정상 형식으로 분류했고 문자열 자체도 형식에 맞아야 후보로 사용
        if sample.get("plate_type") != "KOREAN_VALID" or not re.fullmatch(r"[0-9]{2,3}[가-힣][0-9]{4}", text):
            continue
        # 2-1. 서로 다른 유효 번호의 존재를 기억해 간격 제한으로 투표에서 빠져도 충돌을 표시합니다.
        observed_numbers.add(text)
        # 동일 프레임의 상충 결과도 충돌로 남기되 투표는 한 번만 허용
        previous = frame_values.setdefault(frame_index, (timestamp, text))
        if previous[0] != timestamp:
            raise ValueError("같은 프레임에 서로 다른 영상 시각이 기록됐습니다.")
        if frame_index in seen_frames:
            continue
        seen_frames.add(frame_index)
        # 2-2. any()는 이미 채택한 시각과 너무 가까운 표본이 하나라도 있는지 검사합니다.
        if any(abs(timestamp - old_time) < minimum_spacing - 1e-9 for old_time in accepted_times):
            continue
        # 2-3. 표로 채택한 영상 시각만 기록해 이후 표본과 최소 시간 간격을 비교합니다.
        accepted_times.append(timestamp)
        valid_numbers.append(text)

    # 3. 유효한 번호가 서로 다르면 다수결로 덮어쓰지 않고 검토 대상으로 남깁니다.
    # 3-1. Counter는 채택된 번호 문자열별 출현 횟수를 계산합니다.
    votes = Counter(valid_numbers)
    if len(observed_numbers) > 1:
        status = "CONFLICT"
    elif not votes:
        status = "NO_VALID_KOREAN_PLATE"
    # 3-2. 한 번호가 최소 투표 수에 미치지 못하면 번호 문자열을 반환하더라도 확정하지 않습니다.
    elif max(votes.values()) < minimum_votes:
        status = "INSUFFICIENT_EVIDENCE"
    else:
        status = "CONFIRMED"
    return {"status": status, "plate_number": next(iter(votes)) if status == "CONFIRMED" else "",
            "plate_type": "KOREAN_VALID" if status == "CONFIRMED" else None,
            "votes": dict(votes), "minimum_votes": minimum_votes,
            "observed_valid_numbers": sorted(observed_numbers),
            "minimum_spacing_seconds": minimum_spacing}


def validate_plate_summary(summary, sample_count):
    # 4. 원본 프레임 없이도 저장된 합의 요약 안의 모순은 검사할 수 있습니다.
    keys = {"status", "plate_number", "plate_type", "votes", "minimum_votes",
            "observed_valid_numbers", "minimum_spacing_seconds"}
    if (not isinstance(summary, dict) or set(summary) != keys or type(sample_count) is not int or
            not 0 <= sample_count <= 100000):
        raise ValueError("번호판 합의 요약·표본 수가 올바르지 않습니다.")
    minimum, spacing = summary["minimum_votes"], summary["minimum_spacing_seconds"]
    if (type(minimum) is not int or not 2 <= minimum <= 100000 or isinstance(spacing, bool) or
            not isinstance(spacing, (int, float)) or not math.isfinite(spacing) or spacing < .25):
        raise ValueError("번호판 확정 조건이 올바르지 않습니다.")
    votes, observed = summary["votes"], summary["observed_valid_numbers"]
    def valid_plate(value):
        return isinstance(value, str) and re.fullmatch(r"[0-9]{2,3}[가-힣][0-9]{4}", value) is not None
    if (not isinstance(votes, dict) or not isinstance(observed, list) or
            any(not valid_plate(value) for value in observed) or
            any(not valid_plate(plate) or type(count) is not int or not 1 <= count <= sample_count
                for plate, count in votes.items())):
        raise ValueError("번호판별 투표·관찰 목록이 올바르지 않습니다.")
    if (observed != sorted(set(observed)) or not set(votes) <= set(observed) or
            len(observed) > sample_count or sum(votes.values()) > sample_count or bool(votes) != bool(observed)):
        raise ValueError("투표 수가 표본 수·관찰 번호판과 일치하지 않습니다.")
    # 4-1. 충돌은 다수결로 확정하지 않는 기존 규칙과 같은 순서로 확인합니다.
    if len(observed) > 1:
        expected = "CONFLICT"
    elif not votes:
        expected = "NO_VALID_KOREAN_PLATE"
    elif max(votes.values()) < minimum:
        expected = "INSUFFICIENT_EVIDENCE"
    else:
        expected = "CONFIRMED"
    plate = next(iter(votes)) if expected == "CONFIRMED" else ""
    plate_type = "KOREAN_VALID" if expected == "CONFIRMED" else None
    if summary["status"] != expected or summary["plate_number"] != plate or summary["plate_type"] != plate_type:
        raise ValueError("저장된 번호판 판정이 투표·확정 조건과 일치하지 않습니다.")
    # 4-2. 실제 표본 간격·프레임 중복이나 문자 정답은 원본 자료가 있어야 검증할 수 있습니다.
    return {"plate_status": expected, "plate_number": plate, "accepted_votes": sum(votes.values()),
            "required_votes": minimum, "minimum_spacing_seconds": spacing}

# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/plate_review.py

"""번호판 형식의 검토 사유를 설명합니다. 누락 문자를 추측해 채우지 않습니다."""

import re


KOREAN_PLATE_PATTERN = re.compile(r"[0-9]{2,3}[가-힣][0-9]{4}")
REVIEW_REASON_CODES = frozenset({"PLATE_NOT_DETECTED", "PLATE_CROP_FAILED", "NO_OCR_TEXT",
                                "NON_KOREAN_PLATE_FORMAT", "KOREAN_CHARACTER_NOT_FOUND",
                                "UNRECOGNIZED_PLATE_FORMAT"})


def sample_review_reasons(samples):
    # 저장된 사유 목록을 그대로 믿지 않고 OCR 원문·형식에서 다시 계산합니다.
    return sorted({reason for sample in samples
                   for reason in plate_review_reasons(sample.get("plate_number", ""),
                                                       sample.get("plate_type", "NOT_DETECTED"))})


def plate_review_reasons(text, plate_type):
    # 1. 형식 통과는 실제 정답·주행 통과 확정과 다릅니다.
    if plate_type == "KOREAN_VALID" and isinstance(text, str) and KOREAN_PLATE_PATTERN.fullmatch(text):
        return []
    if plate_type == "NOT_DETECTED":
        return ["PLATE_NOT_DETECTED"]
    if plate_type == "CROP_FAILED":
        return ["PLATE_CROP_FAILED"]
    if plate_type == "OCR_FAILED" or not text:
        return ["NO_OCR_TEXT"]
    if plate_type == "FOREIGN_OR_OTHER":
        return ["NON_KOREAN_PLATE_FORMAT"]
    # 2. 숫자 사이 한글이 없는 경우에도 어떤 한글인지 임의로 복원하지 않습니다.
    if isinstance(text, str) and re.fullmatch(r"[0-9]{2,3}[-._]?[0-9]{4}", text):
        return ["KOREAN_CHARACTER_NOT_FOUND"]
    return ["UNRECOGNIZED_PLATE_FORMAT"]

"""정책 PDF ROUTE-001..006 참고. 개인 이력 우선, 혼합 질문 지원."""

import re

PERSONAL = {
    "RESERVATION": [
        r"(내|나의|제가|우리|내일).{0,15}(예약|주차면|배정|자리)",
        r"(예약|주차면).{0,9}(내역|현황|위치|어디|조회|확인|상태)",
        r"예약했",
        r"예약된",
    ],
    "USAGE": [
        r"(내|나의|우리|지난주|어제|오늘).{0,15}(입차|출차|입출차|주차.{0,4}이용|이용.{0,4}내역|주차.{0,4}기록)",
        r"(입출차|주차.{0,4}이용).{0,10}(기록|내역|조회|몇)",
        r"언제.{0,8}(들어|나갔|주차)",
    ],
    "VEHICLE": [
        r"(내|나의|우리|등록된).{0,12}(차량|차량번호|차번호|번호판|자동차)",
        r"(차량번호|번호판).{0,10}(뭐|알려|조회)",
    ],
    "MILEAGE": [
        r"(내|나의|보유|현재).{0,12}(마일리지|포인트)",
        r"(마일리지|포인트).{0,12}(잔액|얼마|내역|조회)",
    ],
    "FEE": [
        r"(내|나의|이번달|이번 달|우리).{0,12}(관리비|청구|미납)",
        r"관리비.{0,12}(내역|얼마|조회|청구금액)",
    ],
}
# 실시간 주차 현황 질문 분류
PARKING_STATUS = [
    r"(빈자리|빈공간|빈 공간|남은 자리|주차 가능 공간)",
    r"(주차장|주차 공간|주차면).{0,15}(현황|혼잡|몇 자리|몇 개|남았|비었)",
    r"(지하\s*\d+층|[a-z]구역).{0,15}(빈자리|주차 가능|자리)",
]
POLICY = [
    r"정책",
    r"규정",
    r"방법",
    r"절차",
    r"어떻게",
    r"가능",
    r"기준",
    r"신청",
    r"취소",
    r"수수료",
    r"등록해야",
    r"해야 하나",
    r"보상",
    r"패널티",
    r"차감",
    r"위반",
    r"얼마인가요",
]
DOMAIN = [
    "주차",
    "차량",
    "예약",
    "마일리지",
    "관리비",
    "입차",
    "출차",
    "신고",
    "회원가입",
    "오피스",
    "office",
    "연기",
    "위험",
    "알림",
    "주차면",
]
# 띄어쓰기를 제거한 문장에서 조회 의도를 인식합니다. 기존 유형 이름은 유지합니다.
EXTRA_PERSONAL = {
    "USAGE": [
        r"주차(?:이력|내역|기록)",
        r"(?:입차|출차|입출차).*(?:시간|시각|언제|내역|이력)",
        r"(?:어제|오늘|최근|이번달|지난달).*(?:이용내역|이용기록)",
    ],
    "RESERVATION": [
        r"예약.*(?:내역|상태|위치|어디|시간|시작|종료|주차면)",
        r"취소한예약",
        r"예약된",
        r"예약한자리",
    ],
    "VEHICLE": [r"등록(?:된)?차량", r"차량.*(?:승인|반려|등록상태)", r"내차량번호"],
}
POLICY_INTENT = (
    r"방법|절차|규정|정책|어떻게|기준|하려면|취소가능|예약가능|수수료|보상|패널티|위반"
)
ACTION_INTENT = (
    r"(?:취소|등록|추가|수정|삭제|변경|예약)(?:해줘|해주세요|해줄래|해줄수있어)"
)


def classify(question: str):
    q = re.sub(r"\s+", "", question).lower()
    # 변경을 실행하는 기능은 아직 없으므로 조회/정책 답변과 분리합니다.
    if re.search(ACTION_INTENT, q):
        return {"categories": [], "policy": False, "type": "ACTION"}
    if re.search(r"내(?:차|차량)(?:는|가)?(?:어디|위치)", q) and not re.search(
        r"예약|입차|출차", q
    ):
        return {"categories": [], "policy": False, "type": "CLARIFY"}

    # '내 예약 위치와 취소 방법'처럼 서로 다른 요청은 각각 판단합니다.
    clauses = re.split(
        r"그리고|또한|및|[,，\n]|(?:와|과)(?=내|예약|차량|등록|취소|빈|주차)", q
    )
    found = set()
    policy = False
    for clause in clauses:
        if not clause:
            continue
        # '내 예약 취소 방법'은 개인 조회가 아닌 정책 문의
        if re.search(POLICY_INTENT, clause):
            policy = True
            continue
        clause_categories = set()
        for key, patterns in PERSONAL.items():
            if any(
                re.search(p, clause) for p in patterns + EXTRA_PERSONAL.get(key, [])
            ):
                clause_categories.add(key)
        # 실시간 현황과 예약을 함께 물으면 두 유형 모두 유지합니다.
        if any(re.search(p, clause) for p in PARKING_STATUS) or re.search(
            r"빈자리|남은주차면|주차가능(?:한)?(?:자리|곳)|주차장.*혼잡", clause
        ):
            clause_categories.add("PARKING_STATUS")
            # '남은 자리' 자체를 개인 예약이라고 추정하지 않습니다.
            if not re.search(r"예약|배정", clause):
                clause_categories.discard("RESERVATION")
        found.update(clause_categories)

    cats = [key for key in [*PERSONAL, "PARKING_STATUS"] if key in found]
    # 기존 서비스 도메인의 일반 질문은 정책 검색을 유지합니다.
    policy = policy or (not cats and any(w in q for w in DOMAIN))
    kind = (
        "MIXED"
        if policy and cats
        else (
            "MULTI_DB"
            if len(cats) > 1
            else cats[0] if cats else "POLICY" if policy else "UNKNOWN"
        )
    )
    return {"categories": cats, "policy": policy, "type": kind}

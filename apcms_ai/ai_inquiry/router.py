"""정책 PDF ROUTE-001..006 참고. 개인 이력 우선, 혼합 질문 지원."""
import re
PERSONAL = {
 'RESERVATION': [r'(내|나의|제가|우리|내일).{0,15}(예약|주차면|배정|자리)',r'(예약|주차면).{0,9}(내역|현황|위치|어디|조회|확인|상태)',r'예약했',r'예약된'],
 'USAGE': [r'(내|나의|우리|지난주|어제|오늘).{0,15}(입차|출차|입출차|주차.{0,4}이용|이용.{0,4}내역|주차.{0,4}기록)',r'(입출차|주차.{0,4}이용).{0,10}(기록|내역|조회|몇)',r'언제.{0,8}(들어|나갔|주차)'],
 'VEHICLE': [r'(내|나의|우리|등록된).{0,12}(차량|차량번호|차번호|번호판|자동차)',r'(차량번호|번호판).{0,10}(뭐|알려|조회)'],
 'MILEAGE':[r'(내|나의|보유|현재).{0,12}(마일리지|포인트)',r'(마일리지|포인트).{0,12}(잔액|얼마|내역|조회)'],
 'FEE':[r'(내|나의|이번달|이번 달|우리).{0,12}(관리비|청구|미납)',r'관리비.{0,12}(내역|얼마|조회|청구금액)']
}
# 실시간 주차 현황 질문 분류
PARKING_STATUS = [
    r'(빈자리|빈공간|빈 공간|남은 자리|주차 가능 공간)',
    r'(주차장|주차 공간|주차면).{0,15}(현황|혼잡|몇 자리|몇 개|남았|비었)',
    r'(지하\s*\d+층|[a-z]구역).{0,15}(빈자리|주차 가능|자리)',
]
POLICY = [r'정책',r'규정',r'방법',r'절차',r'어떻게',r'가능',r'기준',r'신청',r'취소',r'수수료',r'등록해야',r'해야 하나',r'보상',r'패널티',r'차감',r'위반',r'얼마인가요']
DOMAIN = ['주차','차량','예약','마일리지','관리비','입차','출차','신고','회원가입','오피스','office','연기','위험','알림','주차면']
def classify(question: str):
 q=question.strip().lower()
 cats=[key for key, patterns in PERSONAL.items() if any(re.search(p,q) for p in patterns)]
 # PARKING_STATUS
 if any(re.search(p, q) for p in PARKING_STATUS):
    cats = [cat for cat in cats if cat != 'RESERVATION']
    cats.append('PARKING_STATUS')
 # '내 예약 취소 방법'은 개인 조회가 아닌 정책 문의
 if cats and re.search(r'(방법|절차|규정|정책|어떻게|취소 가능|수수료)',q) and not re.search(r'(내역|현황|조회|확인|위치|어디|기록|잔액)',q):
  cats=[]
 policy=any(re.search(p,q) for p in POLICY) or (not cats and any(w in q for w in DOMAIN))
 return {'categories':cats, 'policy':policy, 'type': 'MIXED' if policy and cats else ('MULTI_DB' if len(cats)>1 else cats[0] if cats else 'POLICY' if policy else 'UNKNOWN')}

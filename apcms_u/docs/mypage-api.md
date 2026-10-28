# 마이페이지 API

인증된 ACTIVE OFFICE 사용자 전용이다. 사무실 ID는 서버 인증 principal에서 얻으며 요청으로 받지 않는다.
기존 내 차량 관리 및 마일리지 API는 변경하지 않는다. 테이블·공통코드·스키마 추가 없음.

## 조회

- `GET /api/mypage/charges/current`: 한국 시간 기준 당월 본인 청구와 상세, 마일리지 잔액. 청구가 없으면 `charges: []`이며 생성하지 않는다.
- `GET /api/mypage/parking-usages?page=0&size=10`: 본인 OFFICE의 PARKING_USAGE. 입차시간·ID 내림차순.
- `GET /api/mypage/accepted-reports?page=0&size=10`: 본인 차량을 대상으로 하는 ACCEPTED 신고. 승인시간·ID 내림차순. 소프트 삭제 차량의 기록도 보존한다. 신고자 정보와 신고 원문은 반환하지 않는다.
- `GET /api/mypage/penalties?page=0&size=10`: VEHICLE_PENALTY → VEHICLE → OFFICE 소유권 조인으로 실제 부과 내역을 조회한다. 위반 유형명·위반금액·부과일·사유를 반환하며, 사용자 패널티 화면은 이 API를 사용한다. 기존 accepted-reports API는 유지한다.
- 페이지 응답은 `Page<응답DTO>`. page는 0 이상, size는 1~50. 정렬은 서버에서 고정한다.
- 유형·상태 표시명은 COMMON_CODE_DETAIL의 GROUP_CODE+CODE LEFT JOIN으로 CODE_NAME을 조회한다. 비활성 과거 코드도 이름을 표시하며, 누락 시 안내 문자열을 사용한다.

관리비 응답 예시 (실제 데이터가 아닌 계약 예시):

```json
{
  "year_month": "202610",
  "mileage_balance": 30000,
  "charges": [{
    "id": 33,
    "year_month": "202610",
    "total_amount": 85000,
    "mileage_discount_amount": 0,
    "final_amount": 85000,
    "status_code": "BILLED",
    "status_name": "청구완료",
    "items": [{"id": 1, "type_name": "예약요금", "amount": 85000, "description": null}]
  }]
}
```

입출차 응답 content의 필드: id, vehicle_number, entry_at, exit_at, parking_type_name.
승인 신고 응답 content의 필드: id, vehicle_number, type_name, status_name, review_reason, created_at, reviewed_at.
실제 패널티 응답 content의 필드: id, vehicle_number, type_name, penalty_amount, reason, imposed_at.
LocalDateTime은 기존 Jackson 설정의 ISO 일시 문자열이다. 프론트는 날짜를 재해석하지 않고 표시한다.

## 관리자 코드 변경 없는 패널티 관리비 반영 (2026-10-28 추가)

`POST /api/mypage/charges/current/penalties` → 성공 시 최신 당월 관리비 조회 응답.

- 화면 진입·관리비 재조회 시 호출한다. GET 조회 자체는 데이터를 갱신하지 않는다.
- 인증된 사무실의 OFFICE → 당월 청구 → 당월 미반영 패널티 순서로 잠근다.
- 한국 시간 기준 당월에 부과된 양수 패널티만 반영한다. 이전 달의 패널티는 당월에 임의 이월하지 않는다.
- OFFICE_CHARGE_ITEM의 CHARGE_TYPE_CODE=PENALTY, REFERENCE_ID=VEHICLE_PENALTY_ID 존재 여부로 중복 반영을 방지한다. 어느 청구에든 이미 반영된 패널티는 다시 청구하지 않는다.
- 기존 BILLED 청구를 우선 사용하며, BILLED가 없고 READY가 있으면 합산하되 READY 상태는 유지한다.
- 미반영 패널티가 있고 사용 가능한 당월 청구가 없으면 기존 seq_office_charge·seq_office_charge_item을 allocationSize=1로 사용해 BILLED 청구와 상세를 생성한다. 미반영 패널티가 없으면 빈 청구를 만들지 않는다.
- 이미 PAID인 청구는 수정하지 않고 새 패널티용 추가 청구를 만든다. 실제 DB에 사무실+연월 유니크 제약이 있다면 추가 청구 정책과의 호환성 확인이 필요하다.
- 예: TOTAL_AMOUNT=85,000원 + 패널티 10,000원 → TOTAL_AMOUNT=95,000원. 기존 누적 할인 20,000원이 있으면 FINAL_AMOUNT=75,000원.
- 청구 상세·헤더 갱신과 새 청구 생성은 한 트랜잭션이다. 저장 실패 시 모두 롤백된다. 시퀀스 번호에 공백이 생길 수 있는 일반적인 Oracle 동작은 허용한다.
- 마일리지 사용 직전에도 같은 트랜잭션에서 패널티를 반영한 후 청구 금액과 잔액을 검증한다. 사용자가 요청한 마일리지 금액을 자동으로 늘리지는 않는다.
- 관리자 신고 승인·패널티 등록/수정/삭제 코드는 변경하지 않는다. 관리자가 이후 수정·삭제한 패널티와 이미 저장된 청구 상세를 소급 정산하지 않으며 청구 시점 금액은 보존한다.
- 이 서비스에서 임의로 패널티 상태 코드를 해석하거나, 직접 연결되지 않은 REPORT에 금액을 추정해서 붙이지 않는다. 부과 자체는 VEHICLE_PENALTY를 기준으로 한다.
- 기존 시퀀스를 매핑할 뿐 CREATE SEQUENCE·CREATE TABLE·ALTER TABLE 또는 데이터 보정 SQL은 실행하지 않는다.
- 패널티 추가 후 마이페이지 대상 테스트 46개가 통과했다. 새 패널티 서비스 테스트 13개, 기존 서비스 13개, 계정 10개, 컨트롤러 8개, JPA 조회·Oracle 페이징 2개다. 실제 Oracle DB 실행·동시 요청 테스트를 의미하지 않는다.

## 관리비 마일리지 사용

`POST /api/mypage/charges/{chargeId}/mileage`

```json
{"amount": 10000, "expected_discount_amount": 0}
```

- 1P=1원, 1,000P 이상·1,000P 단위. 부분 사용 가능, 취소 기능 없음.
- 본인 당월 BILLED 청구만 허용. 보유 잔액 및 FINAL_AMOUNT 초과 사용 금지.
- 기존 관리자 차감과 동일한 OFFICE 행을 먼저 잠그고, 본인 청구 행을 잠근다.
- expected_discount_amount는 마지막 조회에서 받은 누적 할인액. 잠금 후 값이 달라졌으면 409로 거절한다. 재전송·다른 탭의 오래된 요청을 자동 재적용하지 않는다.
- MILEAGE_HISTORY에 USE, 음수 금액, OFFICE_CHARGE, 청구 ID를 기록한다.
- 누적 할인액 증가, FINAL_AMOUNT=TOTAL_AMOUNT-MILEAGE_DISCOUNT_AMOUNT. 최종 금액 0이면 PAID, 그 외 BILLED 유지.
- OFFICE_CHARGE_ITEM에 별도 할인 항목을 삽입하지 않는다. 청구 상세와 헤더의 할인 중복을 피한다.
- 이력 저장과 청구 갱신은 같은 Spring JPA 트랜잭션. 정상 응답은 최신 당월 관리비 조회 응답과 같다.
- 응답 유실 시 같은 POST를 자동 재전송하지 않고 GET으로 결과를 확인한다.

오류: 인증 없음 401, OFFICE 아님/비활성·탈퇴 계정 403, 소유 청구 없음 404, 요청 단위·페이징 오류 400,
잔액 부족·청구액 초과·중복 요청·청구 상태/금액 불일치 409. 메시지 직렬화는 기존 Spring 오류 설정을 따른다.

## 비밀번호 변경

`PATCH /api/mypage/password` → 성공 시 204.

```json
{"current_password":"현재 비밀번호","new_password":"새 비밀번호","confirm_password":"새 비밀번호"}
```

- 인증된 본인의 OFFICE 행을 잠근 후 현재 비밀번호를 PasswordEncoder.matches로 검증한다.
- 새 비밀번호는 기존 가입 화면과 같은 8~20자이며 확인 값과 일치해야 한다.
- 가입과 동일한 PasswordEncoder로 해시한 값만 PASSWORD_HASH에 저장한다. 평문 비밀번호 로그 없음.
- UPDATED_AT은 SYSDATE로 갱신한다. 기존 access/refresh 만료·회전·로그인 정책은 변경하지 않는다.

## 회원 탈퇴

`POST /api/mypage/withdrawal` → 성공 시 204.

```json
{"current_password":"현재 비밀번호","confirmation":"탈퇴"}
```

- 현재 비밀번호 및 확인 문구를 검증하고 OFFICE → COMPANY 순서로 잠근다.
- 같은 회사에 다른 미탈퇴 OFFICE가 있거나 회사가 이미 삭제 상태이면 409로 거절한다.
- BUSINESS_NUMBER, LOGIN_ID, EMAIL, PHONE을 기존 값 + `_d_MMdd`로 변경한다. MMdd는 DB의 SYSDATE 기준이다.
- 선택값이 NULL이면 유지한다. VARCHAR2 BYTE 제한(각 50/50/100/50)도 넘지 않도록 필요한 경우 원래 값의 앞부분만 코드 포인트 단위로 줄인다.
- 접미사 결과가 이미 존재하면 409. 같은 날 동일 ID 재가입·재탈퇴 시 충돌 값을 덮어쓰거나 임의 번호를 추가하지 않는다.
- OFFICE.STATUS_CODE=WITHDRAWN, WITHDRAWN_AT/UPDATED_AT=SYSDATE.
- COMPANY.DELETED_AT/UPDATED_AT=SYSDATE. COMPANY.STATUS_CODE는 미확인 코드를 넣지 않고 유지한다.
- 탈퇴 접미사 ID와 기존 비밀번호로 재로그인하지 못하도록 PASSWORD_HASH를 추측할 수 없는 임의 비밀번호의 해시로 교체한다. 기존 로그인 구현 파일은 수정하지 않는다.
- 회사·사무실 변경은 하나의 트랜잭션이며 실패하면 전부 롤백한다. 차량·거래 이력은 삭제하지 않는다.
- 성공 후 프론트는 기존 logoutAction을 재사용해 현재 기기의 로컬 로그인 정보와 refresh 토큰을 정리하고 로그인 화면으로 이동한다.

사용자 요청에 따라 기존 인증 파일은 수정하지 않았다. 기존 토큰은 OFFICE_ID에 연결되어 있지 않으므로,
탈퇴 후 원래 LOGIN_ID로 새 계정을 생성하면 예전 토큰이 새 계정으로 인증될 수 있는 위험은 남아 있다.
동일 ID 재가입 시나리오는 시연 범위 밖으로 합의했고 토큰 보완은 이번 범위에서 제외했다. 전역 토큰 폐기나 재가입 방지가 구현되었다고 간주하면 안 된다.

## 검증 및 팀 조율

- 기존 OracleLegacyDialect·ddl-auto=validate 설정을 유지한다. Hibernate 메타데이터 및 Repository 쿼리는 DB 접속 없이 테스트한다.
- Oracle 11g LimitHandler의 ROWNUM 페이징 생성 검증 포함. 실제 Oracle에서의 잠금 대기·동시성·조회 실행은 별도 통합 검증 필요.
- 공유 DB에서 쓰기 테스트·마이그레이션·테스트 데이터 생성은 실행하지 않는다.
- 기존 사용자 마일리지 범용 create/update/delete는 변경하지 않았다. 이 경로로 잔액을 감소시키는 작업이 가능하면 동일 OFFICE 잠금 규칙 적용이 필요하다. 이 조율 없이는 시스템 전체 동시 차감 안전성을 보장하지 않는다.
- 기존 승인 신고 API는 REPORT.TARGET_VEHICLE_ID와 VEHICLE.OFFICE_ID 관계로 소유권을 판단한다. 패널티 화면은 실제 VEHICLE_PENALTY 소유권 조회로 변경했다. VEHICLE_PENALTY와 REPORT 사이에 확인되지 않은 연결을 임의로 만들지 않는다.
- 비밀번호 변경·회원 탈퇴는 추가 승인에 따라 연동했다. 기존 PasswordChange의 평문 비밀번호 console 출력은 제거했다.
- 기존 JWT 필터·토큰 발급·refresh·OAuth·보안 설정 파일은 사용자 요청에 따라 수정하지 않았다. 기존 인증 로그도 변경하지 않았다.

## 구현 파일

프론트 (`front/APCMS/src/`):

- `pages/user/mypage/MyPage.tsx`: 메뉴 4개 및 기존 차량·마일리지 컴포넌트 연결 유지.
- `pages/user/mypage/MyInfo.tsx`, `MyInfo.module.css`: 계정·패널티·관리비 3개 상자와 상세. 패널티 위반금액 표시 및 사용자 측 자동 청구 반영 호출. 내 정보에는 주차 내역 상자·최근 목록을 두지 않는다.
- `pages/user/mypage/ParkingHistory.tsx`: 본인 입출차 내역 및 페이지 탐색.
- `pages/user/mypage/PasswordChange.tsx`, `AccountManagement.tsx`: 현재 비밀번호 확인을 포함한 변경·탈퇴 화면.
- `api/myPageApi.ts`: 기존 userApi를 사용하는 신규 마이페이지 전용 클라이언트.

백엔드 (`back/apcms_u/src/main/java/kr/co/alpharking/`):

- `controller/mypage/MyPageController.java`, `service/mypage/MyPageService.java`, `MyPageAccountService.java`, `dto/mypage/MyPageDtos.java`.
- `entity/mypage/OfficeCharge.java`, `OfficeChargeItem.java`.
- `entity/mypage/VehiclePenalty.java`: 기존 패널티 테이블의 읽기 전용 매핑.
- `repository/mypage/MyPagePenaltyRepository.java`, `service/mypage/MyPagePenaltyService.java`: 실제 패널티 조회와 당월 청구 중복 방지·자동 생성.
- `entity/cmn/CommonCodeDetail.java`, `CommonCodeKey.java`: 공통코드 패키지 이동. 기존 JPQL 엔티티 이름은 호환성을 위해 유지.
- `repository/mypage/MyPageOfficeRepository.java`, `MyPageCompanyRepository.java`, `OfficeChargeRepository.java`, `OfficeChargeItemRepository.java`, `MyPageMileageRepository.java`, `MyPageParkingUsageRepository.java`, `MyPageReportRepository.java`.

테스트 (`back/apcms_u/src/test/java/kr/co/alpharking/`):

- `controller/mypage/MyPageControllerTest.java`.
- `service/mypage/MyPageServiceTest.java`, `MyPageAccountServiceTest.java`, `MyPageJpaQueryTest.java`.
- `service/mypage/MyPagePenaltyServiceTest.java`: 합산·생성·중복 방지·기존 할인 보존·롤백·위반 금액 응답 검증.

기존 관리자 차감 보완은 앞선 승인 작업의 변경을 보존했으며 이번 단계에서 추가 수정하지 않았다.

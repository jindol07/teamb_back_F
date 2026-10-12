# Spring Boot 연동 계약 (초안, 실제 DTO 검증 필요)

- AI → Spring Boot: `GET /api/auth/me` Authorization: Bearer JWT, 반환 JSON `{ "officeId": "1" }` 또는 `{ "data": { "officeId": "1" } }`
- AI → Spring Boot: `GET /api/reservation`, `GET /api/parkingusage` (본인 Office 데이터만 반환; Spring Boot가 JWT에서 Office 식별)
- 향후 미확정: `GET /api/vehicle`, `/api/mileage`, `/api/maintenance` (환경변수로 변경 가능)
- AI → Spring Boot: `POST /api/inquiry/add` Authorization: Bearer JWT

예시 요청 JSON (서버 Controller DTO 확인 후 매핑 필요):
```json
{
  "conversationId": "client-generated-uuid",
  "question": "내 예약 어디야?",
  "answer": "...",
  "type": "RESERVATION",
  "sources": [{"source":"api:RESERVATION", "page":null}]
}
```

**중요:** `INQUIRY_CONVERSATION`과 `INQUIRY_MESSAGE` 두 테이블에 한 요청으로 대화 1건(upsert) + 질문/답변 메시지 2건을 **Spring Boot 내부 단일 트랜잭션**으로 저장하도록 `POST /api/inquiry/add` 컨트롤러를 구현하세요. DB 테이블/DTO 스키마가 제공되지 않아 Python은 SQL을 작성하지 않고 저장 API를 호출합니다. JWT로 식별한 Office만 저장·조회 가능해야 합니다. 서버가 동일 conversationId 재시도 시 메시지를 중복 삽입하지 않으려면 별도 idempotency key 설계를 권장합니다.

MOCK 모드는 해당 이름의 SQLite 테이블을 만들어 실제 INSERT를 수행합니다. **운영 DB에 직접 저장하는 것이 아닙니다.**

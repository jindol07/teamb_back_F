# Spring Boot 챗봇 본인 조회 계약

## 현재 구현한 읽기 API

- 기본 URL: `http://localhost:80/alpharking/` (개발 서버 주소는 환경변수로 지정)
- 모든 요청은 `Authorization: Bearer JWT` 필요. 기존 JWT 필터가 조회한 `Office`로 소유자를 결정합니다.
- `GET /api/chatbot/me`: `{ "officeId": 2 }`. 비밀번호·전화번호·이메일 등은 반환하지 않습니다.
- `GET /api/chatbot/me/usage`: 실제 입출차 이력, 입차 시각 최신순 최대 50건.
- `GET /api/chatbot/me/reservations`: 예약 이력(취소 포함), 등록 시각 최신순 최대 50건.
- `GET /api/chatbot/me/vehicles`: 삭제되지 않은 본인 차량, 등록 시각 최신순 최대 50건.
- 클라이언트의 `officeId`/`mock_user_id`로 다른 사용자를 선택할 수 없습니다.
- 기존 전체 예약 API는 사용하지 않습니다. 현재 기간 필터는 미지원이며 LLM에도 조회 범위를 명시합니다.
- API 모드에서는 질문·답변을 Spring Boot에 저장한 후 `saved: true`와 서버 발급 대화 ID를 반환합니다.
  프론트는 최근 대화를 서버에서 복원하며, 개인 대화를 공통 localStorage에 저장하지 않습니다.
- 마일리지·청구 조회는 미지원으로 안내합니다. 실제 Oracle 조회와 계정 2개의 브라우저 검증은 별도 필요합니다.
- 프론트: `VITE_INQUIRY_DATA_MODE=API`, AI: `DATA_MODE=API`. 설정 후 각각 서버를 재시작합니다.
- 이전 MOCK 모드는 개발 테스트에서만 사용합니다.

## 대화 저장·복원 API (기존 테이블 사용)

- AI → Spring Boot: `POST /api/chatbot/conversations/exchanges`, Authorization: Bearer JWT
- React/AI → Spring Boot: `GET /api/chatbot/conversations/{id}/messages`, 본인 대화의 최근 메시지 최대 40개.
- React → Spring Boot: `GET /api/chatbot/conversations/latest`, 본인의 최근 미종료 대화와 메시지.
- 조회·추가 저장은 매번 JWT Office와 소유권을 확인합니다. 타인/없는/종료된 대화는 404입니다.

첫 질문 저장 요청 JSON:
```json
{
  "conversationId": null,
  "requestId": "ff4f5590-2259-4b54-aaab-ff81b56a3d88",
  "question": "내 예약 어디야?",
  "answer": "...",
  "type": "RESERVATION",
  "sources": [{"source":"api:RESERVATION", "page":null}]
}
```

- 첫 저장은 `SEQ_INQUIRY_CONVERSATION`으로 대화를 만들고, 이후에는 응답의 `conversationId`를 재사용합니다.
- DB NUMBER(19) ID는 JSON에서 숫자 문자열로 전달합니다. 첫 React → AI 요청의 `conversation_id`는 null입니다.
- 메시지는 `SEQ_INQUIRY_MESSAGE`로 생성하며, 발신자 공통 코드는 `INQUIRY_SENDER`의 `USER`, `AI`입니다.
- `@Transactional`로 대화와 질문·답변을 함께 저장합니다. `TITLE`은 첫 질문을 UTF-8 100바이트 이내로 자릅니다.
- `RAG_SOURCE_JSON`에는 `{requestId, type, sources}` JSON을 저장합니다. Office 행 잠금 후 요청 UUID를 확인하여
  같은 요청 재시도 시 중복 INSERT 대신 기존 답변을 반환합니다. 스키마 변경은 없습니다.
- FastAPI는 소유권 확인된 서버의 최근 메시지 12개를 각 1000자, 총 12000자 이내로 LLM 문맥에 넣습니다.
- 브라우저는 JWT가 바뀌면 메모리 대화를 초기화하고 본인 기록만 다시 조회합니다.
- 첫 저장 실패/응답 유실 시 프론트는 같은 질문의 재시도에 같은 요청 UUID를 사용합니다.
- 실제 Oracle의 CLOB·JSON_VALUE·시퀀스·롤백 동작과 브라우저 계정 2개 검증은 별도 필요합니다.

MOCK 모드는 해당 이름의 SQLite 테이블을 만들어 실제 INSERT를 수행합니다. **운영 DB에 직접 저장하는 것이 아닙니다.**

# APCMS 통합 AI — YOLO/OCR + RAG 1:1 문의

## 구조
- `main.py`: FastAPI 통합 진입점; 기존 `/recognize` 경로 유지
- `ai_vision/`: 기존 `recognizer.py`, `api.py`, 모델, 검증용 테스트 이미지/스크립트
- `ai_inquiry/main.py`: React 채팅 API `/api/inquiry/chat`
- `ai_inquiry/router.py`: 정책 / 본인 예약 / 본인 이용기록 / 차량 / 마일리지 / 관리비 분류
- `ai_inquiry/service.py`: 개인조회 → RAG → LLM → 저장 API
- `ai_inquiry/clients/backend_client.py`: Spring Boot 로그인 검증·읽기 API·`POST /api/inquiry/add`
- `ai_inquiry/mocks/`: 더미 Office 2명과 실제 SQLite INSERT 테스트
- `ai_inquiry/documents/알파킹정책.pdf`: 사용자 제공 정책 원본
- `react/AlpacaChatbot.tsx`: 기존 CSS class 유지하고 mock 답변 제거한 React 코드

## 로컬 실행
Python 가상환경을 `apcms_ai`에 만들고 기존 비전 requirements와 RAG 라이브러리를 함께 설치합니다.
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
# .env.example 을 .env 로 복사하고 GOOGLE_API_KEY 설정
python -m ai_inquiry.build_index
#uvicorn main:app --reload --port 8000
#윈도우 서버 run
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
#리눅스(우분투) 서버 run
python -m uvicorn main:app --host 0.0.0.0 --port 8000
#http://127.0.0.1:8001/docs
```
**PaddleOCR/PaddlePaddle 버전·OS 종속성:** 기존 프로젝트 설치 환경 유지 권장. `/recognize` 는 원본처럼 서버 시작 시 YOLO/Paddle 모델을 로딩합니다. 모델을 로딩할 수 없는 머신은 통합 서버가 시작되지 않을 수 있습니다.

## 테스트 (Gemini 키 없이 라우팅/DB INSERT)
```bash
# .env: APP_ENV=development, DATA_MODE=MOCK, LLM_MODE=STUB
python -m pytest ai_inquiry/tests -q
```
`LLM_MODE=STUB`은 **RAG 검색을 생략하고 테스트 답변을 반환**합니다. 실제 정책 검색 + LLM 답변은 `LLM_MODE=GEMINI`, 유효한 키, `python -m ai_inquiry.build_index` 필요.

API 예시 POST `http://localhost:8000/api/inquiry/chat`
```json
{"conversation_id":"test-conversation-1","question":"내 주차 이용 기록 알려줘","mock_user_id":"1"}
```
정상 응답: `{ "conversation_id": "...", "type":"USAGE", "answer":"...", "sources":[...], "saved": true }`. MOCK에서 SQLite `INQUIRY_CONVERSATION`, `INQUIRY_MESSAGE`에 실제로 두 행의 메시지가 삽입됩니다.

## 운영 API 연동
`.env`: `APP_ENV=production`, `DATA_MODE=API`, `LLM_MODE=GEMINI` 설정. 인증 API(`/api/auth/me`)가 아직 없으므로 개발 중에는 MOCK만 사용. React `.env`에는 `VITE_AI_API_BASE_URL=http://localhost:8000`, `VITE_INQUIRY_DATA_MODE=MOCK`, `VITE_MOCK_USER_ID=1`을 설정합니다. 인증 적용 뒤 React의 `getAuthToken()` 구현 및 API 모드 설정이 필수입니다.

### 저장 API 주의
실제 Spring Boot `api/inquiry/add` 요청 DTO를 받지 못했으므로 예시 payload와 통신 코드를 마련했습니다. **Spring Boot 백엔드 컨트롤러의 JSON DTO를 확인하여 `BackendClient.add_conversation`의 payload 매핑을 조정해야 실제 저장됩니다.** `/api/reservation`, `/api/parkingusage` 응답 JSON도 실제 스키마가 확정되면 매핑을 검증해야 합니다. `ai_inquiry/API_CONTRACT.md` 참조.

### 채팅 세션
현재 React `conversationId`는 컴포넌트 생명주기 동안 유지되며 재접속 시 새 ID입니다. 기존 대화 이력 로딩 API/재시도 중복 방지는 별도 백엔드 개발이 필요합니다. 서버는 무상태이며 이번 버전은 후속 대화 맥락을 자동 로딩하지 않습니다.

### 기존 vision 스크립트
기존 테스트 스크립트는 `ai_vision/`으로 이동했습니다. 원본에 상대경로/개발환경 가정이 남은 개별 실험 스크립트는 추가 수정이 필요할 수 있으며, 원본 README를 `ai_vision/ORIGINAL_README.md`로 보존했습니다.

### AI 프로젝트 3개 파이썬 버전 3.12 통일!
3.12 설치

& "D:\finalProjectB\app\Python312\python.exe" -m venv .venv312

.venv312\Scripts\Activate

python -m pip install --upgrade pip

python -m pip install -r requirements.txt

-- 기존 가상환경 제거
Remove-Item -Recurse -Force .venv

-- 제거 완료: False
Test-Path .venv
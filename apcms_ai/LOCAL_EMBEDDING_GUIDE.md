# 로컬 임베딩 전환 안내

기존 `apcms_ai` 프로젝트와 동일한 구조입니다. YOLO/OCR 및 문의 API 코드는 유지합니다.

## 설치

```powershell
cd D:\finalProjectB\back\apcms_ai
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

`.env`에서 `GEMINI_EMBED_MODEL`을 제거하고 아래를 추가하세요.

```dotenv
LOCAL_EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

`GOOGLE_API_KEY`는 Gemini 답변 생성에 계속 필요합니다. 임베딩에는 사용하지 않습니다.

## 정책 인덱스 생성

FastAPI 서버를 종료한 상태에서 다음 명령을 실행합니다.

```powershell
python -m ai_inquiry.build_index
```

최초 실행은 HuggingFace 모델 다운로드로 시간이 걸리며 인터넷이 필요합니다. 이후 모델은 로컬 캐시에서 로드됩니다. 인덱싱 성공 후 FastAPI를 재시작하세요.

## 주의

- 기존 Google 임베딩으로 생성된 Chroma 인덱스는 로컬 임베딩과 호환되지 않습니다. 새 인덱스로 교체해야 합니다.
- Chroma는 저장/검색 시 같은 임베딩 모델을 사용해야 합니다.
- 이 변경은 Gemini 답변 생성의 429 한도 문제까지 해결하지는 않습니다.
- 인덱스 교체 시 서버가 기존 DB 파일을 열고 있으면 Windows에서 폴더 이름 변경이 실패할 수 있습니다.
- 기존 프로젝트의 `.env` 파일은 포함하지 않았습니다. 로컬 환경의 값을 유지하고 위 항목만 수정하세요.

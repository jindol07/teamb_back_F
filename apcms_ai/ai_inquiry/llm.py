"""Gemini 답변 생성과 정책 검색용 Gemini Embedding 2 연결."""
import os
import math
from functools import lru_cache
from langchain_core.embeddings import Embeddings
from ai_inquiry.config import settings

EMBEDDING_FORMAT = 'gemini2-retrieval-v1'


class GeminiEmbeddings(Embeddings):
    """Chroma의 문서·질문 인터페이스를 Google SDK에 연결합니다."""

    def __init__(self, model, dimensions):
        from google import genai
        from google.genai import types

        self.model = model
        self.dimensions = dimensions
        self.client = genai.Client(
            api_key=os.environ['GOOGLE_API_KEY'], vertexai=False,
            http_options=types.HttpOptions(timeout=30000),
        )

    def _embed(self, texts):
        from google.genai import types

        vectors = []
        # Content별로 분리해야 여러 문서가 하나의 벡터로 합쳐지지 않습니다.
        for start in range(0, len(texts), 16):
            batch = texts[start:start + 16]
            try:
                response = self.client.models.embed_content(
                    model=self.model,
                    contents=[types.Content(parts=[types.Part(text=text)]) for text in batch],
                    config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
                )
            except Exception as error:
                # 키·요청 원문이 포함될 수 있는 외부 오류 대신 상태 코드만 전달합니다.
                code = getattr(error, 'code', None)
                raise RuntimeError(f'Gemini 임베딩 요청 실패 (HTTP {code or "연결 오류"}). API 키·할당량·네트워크를 확인하세요.') from None
            rows = [list(item.values or []) for item in (response.embeddings or [])]
            if len(rows) != len(batch) or any(
                len(row) != self.dimensions or not all(math.isfinite(value) for value in row)
                for row in rows
            ):
                raise RuntimeError('Gemini 임베딩 개수 또는 차원이 요청과 일치하지 않습니다.')
            vectors.extend(rows)
        return vectors

    def embed_documents(self, texts):
        # Embedding 2는 task_type 대신 검색용 문서·질문 접두사를 사용합니다.
        return self._embed([f'title: none | text: {text}' for text in texts])

    def embed_query(self, text):
        return self._embed([f'task: search result | query: {text}'])[0]

@lru_cache
def get_chat():
    if not os.getenv('GOOGLE_API_KEY'):
        raise RuntimeError('GOOGLE_API_KEY is required for Gemini LLM answers')
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=settings()['model'], temperature=0)

@lru_cache
def get_embeddings():
    # 정책 문서 저장과 질문 검색에서 반드시 같은 모델을 사용해야 합니다.
    cfg = settings()
    if not os.getenv('GOOGLE_API_KEY'):
        raise RuntimeError('GOOGLE_API_KEY is required for Gemini embeddings')
    if cfg['embedding_model'] != 'gemini-embedding-2':
        raise ValueError('현재 임베딩 연결은 gemini-embedding-2 전용입니다.')
    if not 128 <= cfg['embedding_dimensions'] <= 3072:
        raise ValueError('Gemini 임베딩 차원은 128~3072 범위여야 합니다.')
    return GeminiEmbeddings(cfg['embedding_model'], cfg['embedding_dimensions'])

"""Chroma 의미 검색 + 로컬 키워드 검색 (추가 API 호출 없음)."""
from pathlib import Path
from functools import lru_cache
import re
import json
from langchain_chroma import Chroma
from ai_inquiry.llm import get_embeddings, EMBEDDING_FORMAT
from ai_inquiry.config import settings

# Hugging Face 인덱스(chroma_db)는 그대로 두고 Gemini 인덱스만 사용합니다.
CHROMA_DIR = Path(__file__).resolve().parent / 'chroma_db_gemini'

# 정책 도메인 용어의 질문 표현 차이를 보완한다.
SYNONYMS = {
    '마일리지': ('마일리지', '적립', '차감'),
    '사용처': ('사용처', '사용', '차감', '관리비'),
    '쓸': ('사용', '차감'),
    '무엇': ('사용', '혜택'),
    '회원가입': ('회원가입', '최초 차량', '등록'),
    '추천': ('추천', '재추천', '거절', '수락'),
}
STOPWORDS = {'어떻게', '하나요', '있나요', '되나요', '무엇을', '어떤', '알려줘', '대한', '관련', '것은'}

@lru_cache
def get_store():
    if not (CHROMA_DIR / 'chroma.sqlite3').exists():
        raise FileNotFoundError('정책 인덱스가 없습니다. python -m ai_inquiry.build_index 실행 후 다시 시도하세요.')
    # 생성이 완료되지 않았거나 다른 모델·차원으로 만든 인덱스는 섞어 쓰지 않습니다.
    try:
        manifest = json.loads((CHROMA_DIR / 'embedding_manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise RuntimeError('Gemini 정책 인덱스 생성이 완료되지 않았습니다. 인덱스를 확인하세요.') from None
    cfg = settings()
    if (manifest.get('model') != cfg['embedding_model']
            or manifest.get('dimensions') != cfg['embedding_dimensions']
            or manifest.get('format') != EMBEDDING_FORMAT):
        raise RuntimeError('정책 인덱스와 임베딩 설정이 다릅니다. 같은 설정으로 인덱스를 다시 생성하세요.')
    return Chroma(
        collection_name='parking_policies',
        persist_directory=str(CHROMA_DIR),
        embedding_function=get_embeddings(),
    )


def _terms(question):
    tokens = re.findall(r'[가-힣A-Za-z0-9-]+', question.lower())
    terms = {t for t in tokens if len(t) >= 2 and t not in STOPWORDS}
    for trigger, words in SYNONYMS.items():
        if trigger in question.lower():
            terms.update(w.lower() for w in words)
    return terms


def _keyword_score(content, terms):
    text = content.lower()
    return sum(1 for term in terms if term in text)


def search_policy(question, k=6):
    store = get_store()
    # 의미 검색은 후보를 넓게 찾되 Gemini에는 k개만 전달한다.
    semantic = store.similarity_search(question, k=max(k * 2, 12))
    # 기존 인덱스의 전체 청크를 가져와 로컬 키워드 매칭한다.
    raw = store.get(include=['documents', 'metadatas'])
    terms = _terms(question)
    candidates = {}

    def add(content, metadata, semantic_rank=None):
        if not content:
            return
        # 동일한 문서 조각은 한 번만 반영한다.
        key = (metadata.get('source', ''), metadata.get('page'), content)
        item = candidates.setdefault(key, {'content': content, 'metadata': metadata, 'score': 0.0})
        if semantic_rank is not None:
            item['score'] += 1.0 / (10 + semantic_rank)

    for rank, doc in enumerate(semantic, start=1):
        add(doc.page_content, doc.metadata, semantic_rank=rank)
    for content, metadata in zip(raw.get('documents') or [], raw.get('metadatas') or []):
        add(content, metadata or {})

    for item in candidates.values():
        item['score'] += 0.015 * _keyword_score(item['content'], terms)

    ranked = sorted(candidates.values(), key=lambda item: item['score'], reverse=True)[:k]
    sources = []
    contexts = []
    for item in ranked:
        meta = item['metadata']
        info = {'source': meta.get('source', '알 수 없음'), 'page': meta.get('page')}
        if info not in sources:
            sources.append(info)
        contexts.append(
            f"[출처: {info['source']}, 페이지: {info['page']}]\n{item['content']}"
        )
    return '\n\n'.join(contexts), sources

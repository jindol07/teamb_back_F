from pathlib import Path
from functools import lru_cache
from langchain_chroma import Chroma
from ai_inquiry.llm import get_embeddings

CHROMA_DIR = Path(__file__).resolve().parent / 'chroma_db'

@lru_cache
def get_store():
    if not (CHROMA_DIR / 'chroma.sqlite3').exists():
        raise FileNotFoundError('정책 인덱스가 없습니다. python build_index.py 실행 후 다시 시도하세요.')
    return Chroma(collection_name='parking_policies', persist_directory=str(CHROMA_DIR),
                  embedding_function=get_embeddings())

def search_policy(question, k=4):
    docs = get_store().similarity_search(question, k=k)
    sources = []
    for doc in docs:
        info = {'source': doc.metadata.get('source', '알 수 없음'), 'page': doc.metadata.get('page')}
        if info not in sources:
            sources.append(info)
    return '\n\n'.join(doc.page_content for doc in docs), sources

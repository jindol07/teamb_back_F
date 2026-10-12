"""교육 예제 ch15_build_chroma.py를 수정. 정책 파일만 인덱싱한다."""
from pathlib import Path
import shutil
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from ai_inquiry.llm import get_embeddings
from ai_inquiry.vector_store import CHROMA_DIR

DOC_DIR = Path(__file__).resolve().parent / 'documents'

def main():
    docs = []
    for path in sorted(DOC_DIR.iterdir()):
        if path.suffix.lower() == '.pdf':
            for d in PyPDFLoader(str(path)).load():
                d.metadata = {'source': path.name, 'page': int(d.metadata.get('page', 0)) + 1}
                docs.append(d)
        elif path.suffix.lower() in {'.txt', '.md'}:
            docs.append(Document(page_content=path.read_text(encoding='utf-8'),
                                 metadata={'source': path.name, 'page': 1}))
    if not docs:
        raise RuntimeError('documents/ 폴더에 정책 PDF/TXT/MD를 추가하세요.')
    chunks = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80).split_documents(docs)
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)  # 빌드 시 현재 collection을 교체. 운영에서는 원자적 교체 필요.
    Chroma.from_documents(documents=chunks, embedding=get_embeddings(),
                          collection_name='parking_policies', persist_directory=str(CHROMA_DIR))
    print(f'인덱싱 완료: {len(docs)}문서 / {len(chunks)}청크 / {CHROMA_DIR}')

if __name__ == '__main__':
    main()

"""알파킹 정책 문서 Chroma 인덱싱"""

from pathlib import Path
import json

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from ai_inquiry.llm import get_embeddings, EMBEDDING_FORMAT
from ai_inquiry.config import settings
from ai_inquiry.vector_store import CHROMA_DIR


DOC_DIR = Path(__file__).resolve().parent / "documents"


def main():

    docs = []

    # 1. 정책 문서 읽기
    for path in sorted(DOC_DIR.iterdir()):

        if path.suffix.lower() == ".pdf":

            for doc in PyPDFLoader(str(path)).load():
                doc.metadata = {
                    "source": path.name,
                    "page": int(doc.metadata.get("page", 0)) + 1
                }
                docs.append(doc)

        elif path.suffix.lower() in {".txt", ".md"}:

            docs.append(
                Document(
                    page_content=path.read_text(encoding="utf-8"),
                    metadata={
                        "source": path.name,
                        "page": 1
                    }
                )
            )

    if not docs:
        raise RuntimeError("정책 문서가 없습니다.")

    # 2. 문서 청킹
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80
    ).split_documents(docs)

    # 3. 새 Gemini 폴더만 생성합니다. 기존 인덱스를 자동 삭제하지 않습니다.
    # 재생성이 필요하면 서버 종료 후 기존 Gemini 폴더를 별도 백업·이동하세요.
    if CHROMA_DIR.resolve().name != 'chroma_db_gemini':
        raise RuntimeError('Gemini 전용 인덱스 경로가 아닙니다.')
    if CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir()):
        raise RuntimeError('Gemini 인덱스 폴더가 이미 있습니다. 서버 종료 후 별도 보관하고 다시 실행하세요.')
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    # 4. Gemini 임베딩으로 Chroma DB 생성 (기존 문서 분할·출처 구조 유지)
    store = Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        collection_name="parking_policies",
        persist_directory=str(CHROMA_DIR)
    )

    if len(store.get(include=[])['ids']) != len(chunks):
        raise RuntimeError('저장된 정책 조각 수가 생성한 조각 수와 일치하지 않습니다.')
    cfg = settings()
    # 마지막에 완료 정보를 기록해 실패·부분 생성 인덱스의 사용을 막습니다.
    (CHROMA_DIR / 'embedding_manifest.json').write_text(json.dumps({
        'model': cfg['embedding_model'],
        'dimensions': cfg['embedding_dimensions'],
        'format': EMBEDDING_FORMAT,
        'chunks': len(chunks),
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    print(
        f"인덱싱 완료: "
        f"{len(docs)}페이지/문서 / "
        f"{len(chunks)}청크 / "
        f"{CHROMA_DIR}"
    )


if __name__ == "__main__":
    main()

"""알파킹 정책 문서 Chroma 인덱싱"""

from pathlib import Path
import shutil

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from ai_inquiry.llm import get_embeddings
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

    # 3. 기존 Chroma DB 삭제
    # 반드시 FastAPI 서버를 종료한 상태에서 실행
    #if CHROMA_DIR.exists():
    #    shutil.rmtree(CHROMA_DIR)
    # 3. 10/23 배포 관련
    if CHROMA_DIR.exists():
        for item in CHROMA_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    # 4. 로컬 임베딩을 이용해 Chroma DB 생성
    store = Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        collection_name="parking_policies",
        persist_directory=str(CHROMA_DIR)
    )

    print(
        f"인덱싱 완료: "
        f"{len(docs)}페이지/문서 / "
        f"{len(chunks)}청크 / "
        f"{CHROMA_DIR}"
    )


if __name__ == "__main__":
    main()
from dotenv import load_dotenv
from langchain.retrievers import EnsembleRetriever
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

load_dotenv()

PERSIST_DIR = "cache/kifrs_chroma"
COLLECTION_NAME = "kifrs"
EMBEDDING_MODEL = "text-embedding-3-large"


QUERIES = [
    ("수익 인식 시점",      "K-IFRS 1115"),
    ("리스 회계처리 방법",   "K-IFRS 1116"),
    ("금융자산 손상 인식",   "K-IFRS 1109"),
    ("재고자산 평가 방법",   "K-IFRS 1002"),
    ("유형자산 감가상각",    "K-IFRS 1016"),
    ("법인세 인식 기준",     "K-IFRS 1012"),
    ("보험계약 측정 모델",   "K-IFRS 1117"),
]


def main() -> None:
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=OpenAIEmbeddings(model=EMBEDDING_MODEL),
        persist_directory=PERSIST_DIR,
    )

    raw = vectorstore.get()
    docs = [
        Document(page_content=raw["documents"][i], metadata=raw["metadatas"][i])
        for i in range(len(raw["documents"]))
    ]
    print(f"Loaded {len(docs)} docs for BM25")

    bm25 = BM25Retriever.from_documents(docs)
    bm25.k = 10

    hybrid = EnsembleRetriever(
        retrievers=[bm25, vectorstore.as_retriever(search_kwargs={"k": 10})],
        weights=[0.5, 0.5],
    )

    for query, expected in QUERIES:
        print(f"\n=== Query: {query} (기대 표준: {expected}) ===")
        hits = hybrid.invoke(query)[:3]
        for doc in hits:
            meta = doc.metadata
            mark = "O" if meta.get("standard") == expected else " "
            head = doc.page_content[:120].replace("\n", " ")
            std = str(meta.get("standard") or "-")
            para = str(meta.get("paragraph") or "-")
            print(f"  {mark} {std:25s} {para:8s} | {head}")


if __name__ == "__main__":
    main()
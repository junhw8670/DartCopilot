"""K-IFRS RAG MCP server.

Two tools:
- search_kifrs: hybrid BM25 + dense-vector semantic search over the index
- get_standard_by_number: exact metadata lookup by standard/paragraph reference
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv 
from langchain_chroma import Chroma
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("KifrsRAG")

BASE_DIR = Path(__file__).resolve().parent.parent
VECTOR_DIR = BASE_DIR / "cache" / "kifrs_chroma"
COLLECTION_NAME = "kifrs"
EMBEDDING_MODEL = "text-embedding-3-large"

embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
vectorstore = Chroma(
    collection_name=COLLECTION_NAME,
    embedding_function=embeddings,
    persist_directory=str(VECTOR_DIR),
)


_hybrid: EnsembleRetriever | None = None

def _get_hybrid() -> EnsembleRetriever:
    """Lazy build/cache BM25 + dense vector hybrid retriever.""" 
    global _hybrid
    if _hybrid is None:
        raw = vectorstore.get()
        docs = [
            Document(page_content=raw["documents"][i], metadata=raw["metadatas"][i])
            for i in range(len(raw["documents"]))
        ]
        bm25 = BM25Retriever.from_documents(docs)
        bm25.k = 10

        _hybrid = EnsembleRetriever(
            retrievers=[bm25, vectorstore.as_retriever(search_kwargs={"k": 10})],
            weights=[0.5, 0.5],
        )
    return _hybrid

@mcp.tool()
def search_kifrs(query: str, top_k: int = 5) -> dict[str, Any]:
    """Search the K-IFRS corpus by hybrid BM25 + dense vector similarity.

    Runs both keyword (BM25) and semantic (cosine) search over the indexed
    standards via LangChain's EnsembleRetriever, which internally fuses the
    rankings with Reciprocal Rank Fusion. Each result includes the standard
    number, paragraph number, body text, and source PDF for citation.

    Args:
        query: Natural-language Korean query
            (e.g., "수익 인식 시점", "리스 회계처리 방법", "금융자산 손상").
        top_k: Number of fused results to return. Default 5.

    Returns:
        {
            "query": "수익 인식 시점",
            "results": [
                {
                    "standard": "K-IFRS 1115",
                    "standard_name": "고객과의 계약에서 생기는 수익",
                    "paragraph": "31",
                    "text": "...",
                    "source_file": "시행중_K-IFRS_제1115호_...pdf"
                },
                ...
            ]
        }

        ALWAYS cite (standard, paragraph) in the final answer.
    """
    hits = _get_hybrid().invoke(query)[:top_k]
    return {
        "query": query,
        "results": [
            {
                "standard": d.metadata.get("standard"),
                "standard_name": d.metadata.get("standard_name"),
                "paragraph": d.metadata.get("paragraph"),
                "text": d.page_content,
                "source_file": d.metadata.get("source_file"),
            }
            for d in hits
        ],
    }
    
if __name__ == "__main__":
    mcp.run(transport="stdio")
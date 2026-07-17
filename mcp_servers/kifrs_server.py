from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv 
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from mcp.server.fastmcp import FastMCP

import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

mcp = FastMCP("KifrsRAG")

VECTOR_DIR = Path(
    os.getenv(
        "KIFRS_VECTOR_DIR",
        str(BASE_DIR / "cache" / "kifrs_chroma"),
    )
).resolve()

COLLECTION_NAME = "kifrs"
EMBEDDING_MODEL = "text-embedding-3-large"

embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

vectorstore = Chroma(
    collection_name=COLLECTION_NAME,
    embedding_function=embeddings,
    persist_directory=str(VECTOR_DIR),
)


@mcp.tool()
def search_kifrs(query: str, top_k: int = 8) -> dict[str, Any]:
    """Search the K-IFRS corpus using dense vector similarity.

    Runs semantic search over the indexed K-IFRS standards.
    Each result includes the standard number, paragraph number, body text, and source PDF for citation.

    Args:
        query: Natural-language Korean query
            (e.g., "수익 인식 시점", "리스 회계처리 방법", "금융자산 손상").
        top_k: Number of vector search results to return. Default 8.

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
    hits = vectorstore.similarity_search(
        query=query,
        k=top_k,
    )
    return {
        "query": query,
        "results": [
            {
                "standard": d.metadata.get("standard"),
                "standard_name": d.metadata.get("standard_name"),
                "paragraph": d.metadata.get("paragraph"),
                "section" : d.metadata.get("section"),
                "text": d.page_content,
                "source_file": d.metadata.get("source_file"),
            }
            for d in hits
        ],
    }
    
if __name__ == "__main__":
    mcp.run(transport="stdio")
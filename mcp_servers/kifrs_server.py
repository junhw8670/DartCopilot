from mcp.server.fastmcp import FastMCP
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from pathlib import Path
from typing import Optional

mcp = FastMCP("KifrsRAG")

VECTOR_DIR = Path(__file__).resolve().parent.parent / "cache" / "kifrs_chroma"
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma(
    collection_name="kifrs",
    embedding_function=embeddings,
    persist_directory=str(VECTOR_DIR),
)

@mcp.tool()
def search_kifrs(query: str, top_k: int = 5) -> dict:
    """Search the K-IFRS corpus by semantic similarity.

    Performs cosine-similarity search over pre-embedded K-IFRS body text (62 standards, BC sections excluded). 
    Each result includes the standard number, paragraph number, body text, and source PDF for citation.

    Args:
        query: Search query in Korean natural language (e.g., "수익 인식 시점", "금융상품 분류 기준", "리스 회계 처리 방법").
               Precision improves with accurate accounting terminology.
        top_k: Number of results. Default 5.

    Returns:
        {
            "query": "수익 인식 시점",
            "results": [
                {
                    "standard": "K-IFRS 1115",
                    "standard_name": "고객과의 계약에서 생기는 수익",
                    "paragraph": "31",
                    "text": "기업은 고객에게 약속한 재화나 용역...",
                    "source_file": "K-IFRS_1115_수익.pdf",
                    "score": 0.87
                },
                ...
            ]
        }

        ALWAYS cite (standard, paragraph) in the final answer.
    """
    docs = vectorstore.similarity_search_with_score(query, k=top_k)
    return {
        "query": query,
        "results": [
            {
                "standard": doc.metadata.get("standard"),
                "standard_name": doc.metadata.get("standard_name"),
                "paragraph": doc.metadata.get("paragraph"),
                "text": doc.page_content,
                "source_file": doc.metadata.get("source_file"),
                "score": float(1 - score),
            }
            for doc, score in docs
        ]
    }

@mcp.tool()
def get_standard_by_number(standard: str, paragraph: Optional[str] = None) -> dict:
    """Direct lookup of a K-IFRS standard by number and optional paragraph.

    Use this when the user specifies an exact location (e.g., "K-IFRS 1115 paragraph BC31").
    Bypasses semantic search and always returns the precise text.

    Args:
        standard: Standard number. Accepts variations: "K-IFRS 1115", "1115", "KIFRS1115".
        paragraph: Paragraph number (e.g., "BC31").
                   If None, returns the table of contents/overview for the standard.

    Returns:
        With paragraph:
        {
            "standard": "K-IFRS 1115",
            "standard_name": "고객과의 계약에서 생기는 수익",
            "paragraph": "BC31",
            "text": "기업은 고객에게 약속한 재화나 용역...",
            "source_file": "K-IFRS_1115_수익.pdf"
        }
        Without paragraph:
        {
            "standard": "K-IFRS 1115",
            "standard_name": "고객과의 계약에서 생기는 수익",
            "toc": [
                {"section": "목적", "paragraphs": "BC1"},
                {"section": "적용범위", "paragraphs": "BC5~8"},
                ...
            ]
        }
    """

if __name__ == "__main__":
    mcp.run(transport="stdio")
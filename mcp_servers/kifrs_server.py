from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv 
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from mcp.server.fastmcp import FastMCP

import os
import sys

from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
import json
import time


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")





BASE_DIR = Path(__file__).resolve().parent.parent


class TrackedFastMCP(FastMCP):
    def __init__(self, *args, stats_path: Path, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats_path = stats_path
        self.tool_counts = Counter()
        self._stats_lock = asyncio.Lock()

    async def call_tool(self, name: str, arguments: dict):
        started = time.perf_counter()
        success = False

        try:
            result = await super().call_tool(name, arguments)
            success = True
            return result

        finally:
            elapsed_ms = round(
                (time.perf_counter() - started) * 1000,
                1,
            )

            async with self._stats_lock:
                self.tool_counts[name] += 1

                record = {
                    "timestamp": datetime.now(
                        ZoneInfo("Asia/Seoul")
                    ).isoformat(),
                    "server": "kifrs",
                    "tool": name,
                    "count": self.tool_counts[name],
                    "success": success,
                    "elapsed_ms": elapsed_ms,
                }

                self.stats_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                with self.stats_path.open(
                    "a",
                    encoding="utf-8",
                ) as file:
                    file.write(
                        json.dumps(
                            record,
                            ensure_ascii=False,
                        ) + "\n"
                    )


mcp = TrackedFastMCP(
    "KifrsRAG",
    stats_path=BASE_DIR / "results" / "kifrs_tool_calls.jsonl",
)

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


CALL_COUNT = 0


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
    global CALL_COUNT
    CALL_COUNT += 1

    print(
        f"[search_kifrs #{CALL_COUNT}] query={query}",
        file=sys.stderr,
        flush=True,
    )

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
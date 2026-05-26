from __future__ import annotations

import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .graph import build_graph
from .models import CopilotRequest, CopilotResponse


BASE_DIR = Path(__file__).resolve().parent.parent
MCP_SERVERS_DIR = BASE_DIR / "mcp_servers"

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:        
        dart_params = StdioServerParameters(
            command=sys.executable,
            args=[str(MCP_SERVERS_DIR / "dart_server.py")],
        )
        dart_read, dart_write = await stack.enter_async_context(
            stdio_client(dart_params)
        )
        dart_session = await stack.enter_async_context(
            ClientSession(dart_read, dart_write)
        )
        await dart_session.initialize()
        dart_tools = await load_mcp_tools(dart_session)

        kifrs_params = StdioServerParameters(
            command=sys.executable,
            args=[str(MCP_SERVERS_DIR / "kifrs_server.py")],
        )
        kifrs_read, kifrs_write = await stack.enter_async_context(
            stdio_client(kifrs_params)
        )
        kifrs_session = await stack.enter_async_context(
            ClientSession(kifrs_read, kifrs_write)
        )
        await kifrs_session.initialize()
        kifrs_tools = await load_mcp_tools(kifrs_session)

        app.state.graph = build_graph(dart_tools, kifrs_tools)

        yield

app = FastAPI(
    title="DART Insight Copilot",
    description="OpenDART 공시 데이터 + K-IFRS 회계기준을 결합한 multi-agent 분석 시스템",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """For Health Check."""
    return {"status": "ok", "service": "DART Insight Copilot"}


@app.post("/api/dart/query", response_model=CopilotResponse)
async def dart_query(payload: CopilotRequest):
    """Return a response in Korean after analyzing natural language query with the multi agent.
    
    Stream:
    1. Supervisor analyzes query → select next workers
    2. selected workers call MCP tools and fetch data/document
    3. Supervisor aggregates the result of workers and summarize in Korean memo.
    """
    try:
        result = await app.state.graph.ainvoke({
            "messages": [{"role": "user", "content": payload.question}]
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 실패: {e}")
    
    messages = result.get("messages", [])
    final_msg = messages[-1].content if messages else ""
    
    return CopilotResponse(
        answer=final_msg,
        citations=[],  # W4·W5에 K-IFRS agent 결과에서 추출하도록 확장
        error=None,
    )
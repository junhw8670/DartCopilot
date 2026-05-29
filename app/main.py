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
from .models import CopilotRequest, CopilotResponse, Citation
import json

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


def _extract_citations(messages) -> list[Citation]:
    """Pull K-IFRS and OpenDART citations from LangGraph tool messages."""
    citations: list[Citation] = []
    seen: set[tuple] = set()

    def _add(key: tuple, cit: Citation) -> None:
        """A helper that adds without duplicates."""
        if key not in seen:
            seen.add(key)
            citations.append(cit)

    for m in messages:
        tool_name = getattr(m, "name", None)
        if not tool_name:
            continue
        try:
            payload = json.loads(m.content) if isinstance(m.content, str) else m.content
        except (json.JSONDecodeError, TypeError):
            continue
        
        if tool_name == "search_kifrs":
            for r in payload.get("results", []):
                std = r.get("standard")
                para = r.get("paragraph")
                _add(
                    ("kifrs", std, para),
                    Citation(
                        source="K-IFRS",
                        label=f"{std or ''} 문단 {para or ''}".strip(),
                        standard=std,
                        standard_name=r.get("standard_name"),
                        paragraph=para,
                        source_file=r.get("source_file"),
                    ),
                )
        elif tool_name in {"list_disclosures", "fetch_amendments"}:
            items = payload.get("list") or payload.get("amendments") or []
            for d in items:
                rno = d.get("rcept_no")
                if rno:
                    _add(
                    ("dart", rno),
                    Citation(
                        source="OpenDART",
                        label=f"{d.get('corp_name') or ''} {d.get('report_nm') or ''}".strip(),
                        rcept_no=rno,
                        corp_name=d.get("corp_name"),
                        report_nm=d.get("report_nm")
                    ),
                )

        
        elif tool_name in {"fetch_report", "fetch_amendment_details"}:
            rno = payload.get("rcept_no")
            if rno:
                _add(
                    ("dart", rno),
                    Citation(
                        source="OpenDART",
                        label=f"공시 원문 ({rno})",
                        rcept_no=rno,
                    ),
                )

        elif tool_name == "parse_business_report_xml":
            corp = payload.get("company_name")
            report = payload.get("report_name")
            period = f"{payload.get('period_from', '')}~{payload.get('period_to', '')}"
            if corp:
                _add(
                    ("dart_parse", corp, period),
                    Citation(
                        source="OpenDART",
                        label=f"{corp} {report or ''} ({period})".strip(),
                        corp_name=corp,
                        report_nm=report,
                    ),
                )

    return citations


@app.post("/api/dart/query", response_model=CopilotResponse)
async def dart_query(payload: CopilotRequest):
    """Return a response in Korean after analyzing natural language query with the multi agent.
    
    Stream:
    1. Supervisor analyzes query → select next workers
    2. selected workers call MCP tools and fetch data/document
    3. Supervisor aggregates the result of workers and summarize in Korean memo.
    """
    messages_in = payload.history + [
        {"role": "user", "content": payload.question}
    ]
    try:
        result = await app.state.graph.ainvoke({
            "messages": messages_in})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 실패: {e}")
    
    messages = result.get("messages", [])
    final_msg = messages[-1].content if messages else ""
    
    return CopilotResponse(
        answer=final_msg,
        citations=_extract_citations(messages),  # W4·W5에 K-IFRS agent 결과에서 추출하도록 확장
        error=None,
    )


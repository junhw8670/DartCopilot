from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from .graph import graph
from .models import CopilotRequest, CopilotResponse


BASE_DIR = Path(__file__).resolve().parent.parent


app = FastAPI(
    title="DART Insight Copilot",
    description="OpenDART 공시 데이터 + K-IFRS 회계기준을 결합한 multi-agent 분석 시스템",
)


@app.get("/")
async def root():
    """헬스 체크용 루트 엔드포인트."""
    return {"status": "ok", "service": "DART Insight Copilot"}


@app.post("/api/dart/query", response_model=CopilotResponse)
async def dart_query(payload: CopilotRequest):
    """자연어 질문을 받아 multi-agent로 분석하고 한국어 메모 반환.
    
    내부 흐름:
    1. Supervisor가 질문 분석 → 호출할 worker agent 결정
    2. 선택된 agents가 MCP 도구(DART API·K-IFRS RAG) 호출
    3. Supervisor가 결과 종합 → K-IFRS 인용 포함 한국어 메모
    """
    try:
        result = graph.invoke({
            "messages": [{"role": "user", "content": payload.question}]
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 실패: {e}")
    
    # create_supervisor 표준: result["messages"][-1].content가 최종 답변
    messages = result.get("messages", [])
    final_msg = messages[-1].content if messages else ""
    
    return CopilotResponse(
        answer=final_msg,
        citations=[],  # W4·W5에 K-IFRS agent 결과에서 추출하도록 확장
        error=None,
    )
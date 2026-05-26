from __future__ import annotations

from typing import Sequence

from langchain.agents import create_agent
from langgraph_supervisor import create_supervisor
from langchain_core.tools import BaseTool

from .llm_utils import get_llm

model = get_llm()

def _pick(tools_by_name: dict[str, BaseTool], names: Sequence[str]) -> list[BaseTool]:
    """Pick tools matching the given name list and return in list."""
    missing = [n for n in names if n not in tools_by_name]
    if missing:
        raise RuntimeError(f"{missing} missing in MCP server.")
    return [tools_by_name[n] for n in names]

def build_graph(dart_tools: list[BaseTool], kifrs_tools: list[BaseTool],):
    """Compile and return supervisor graph and 6 worker agents.

    Args:
        dart_tools: @mcp.tool() of dart_server.py fetched by load_mcp_tools(dart_session). LangChain BaseTool subject list.
        kifrs_tools: @mcp.tool() of kifrs_server.py fetched by load_mcp_tools(kifrs_session). LangChain BaseTool subject list.

    Returns:
        Compiled graph that can be executed by graph.ainvoke({"messages": [...]}).
    """
    dart_by_name = {t.name: t for t in dart_tools}
    kifrs_by_name = {t.name: t for t in kifrs_tools}


    business_report_agent = create_agent(
        model=model,
        tools=_pick(dart_by_name, ["search_company", "list_disclosures", "fetch_report", "parse_business_report_xml",]),
        name="business_report_expert",
        system_prompt=(
            "You are a Korean business report (사업보고서) summarization expert."
            "Use the tools to fetch and parse the XML report, then summarize sections."
        ),
    )

    ratio_agent = create_agent(
        model=model,
        tools=_pick(dart_by_name, ["search_company", "fetch_financial",]),
        name="ratio_expert",
        system_prompt=(
            "You are a financial ratio analysis expert for a single company at a single point in time."
            "Calculate ratios for stability (debt/equity, current ratio), profitability (ROE, ROA, operating margin), activity (asset turnover), and growth."
        ),
    )

    peer_agent = create_agent(
        model=model,
        tools=_pick(dart_by_name, ["search_company", "fetch_peers", "fetch_multi_company",]),
        name="peer_expert",
        system_prompt=(
            "You are an industry peer comparison expert."
            "Use the same-industry-code peer list to compare key financial metrics across companies at the same point in time."
        ),
    )

    trend_agent = create_agent(
        model=model,
        tools=_pick(dart_by_name, ["search_company", "fetch_multi_years",]),
        name="trend_expert",
        system_prompt=(
            "You are a multi-year time-series trend analysis expert."
            "Analyze year-over-year changes, growth rates, and volatility for one company across multiple years."
        ),
    )

    amendment_agent = create_agent(
        model=model,
        tools=_pick(dart_by_name, ["search_company", "fetch_amendments", "diff_documents",]),
        name="amendment_expert",
        system_prompt=(
            "You are a Korean disclosure amendment(정정공시) analysis expert."
            "Identify amendments, compare before-and-after reports, and explain what has changed and why."
        ),
    )

    kifrs_agent = create_agent(
        model=model,
        tools=_pick(kifrs_by_name, ["search_kifrs"]),
        name="kifrs_expert",
        system_prompt=(
            "You are a K-IFRS (한국채택국제회계기준) standards search and citation expert. "
            "Always cite the source (standard number + paragraph number) in your answer. "
            "You can operate stand-alone without any company context."
        ),
    )

    supervisor = create_supervisor(
        [business_report_agent, ratio_agent, peer_agent, trend_agent, amendment_agent, kifrs_agent],
        model=model,
        prompt=(
            "You are a supervisor that coordinates multiple expert agents to build a comprehensive graph of a company's business report analysis."
            "Based on the user's request, dispatch tasks to the appropriate experts and integrate their outputs into a single Korean-language answer."
        ),
    )

    return supervisor.compile()


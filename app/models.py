from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

class CopilotRequest(BaseModel):
    """Natural language query from user to FastAPI"""
    question: str
    history: list[dict] = Field(default_factory=list)

class Citation(BaseModel):
    """A single citation backing the final answer (K-IFRS or OpenDART)."""
    source: str
    label: str
    standard: Optional[str] = None
    standard_name: Optional[str] = None
    paragraph: Optional[str] = None
    source_file: Optional[str] = None
    rcept_no: Optional[str] = None
    corp_name: Optional[str] = None
    report_nm: Optional[str] = None


class CopilotResponse(BaseModel):
    """Final korean response and metadata produced by the multi-agent graph."""
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    error: Optional[str] = None
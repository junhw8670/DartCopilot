from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

class CopilotRequest(BaseModel):
    """Natural language query from user to FastAPI"""
    question: str

class Citation(BaseModel):
    """A single K-IFRS citation supporting an item in the final answer."""
    standard: str
    standard_name: Optional[str] = None
    paragraph: Optional[str] = None
    source_file: Optional[str] = None
    score: Optional[float] = None


class CopilotResponse(BaseModel):
    """Final korean response and metadata produced by the multi-agent graph."""
    answer: str
    citations: list[dict] = Field(default_factory=list)
    error: Optional[str] = None
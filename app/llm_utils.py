from __future__ import annotations

import os
from typing import Optional

from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

def get_optional_llm() -> Optional[ChatOpenAI]:
    """
    Return an LLM client only when OPENAI_API_KEY is configured.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-5.4-2026-03-05")
    return ChatOpenAI(model=model, temperature=0.2)


def get_llm() -> ChatOpenAI:
    """
    Return an LLM client only when OPENAI_API_KEY is configured. Raise RuntimeError if no key.
    """
    llm = get_optional_llm()
    if llm is None:
        raise RuntimeError("OPENAI_API_KEY가 .env에 설정되어 있어야 합니다.")
    return llm
    
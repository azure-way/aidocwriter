from __future__ import annotations

from typing import Dict, Any

from .config import get_settings
from .llm import LLMClient, LLMMessage


class Summarizer:
    def __init__(self, llm: LLMClient | None = None):
        self.settings = get_settings()
        self.llm = llm or LLMClient(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            api_version=self.settings.reviewer_api_version or self.settings.openai_api_version,
            use_responses=self.settings.reviewer_use_responses,
        )

    def summarize_section(self, markdown: str) -> str:
        sys = (
            "You are a precise summarizer. Extract 5-10 bullet key facts/definitions from the text."
            " Be terse and faithful; no new claims. Output plain bullets."
        )
        content = self.llm.chat(
            model=self.settings.reviewer_model,
            messages=[
                LLMMessage("system", sys),
                LLMMessage("user", markdown),
            ],
        )
        return content if isinstance(content, str) else ""

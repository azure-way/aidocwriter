from __future__ import annotations

from ..config import get_settings
from ..llm import LLMClient, LLMMessage


class CohesionReviewerAgent:
    def __init__(self, llm: LLMClient | None = None):
        self.settings = get_settings()
        self.llm = llm or LLMClient(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            api_version=self.settings.reviewer_api_version or self.settings.openai_api_version,
            use_responses=self.settings.reviewer_use_responses,
        )

    def review_cohesion(self, plan: dict, markdown: str) -> str:
        sys = (
            "You are a cohesion editor. Assess flow, transitions, cross-references, and section alignment."
            " Provide JSON with keys: issues (list), suggestions (list)."
        )
        content = self.llm.chat(
            model=self.settings.reviewer_model,
            messages=[
                LLMMessage("system", sys),
                LLMMessage("user", f"Outline: {plan.get('outline', [])}"),
                LLMMessage("user", markdown),
            ],
        )
        return content if isinstance(content, str) else "{}"

    def review_cohesion_batch(self, plan: dict, markdown: str, sections: list[dict]) -> str:
        sys = (
            "You are a cohesion editor. Assess flow, transitions, cross-references, and alignment for each section independently."
            " Return per-section findings."
        )
        guide = (
            "Return JSON with key 'sections' (array). Each item: {section_id, issues: [], suggestions: []}."
        )
        content = self.llm.chat(
            model=self.settings.reviewer_model,
            messages=[
                LLMMessage("system", sys),
                LLMMessage("user", f"Outline: {plan.get('outline', [])}"),
                LLMMessage("user", f"Target sections: {', '.join([str(s.get('section_id')) for s in sections])}"),
                LLMMessage("user", markdown),
                LLMMessage("user", guide),
            ],
        )
        return content if isinstance(content, str) else "{}"

from __future__ import annotations

from ..config import get_settings
from ..llm import LLMClient, LLMMessage


class StyleReviewerAgent:
    def __init__(self, llm: LLMClient | None = None):
        self.settings = get_settings()
        self.llm = llm or LLMClient(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            api_version=self.settings.reviewer_api_version or self.settings.openai_api_version,
            use_responses=self.settings.reviewer_use_responses,
        )

    def review_style(self, plan: dict, markdown: str) -> str:
        sys = (
            "You are a style editor. Assess clarity, tone, readability, and consistency."
            " Provide JSON with keys: issues (list), suggestions (list), revised_snippets (optional)."
        )
        content = self.llm.chat(
            model=self.settings.reviewer_model,
            messages=[
                LLMMessage("system", sys),
                LLMMessage("user", f"Plan style: {plan.get('global_style', {})}"),
                LLMMessage("user", markdown),
            ],
        )
        return content if isinstance(content, str) else "{}"

    def review_style_batch(self, plan: dict, markdown: str, sections: list[dict]) -> str:
        sys = (
            "You are a style editor. Assess clarity, tone, readability, and consistency for each section independently."
            " Return per-section feedback."
        )
        guide = (
            "Return JSON with key 'sections' (array). Each item: {section_id, issues: [], suggestions: [], revised_snippets (optional)}."
            " revised_snippets may include markdown fragments; if you include section markers, preserve them exactly."
        )
        content = self.llm.chat(
            model=self.settings.reviewer_model,
            messages=[
                LLMMessage("system", sys),
                LLMMessage("user", f"Plan style: {plan.get('global_style', {})}"),
                LLMMessage("user", f"Target sections: {', '.join([str(s.get('section_id')) for s in sections])}"),
                LLMMessage("user", markdown),
                LLMMessage("user", guide),
            ],
        )
        return content if isinstance(content, str) else "{}"

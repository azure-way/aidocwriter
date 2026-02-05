from __future__ import annotations

from typing import Any, Dict

from ..config import get_settings
from ..llm import LLMClient, LLMMessage


class ReviewerAgent:
    def __init__(self, llm: LLMClient | None = None):
        self.settings = get_settings()
        self.llm = llm or LLMClient(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            api_version=self.settings.reviewer_api_version or self.settings.openai_api_version,
            use_responses=self.settings.reviewer_use_responses,
        )

    def review(self, plan: Dict[str, Any], draft_markdown: str) -> str:
        sys = (
            "You are a critical reviewer. Check for contradictions, inconsistencies, missing definitions,"
            " and propose a revised draft."
        )
        guide = (
            "Return JSON with keys: findings, suggested_changes, revised_markdown."
            " Keep revised_markdown as a coherent full document."
            " IMPORTANT: Preserve any section markers of the form '<!-- SECTION:ID:START -->' and '<!-- SECTION:ID:END -->'"
            " exactly as they are; do not remove, rename, or alter them."
        )
        plan_summary = str({k: plan.get(k) for k in ["title", "audience", "glossary", "global_style"]})
        content = self.llm.chat(
            model=self.settings.reviewer_model,
            messages=[
                LLMMessage("system", sys),
                LLMMessage("user", f"Plan: {plan_summary}"),
                LLMMessage("user", f"Draft Markdown begins:\n{draft_markdown}"),
                LLMMessage("user", guide),
            ],
        )
        if isinstance(content, str):
            return content
        return "{}"

    def review_batch(self, plan: Dict[str, Any], markdown: str, sections: list[Dict[str, Any]]) -> str:
        sys = (
            "You are a critical reviewer. Check for contradictions, inconsistencies, missing definitions,"
            " and propose revisions for each section independently."
        )
        guide = (
            "Return JSON with keys: sections (array of objects) and overall_notes (optional)."
            " Each sections item: {section_id, findings: [], suggested_changes: [], revised_markdown: string}."
            " revised_markdown should include only the sections you adjusted, preserving any markers"
            " like '<!-- SECTION:ID:START -->' and '<!-- SECTION:ID:END -->'."
        )
        sections_summary = ", ".join([str(s.get("section_id")) for s in sections]) if sections else ""
        plan_summary = str({k: plan.get(k) for k in ["title", "audience", "glossary", "global_style"]})
        content = self.llm.chat(
            model=self.settings.reviewer_model,
            messages=[
                LLMMessage("system", sys),
                LLMMessage("user", f"Plan: {plan_summary}"),
                LLMMessage("user", f"Target sections: {sections_summary}"),
                LLMMessage("user", f"Draft Markdown begins:\\n{markdown}"),
                LLMMessage("user", guide),
            ],
        )
        return content if isinstance(content, str) else "{}"

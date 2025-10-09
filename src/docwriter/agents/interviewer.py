from __future__ import annotations

import json
from typing import Any, Dict, List

from ..config import get_settings
from ..llm import LLMClient, LLMMessage


DEFAULT_QUESTIONS: List[Dict[str, Any]] = [
    {"id": "audience", "q": "Who is the primary audience? (roles, seniority, background)"},
    {"id": "goals", "q": "What are the main goals of this document?"},
    {"id": "non_goals", "q": "What is explicitly out of scope?"},
    {"id": "constraints", "q": "Any constraints (tech stack, compliance, budget, timeline)?"},
    {"id": "tone", "q": "Preferred tone (formal, pragmatic, tutorial, RFC-like)?"},
    {"id": "pov", "q": "Point of view (1st person plural, neutral, instructive)?"},
    {"id": "structure", "q": "Any structure preferences (chapters, case studies, appendices)?"},
    {"id": "must_cover", "q": "Mandatory topics/keywords to cover?"},
    {"id": "must_avoid", "q": "Topics to avoid?"},
    {"id": "references", "q": "Links or references the doc should align with?"},
    {"id": "diagrams", "q": "Which diagrams are needed (types, key entities/flows)?"},
    {"id": "context", "q": "Company/product context that must be reflected?"},
]


class InterviewerAgent:
    def __init__(self, llm: LLMClient | None = None):
        self.settings = get_settings()
        self.llm = llm or LLMClient(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            api_version=self.settings.planner_api_version or self.settings.openai_api_version,
            use_responses=self.settings.planner_use_responses,
        )

    def propose_questions(self, title: str) -> List[Dict[str, Any]]:
        """Propose an expanded, prioritized question list based on the title.

        Returns a list of {id, q}.
        """
        try:
            sys = (
                "You are a documentation scoping expert. Given a working title, propose a concise"
                " questionnaire to collect everything needed to produce a long, high-quality, consistent"
                " technical document."
            )
            guide = (
                "Return ONLY JSON list of {id, q}. Include audience, goals, constraints, tone, pov,"
                " structure, must_cover, must_avoid, references, diagrams, context, and any other critical items."
            )
            out = self.llm.chat(
                model=self.settings.planner_model,
                messages=[
                    LLMMessage("system", sys),
                    LLMMessage("user", f"Title: {title}"),
                    LLMMessage("user", guide),
                ],
            )
            if isinstance(out, str):
                data = json.loads(out)
                if isinstance(data, list) and data:
                    return data
        except Exception:
            pass
        return DEFAULT_QUESTIONS

    def propose_followups(self, title: str, answers: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Propose follow-up questions to close gaps based on answers."""
        try:
            sys = "You identify missing details for documentation planning and writing."
            guide = (
                "Return ONLY JSON list of {id, q}. Ask for gaps, ambiguous items, or needed specifics."
                " Do not repeat already answered items unless clarification is needed."
            )
            out = self.llm.chat(
                model=self.settings.planner_model,
                messages=[
                    LLMMessage("system", sys),
                    LLMMessage("user", f"Title: {title}"),
                    LLMMessage("user", f"Answers so far (JSON):\n{json.dumps(answers)}"),
                    LLMMessage("user", guide),
                ],
            )
            if isinstance(out, str):
                data = json.loads(out)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

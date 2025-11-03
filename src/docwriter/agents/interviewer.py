from __future__ import annotations

import json
from typing import Any, Dict, List

from ..config import get_settings
from ..llm import LLMClient, LLMMessage


DEFAULT_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "audience",
        "q": "Who is the primary audience? (roles, seniority, background)",
        "sample": "Enterprise integration architects and senior platform engineers overseeing Azure integration projects.",
    },
    {
        "id": "goals",
        "q": "What are the main goals of this document?",
        "sample": "Provide integration design patterns, implementation guidance, and governance practices for Azure-based asynchronous/synchronous workloads.",
    },
    {
        "id": "non_goals",
        "q": "What is explicitly out of scope?",
        "sample": "Detailed language-specific coding tutorials or walkthroughs for on-prem middleware migrations.",
    },
    {
        "id": "constraints",
        "q": "Any constraints (tech stack, compliance, budget, timeline)?",
        "sample": "Must align with the Azure Well-Architected Framework, support global scale, and meet strict latency/SLA requirements.",
    },
    {
        "id": "tone",
        "q": "Preferred tone (formal, pragmatic, tutorial, RFC-like)?",
        "sample": "Authoritative, pragmatic, and executive-ready.",
    },
    {
        "id": "pov",
        "q": "Point of view (1st person plural, neutral, instructive)?",
        "sample": "Neutral advisory viewpoint with platform-owner recommendations.",
    },
    {
        "id": "structure",
        "q": "Any structure preferences (chapters, case studies, appendices)?",
        "sample": "Executive summary, pattern overview, async patterns, sync patterns, hybrid orchestration, observability, case studies, appendices.",
    },
    {
        "id": "must_cover",
        "q": "Mandatory topics/keywords to cover?",
        "sample": "Azure Service Bus, Event Grid, Logic Apps, API Management, retry policies, idempotency, back-pressure handling, monitoring.",
    },
    {
        "id": "must_avoid",
        "q": "Topics to avoid?",
        "sample": "Vendor-specific marketing claims or legacy-only middleware deep dives beyond coexistence notes.",
    },
    {
        "id": "references",
        "q": "Links or references the doc should align with?",
        "sample": "Microsoft Learn integration services documentation, Azure Architecture Center integration patterns.",
    },
    {
        "id": "diagrams",
        "q": "Which diagrams are needed (types, key entities/flows)?",
        "sample": "High-level architecture showing async vs sync integrations plus a sequence diagram illustrating request-to-event choreography.",
    },
    {
        "id": "context",
        "q": "Company/product context that must be reflected?",
        "sample": "Global retail enterprise modernizing POS integrations while integrating with ERP, CRM, and analytics systems.",
    },
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

        Returns a list of {id, q, sample}.
        """
        try:
            sys = (
                "You are a documentation scoping expert. Given a working title, propose a concise"
                " questionnaire to collect everything needed to produce a long, high-quality, consistent"
                " technical document."
            )
            guide = (
                "Return ONLY JSON list of objects {id, q, sample}. Ensure sample is a concise default answer."
                " Include questions for audience, goals, constraints, tone, pov, structure, must_cover, must_avoid, references, diagrams, context,"
                " and any other key details needed to plan a 60+ page technical document."
                " You MUST return maximum 12 questions. Prioritize the most critical ones. you MUST be concise and to the point."
                f" Below you can find some example questions to help you: {json.dumps(DEFAULT_QUESTIONS)}"
            )
            out = self.llm.chat(
                model=self.settings.planner_model,
                messages=[
                    LLMMessage("system", sys),
                    LLMMessage("user", f"Title of the document: {title}"),
                    LLMMessage("user", guide),
                ],
            )
            if isinstance(out, str):
                data = json.loads(out)
                if isinstance(data, list) and data:
                    return self._normalize_questions(data)
        except Exception:
            self.llm.last_usage = {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            }
            return self._normalize_questions(DEFAULT_QUESTIONS)
        self.llm.last_usage = {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }
        return self._normalize_questions(DEFAULT_QUESTIONS)

    def propose_followups(self, title: str, answers: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Propose follow-up questions to close gaps based on answers."""
        try:
            sys = "You identify missing details for documentation planning and writing."
            guide = (
                "Return ONLY JSON list of {id, q}. Ask for gaps, ambiguous items, or needed specifics."
                " Do not repeat already answered items unless clarification is needed."
                "If there is a question about diagrams, you must answer in terms of PlantUML diagrams (actors, participants, relationships)."
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
            self.llm.last_usage = {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            }
            return []
        self.llm.last_usage = {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }
        return []

    def _normalize_questions(self, raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            q_id = str(item.get("id") or f"q{idx+1}")
            question = str(item.get("q") or item.get("question") or "")
            if not question:
                continue
            sample = item.get("sample") or item.get("sample_answer") or item.get("example") or ""
            normalized.append({"id": q_id, "q": question, "sample": str(sample)})
        return normalized

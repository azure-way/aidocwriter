from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any, Iterator, Optional

from ..config import get_settings
from ..llm import LLMClient, LLMMessage


@dataclass
class SectionDraft:
    section_id: str
    title: str
    markdown: str


class WriterAgent:
    def __init__(self, llm: LLMClient | None = None):
        self.settings = get_settings()
        self.llm = llm or LLMClient(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            api_version=self.settings.writer_api_version or self.settings.openai_api_version,
            use_responses=self.settings.writer_use_responses,
        )

    def write_section(
        self,
        plan: Dict[str, Any],
        section: Dict[str, Any],
        dependency_context: Optional[str] = None,
        extra_guidance: Optional[str] = None,
    ) -> Iterator[str]:
        sys = (
            "You are a disciplined technical writer. Write Markdown that strictly adheres to the provided"
            " plan, maintains global consistency, and embeds PlantUML diagrams where requested."
        )
        style = plan.get("global_style", {})
        glossary = plan.get("glossary", {})
        diagram_specs = plan.get("diagram_specs", [])

        section_diagrams = [d for d in diagram_specs if d.get("section_id") == section.get("id")]

        guide = (
            f"Global style: {style}\n"
            f"Glossary: {glossary}\n"
            f"Section: {section}\n"
            f"Diagrams: {section_diagrams}\n"
            f"Dependency context (key facts to respect): {dependency_context or 'N/A'}\n"
            "Rules:\n- Use consistent terminology from the glossary.\n"
            "- Be concise but thorough; prefer clear subsections and lists.\n"
            "- For each diagram spec, produce exactly one ```plantuml``` code block.\n"
            "- The first non-blank line inside every PlantUML block must be a single-quote comment"
            " containing \"diagram_id: <diagram_id>\" for the matching spec.\n"
            "- Ensure that labels/fields/descriptions in diagrams have the escaped new line characters (\\n). For example: wrong: RECTANGLE Dynamics365Sales <<Azure>> as Dynamics 365 \n Sales, correct: RECTANGLE Dynamics365Sales <<Azure>> as Dynamics 365 \\n Sales\n"
            "- Use the plantuml_prompt or description to choose actors, lifelines, and relationships.\n"
        )
        if extra_guidance:
            guide += (
                "- Apply the following revision guidance (adjust prose accordingly; do not copy these notes verbatim):\n"
                f"{extra_guidance}\n"
            )

        if self.settings.streaming:
            sid = str(section.get("id"))
            yield f"<!-- SECTION:{sid}:START -->\n"
            for c in self.llm.chat_stream(
                model=self.settings.writer_model,
                messages=[LLMMessage("system", sys), LLMMessage("user", guide)],
            ):
                yield c
            yield f"\n<!-- SECTION:{sid}:END -->\n"
        else:
            text = self.llm.chat(
                model=self.settings.writer_model,
                messages=[LLMMessage("system", sys), LLMMessage("user", guide)],
            )
            sid = str(section.get("id"))
            yield f"<!-- SECTION:{sid}:START -->\n" + text + f"\n<!-- SECTION:{sid}:END -->\n"

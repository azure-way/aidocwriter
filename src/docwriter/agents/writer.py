from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any, Iterator, Optional

from ..config import get_settings
from ..llm import LLMClient, LLMMessage
from ..plantuml_reference import PLANTUML_REFERENCE_TEXT


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
            " Avoid filler, fluff, hedging, and throat-clearing."
            " Be concise but not telegraphic. Use short-to-medium sentences; lead with the point."
            " Use bullets and tables when they improve clarity; allow brief narrative paragraphs."
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
            "- Start the section with a 1-2 sentence summary.\n"
            "- Paragraphs: max 6 sentences. Prefer <= 26 words per sentence.\n"
            "- Use bullets for lists; no nested bullets.\n"
            "- Avoid overusing phrases: \"in order to\", \"it is important to note\", \"clearly\", \"very\", \"robust\", \"leveraging\".\n"
            "- For each diagram spec, produce exactly one ```plantuml``` code block.\n"
            "- The first non-blank line inside every PlantUML block must be a single-quote comment"
            " containing \"diagram_id: <diagram_id>\" for the matching spec.\n"
            "- Inside every PlantUML block include exactly one @startuml and one @enduml; do not wrap the block in Markdown fences other than ```plantuml.\n"
            "- Keep all labels and element names on a single line; use explicit \\n escapes instead of real line breaks.\n"
            "- Do not emit Mermaid, HTML, or Markdown inside PlantUML; stay within valid PlantUML grammar only.\n"
            "- Use the plantuml_prompt or description to choose actors, lifelines, relationships, and to pick a valid PlantUML diagram type from the reference.\n"
            "- Only emit PlantUML syntax that matches the supported patterns below (ignore unsupported formats).\n"
            "Good example:\n```plantuml\n' diagram_id: diag-1\n@startuml\nactor User\nUser -> API : Request\nAPI --> User : Response\n@enduml\n```\n"
            "Bad example (do not do this):\n```plantuml\n@startuml\n```mermaid\nflowchart LR\n@enduml\n```\n"
            f"Supported PlantUML reference:\n{PLANTUML_REFERENCE_TEXT}\n"
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

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from ..config import get_settings
from ..llm import LLMClient, LLMMessage


logger = logging.getLogger(__name__)


@dataclass
class Plan:
    title: str
    audience: str
    length_pages: int
    outline: List[Dict[str, Any]]
    glossary: Dict[str, str]
    global_style: Dict[str, Any]
    diagram_specs: List[Dict[str, Any]]


class PlannerAgent:
    def __init__(self, llm: LLMClient | None = None):
        self.settings = get_settings()
        self.llm = llm or LLMClient(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            api_version=self.settings.planner_api_version or self.settings.openai_api_version,
            use_responses=self.settings.planner_use_responses,
        )
        logger.debug("PlannerAgent initialized with model %s", self.settings.planner_model)

    def plan(self, title: str, audience: str, length_pages: int) -> Plan:
        logger.debug(
            "Planner starting",
            extra={"title": title, "audience": audience, "length_pages": length_pages},
        )
        sys = (
            "You are a meticulous planning agent. Produce a JSON plan for a long, consistent,"
            " markdown document with sections, objectives, constraints, glossary, and mermaid diagram specs."
            " Keep it compact but complete."
        )
        user = f"Title: {title}\nAudience: {audience}\nTarget length pages: {length_pages}"

        prompt = (
            "Respond ONLY with JSON having keys: title, audience, length_pages, outline, glossary,"
            " global_style, diagram_specs.\n"
            "- outline: list of sections {id, title, goals, key_points, dependencies}\n"
            "- glossary: {term: definition}\n"
            "- global_style: {tone, pov, formatting_rules}\n"
            "- diagram_specs: list of {section_id, type, mermaid_goal, entities, relationships}\n"
        )

        prompt = (
            "Respond ONLY with JSON having keys: title, audience, length_pages, outline, glossary,"
            " global_style, diagram_specs.\n"
            "- outline: list of sections {id, title, goals, key_points, dependencies}\n"
            "- glossary: {term: definition}\n"
            "- global_style: {tone, pov, formatting_rules}\n"
            "- diagram_specs: list of {section_id, type, mermaid_goal, entities, relationships}\n"
        )

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "DocPlan",
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "audience": {"type": "string"},
                        "length_pages": {"type": "integer"},
                        "outline": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "goals": {"type": "array", "items": {"type": "string"}},
                                    "key_points": {"type": "array", "items": {"type": "string"}},
                                    "dependencies": {"type": "array", "items": {"type": "string"}},
                                },
                                "required": ["id", "title"],
                            },
                        },
                        "glossary": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "global_style": {
                            "type": "object",
                            "properties": {
                                "tone": {"type": "string"},
                                "pov": {"type": "string"},
                                "formatting_rules": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                        "diagram_specs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "section_id": {"type": "string"},
                                    "type": {"type": "string"},
                                    "mermaid_goal": {"type": "string"},
                                    "entities": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "relationships": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["section_id", "type"],
                            },
                        },
                    },
                    "required": [
                        "title",
                        "audience",
                        "length_pages",
                        "outline",
                        "glossary",
                        "global_style",
                        "diagram_specs",
                    ],
                },
            },
        }

        try:
            content = self.llm.chat(
                model=self.settings.planner_model,
                messages=[
                    LLMMessage("system", sys),
                    LLMMessage("user", user),
                    LLMMessage("user", prompt),
                ],
                response_format=response_format if self.settings.planner_use_responses else None,
            )
        except Exception as exc:
            logger.exception("Planner LLM call failed for title '%s'", title)
            raise

        import json

        if isinstance(content, dict):
            data = content
        else:
            if not isinstance(content, str):
                logger.error(
                    "Planner expected string or dict response for title '%s' but received %s",
                    title,
                    type(content),
                )
                raise TypeError("Planner LLM response must be a string or dict")
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                logger.exception("Planner produced invalid JSON for title '%s': %s", title, content)
                raise


        logger.debug(
            "Planner completed",
            extra={"title": title, "outline_sections": len(data.get("outline", []))},
        )
        return Plan(
            title=data.get("title", title),
            audience=data.get("audience", audience),
            length_pages=int(data.get("length_pages", length_pages)),
            outline=data.get("outline", []),
            glossary=data.get("glossary", {}),
            global_style=data.get("global_style", {}),
            diagram_specs=data.get("diagram_specs", []),
        )

from __future__ import annotations

import json
from typing import Any, Dict

from ..config import get_settings
from ..llm import LLMClient, LLMMessage


class CoreCompanyProfileAgent:
    def __init__(self, llm: LLMClient | None = None):
        settings = get_settings()
        self.settings = settings
        self.llm = llm or LLMClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            api_version=settings.planner_api_version or settings.openai_api_version,
            use_responses=settings.planner_use_responses,
        )

    def extract(self, text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        sys = "You extract a company profile from source materials."
        guide = (
            "Return ONLY JSON with keys: company_name, overview, capabilities, industries, "
            "certifications, locations, references.\n"
            "- references: array of {title, summary, outcome, year}\n"
        )
        meta_text = json.dumps(metadata or {}, indent=2)
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "CompanyProfile",
                "schema": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string"},
                        "overview": {"type": "string"},
                        "capabilities": {"type": "array", "items": {"type": "string"}},
                        "industries": {"type": "array", "items": {"type": "string"}},
                        "certifications": {"type": "array", "items": {"type": "string"}},
                        "locations": {"type": "array", "items": {"type": "string"}},
                        "references": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "summary": {"type": "string"},
                                    "outcome": {"type": "string"},
                                    "year": {"type": "string"},
                                },
                                "required": ["title", "summary"],
                            },
                        },
                    },
                    "required": [
                        "company_name",
                        "overview",
                        "capabilities",
                        "industries",
                        "certifications",
                        "locations",
                        "references",
                    ],
                },
            },
        }
        content = self.llm.chat(
            model=self.settings.planner_model,
            messages=[
                LLMMessage("system", sys),
                LLMMessage("user", f"Metadata:\n{meta_text}"),
                LLMMessage("user", f"Company materials:\n{text}"),
                LLMMessage("user", guide),
            ],
            response_format=response_format if self.settings.planner_use_responses else None,
        )
        data = content if isinstance(content, dict) else self._parse_json(content)
        return self._normalize(data)

    @staticmethod
    def _parse_json(content: Any) -> Dict[str, Any]:
        if not isinstance(content, str):
            raise ValueError("Invalid company profile JSON")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid company profile JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("Invalid company profile JSON")
        return data

    @staticmethod
    def _normalize(data: Dict[str, Any]) -> Dict[str, Any]:
        def _list(value: Any) -> list[str]:
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
            if isinstance(value, str) and value.strip():
                return [value.strip()]
            return []

        references = []
        for item in data.get("references") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            summary = str(item.get("summary") or "").strip()
            if not title or not summary:
                continue
            references.append(
                {
                    "title": title,
                    "summary": summary,
                    "outcome": str(item.get("outcome") or "").strip(),
                    "year": str(item.get("year") or "").strip(),
                }
            )

        return {
            "company_name": str(data.get("company_name") or "").strip(),
            "overview": str(data.get("overview") or "").strip(),
            "capabilities": _list(data.get("capabilities")),
            "industries": _list(data.get("industries")),
            "certifications": _list(data.get("certifications")),
            "locations": _list(data.get("locations")),
            "references": references,
        }

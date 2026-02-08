from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..config import get_settings
from ..llm import LLMClient, LLMMessage


class CoreRfpAgent:
    def __init__(self, llm: LLMClient | None = None):
        settings = get_settings()
        self.settings = settings
        self.llm = llm or LLMClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            api_version=settings.planner_api_version or settings.openai_api_version,
            use_responses=settings.planner_use_responses,
        )

    def analyze(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        sys = (
            "You are an expert proposal analyst. Analyze the RFP content, infer title and audience,"
            " extract precise requirements, and propose clarification questions only when needed."
        )
        guide = (
            "Return ONLY JSON with keys: title, audience, summary, requirements, questions.\n"
            "- requirements: array of {id, text, priority, section_ref}\n"
            "- id format must be 'RFP-REQ-###' with 1-based numbering.\n"
            "- questions: array of {id, q, sample}\n"
            "- ask up to 20 questions, only if needed to close gaps.\n"
        )
        meta_text = json.dumps(metadata or {}, indent=2)
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "RfpAnalysis",
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "audience": {"type": "string"},
                        "summary": {"type": "string"},
                        "requirements": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "text": {"type": "string"},
                                    "priority": {"type": "string"},
                                    "section_ref": {"type": "string"},
                                },
                                "required": ["text"],
                            },
                        },
                        "questions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "q": {"type": "string"},
                                    "sample": {"type": "string"},
                                },
                                "required": ["q"],
                            },
                        },
                    },
                    "required": ["summary", "requirements", "questions"],
                },
            },
        }
        content = self.llm.chat(
            model=self.settings.planner_model,
            messages=[
                LLMMessage("system", sys),
                LLMMessage("user", f"Metadata:\n{meta_text}"),
                LLMMessage("user", f"RFP text:\n{text}"),
                LLMMessage("user", guide),
            ],
            response_format=response_format if self.settings.planner_use_responses else None,
        )
        data = content if isinstance(content, dict) else self._parse_json(content)
        return self._normalize(data)

    @staticmethod
    def _parse_json(content: Any) -> Dict[str, Any]:
        if not isinstance(content, str):
            raise ValueError("Invalid RFP analysis JSON")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid RFP analysis JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("Invalid RFP analysis JSON")
        return data

    def _normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        requirements_raw = data.get("requirements") or []
        questions_raw = data.get("questions") or []
        requirements: List[Dict[str, Any]] = []
        req_counter = 1
        for item in requirements_raw:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            req_id = str(item.get("id") or "").strip()
            if not req_id.startswith("RFP-REQ-"):
                req_id = f"RFP-REQ-{req_counter:03d}"
            req_counter += 1
            normalized = {
                "id": req_id,
                "text": text,
            }
            if item.get("priority"):
                normalized["priority"] = str(item.get("priority"))
            if item.get("section_ref"):
                normalized["section_ref"] = str(item.get("section_ref"))
            requirements.append(normalized)

        questions: List[Dict[str, Any]] = []
        for idx, item in enumerate(questions_raw):
            if not isinstance(item, dict):
                continue
            q_text = str(item.get("q") or "").strip()
            if not q_text:
                continue
            q_id = str(item.get("id") or f"q{idx + 1}")
            sample = str(item.get("sample") or "")
            questions.append({"id": q_id, "q": q_text, "sample": sample})
        questions = questions[:20]

        return {
            "title": str(data.get("title") or "").strip(),
            "audience": str(data.get("audience") or "").strip(),
            "summary": str(data.get("summary") or "").strip(),
            "requirements": requirements,
            "questions": questions,
        }

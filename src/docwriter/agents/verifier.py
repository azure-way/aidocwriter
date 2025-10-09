from __future__ import annotations

import json
from typing import Dict

from ..config import get_settings
from ..llm import LLMClient, LLMMessage


class VerifierAgent:
    """Quick verifier focusing on contradictions between dependency summaries and final text.

    Returns JSON with keys: contradictions (list of {section_id, summary_bullet, location, snippet, explanation, fix}).
    """

    def __init__(self, llm: LLMClient | None = None):
        self.settings = get_settings()
        self.llm = llm or LLMClient(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            api_version=self.settings.reviewer_api_version or self.settings.openai_api_version,
            use_responses=self.settings.reviewer_use_responses,
        )

    def verify(self, dependency_summaries: Dict[str, str], final_markdown: str) -> str:
        sys = (
            "You are a precise verifier. Compare provided dependency summaries (bullet facts per section)"
            " against the final Markdown. Identify contradictions or violations of those facts."
        )
        guide = (
            "Respond ONLY with JSON: {\n"
            "  \"contradictions\": [\n"
            "    {\n"
            "      \"section_id\": str,\n"
            "      \"summary_bullet\": str,\n"
            "      \"location\": str,  // where in the doc (heading or line range)\n"
            "      \"snippet\": str,   // excerpt showing the issue\n"
            "      \"explanation\": str,\n"
            "      \"fix\": str       // minimal revision suggestion\n"
            "    }\n"
            "  ]\n"
            "}"
        )
        dep_json = json.dumps(dependency_summaries)
        content = self.llm.chat(
            model=self.settings.reviewer_model,
            messages=[
                LLMMessage("system", sys),
                LLMMessage("user", f"Dependency summaries per section (JSON):\n{dep_json}"),
                LLMMessage("user", f"Final document Markdown begins:\n{final_markdown}"),
                LLMMessage("user", guide),
            ],
        )
        return content if isinstance(content, str) else "{\"contradictions\": []}"

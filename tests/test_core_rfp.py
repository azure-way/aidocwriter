from __future__ import annotations

import json

from docwriter.agents.core_rfp import CoreRfpAgent


class FakeLLM:
    def __init__(self, payload: str):
        self.payload = payload

    def chat(self, model, messages, response_format=None):
        return self.payload


def test_core_rfp_normalizes_requirements_and_caps_questions():
    payload = json.dumps(
        {
            "title": "RFP for Managed Services",
            "audience": "Procurement team",
            "summary": "Seeking managed services.",
            "requirements": [
                {"text": "Provide 24/7 support."},
                {"id": "custom", "text": "Meet SLA targets."},
            ],
            "questions": [{"q": f"Question {i}", "sample": "Answer"} for i in range(25)],
        }
    )
    agent = CoreRfpAgent(llm=FakeLLM(payload))
    result = agent.analyze("RFP text")
    assert result["title"] == "RFP for Managed Services"
    assert result["audience"] == "Procurement team"
    assert len(result["requirements"]) == 2
    assert result["requirements"][0]["id"].startswith("RFP-REQ-")
    assert len(result["questions"]) == 20

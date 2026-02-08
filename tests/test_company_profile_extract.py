from __future__ import annotations

import json

from docwriter.agents.core_company_profile import CoreCompanyProfileAgent


class FakeLLM:
    def __init__(self, payload: str):
        self.payload = payload

    def chat(self, model, messages, response_format=None):
        return self.payload


def test_company_profile_extract_parses_payload():
    payload = json.dumps(
        {
            "company_name": "Acme Corp",
            "overview": "We deliver platforms.",
            "capabilities": ["Cloud", "Security"],
            "industries": ["Finance"],
            "certifications": ["ISO 27001"],
            "locations": ["NY"],
            "references": [
                {"title": "Project A", "summary": "Delivered platform", "outcome": "Success", "year": "2023"}
            ],
        }
    )
    agent = CoreCompanyProfileAgent(llm=FakeLLM(payload))
    profile = agent.extract("text")
    assert profile["company_name"] == "Acme Corp"
    assert profile["capabilities"] == ["Cloud", "Security"]
    assert profile["references"][0]["title"] == "Project A"

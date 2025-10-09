from __future__ import annotations

import json

from docwriter.agents.reviewer import ReviewerAgent


class FakeLLM:
    def chat(self, model, messages, stream=False):
        return json.dumps({
            "findings": ["No contradictions found"],
            "suggested_changes": [],
            "revised_markdown": "# Revised\nContent"
        })


def test_reviewer_returns_json():
    agent = ReviewerAgent(llm=FakeLLM())
    out = agent.review({"title": "X", "audience": "Y", "glossary": {}, "global_style": {}}, "# D")
    data = json.loads(out)
    assert "revised_markdown" in data


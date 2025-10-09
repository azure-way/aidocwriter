from __future__ import annotations

import json

from docwriter.agents.planner import PlannerAgent


class FakeLLM:
    def __init__(self, payload: str):
        self.payload = payload

    def chat(self, model, messages, stream=False):
        return self.payload


def test_planner_returns_structured_plan():
    payload = json.dumps(
        {
            "title": "Test",
            "audience": "Engineers",
            "length_pages": 50,
            "outline": [{"id": "s1", "title": "Intro", "goals": [], "key_points": [], "dependencies": []}],
            "glossary": {"LLM": "Large language model"},
            "global_style": {"tone": "informative"},
            "diagram_specs": [{"section_id": "s1", "type": "graph", "mermaid_goal": "flow", "entities": [], "relationships": []}],
        }
    )
    planner = PlannerAgent(llm=FakeLLM(payload))
    plan = planner.plan("Test", "Engineers", 50)
    assert plan.title == "Test"
    assert plan.audience == "Engineers"
    assert plan.length_pages == 50
    assert plan.outline and plan.glossary and plan.global_style and plan.diagram_specs


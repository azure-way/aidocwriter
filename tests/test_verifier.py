from __future__ import annotations

import json

from docwriter.agents.verifier import VerifierAgent


class FakeLLM:
    def chat(self, model, messages, stream=False):
        # Always return no contradictions for simplicity
        return json.dumps({"contradictions": []})


def test_verifier_json_shape():
    v = VerifierAgent(llm=FakeLLM())
    out = v.verify({"s1": "- Fact A"}, "# Doc\n")
    data = json.loads(out)
    assert "contradictions" in data and isinstance(data["contradictions"], list)


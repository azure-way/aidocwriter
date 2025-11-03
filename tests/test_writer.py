from __future__ import annotations

from docwriter.agents.writer import WriterAgent


class FakeLLM:
    def chat(self, model, messages, stream=False):
        if stream:
            def gen():
                yield "# Section Title\n"
                yield "Some content with a diagram.\n"
                yield "```plantuml\n' diagram_id: s1-flow\n@startuml\nA -> B : call\n@enduml\n```\n"
            return gen()
        return "# Section Title\nContent.\n"


def test_writer_streaming_section():
    writer = WriterAgent(llm=FakeLLM())
    plan = {"global_style": {}, "glossary": {}, "diagram_specs": []}
    section = {"id": "s1", "title": "Intro"}
    text = "".join(list(writer.write_section(plan, section)))
    assert "# Section Title" in text

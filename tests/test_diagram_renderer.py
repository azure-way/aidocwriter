from docwriter.diagram_renderer import _preclean_plantuml_text


def test_preclean_removes_fences_and_wraps():
    raw = "```plantuml\nactor User\nUser -> API : hi\n```"
    cleaned = _preclean_plantuml_text(raw)
    assert cleaned.startswith("@startuml")
    assert cleaned.strip().endswith("@enduml")
    assert "```" not in cleaned

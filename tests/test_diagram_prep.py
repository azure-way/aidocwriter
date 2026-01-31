from docwriter.stages.diagram_prep import _sanitize_source, _validate_plantuml_source


def test_sanitize_removes_fences_and_adds_guards():
    body = "```plantuml\n' diagram_id: d1\nA -> B : hi\n```"
    sanitized = _sanitize_source(body)
    assert "@startuml" in sanitized
    assert "@enduml" in sanitized
    assert "```" not in sanitized
    assert "diagram_id" not in sanitized


def test_validate_flags_common_bad_outputs():
    bad = "@startuml\n```mermaid\nflowchart LR\n@enduml"
    issues = _validate_plantuml_source(bad)
    assert "contains markdown code fences inside PlantUML" in issues
    assert "contains Mermaid instead of PlantUML" in issues


def test_validate_accepts_clean_source():
    clean = "@startuml\nactor User\nUser -> API : Call\n@enduml"
    assert _validate_plantuml_source(clean) == []

from __future__ import annotations

from typing import Dict

PLANTUML_FEATURES: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {
    "plantuml_diagram_types": {
        "uml": {
            "class_diagram": {
                "description": "Models classes, attributes, methods, and relationships.",
                "syntax": "@startuml\nclass A {\n  +attr : int\n  +method()\n}\nA --> B\n@enduml",
            },
            "object_diagram": {
                "description": "Represents object instances and their links.",
                "syntax": "@startuml\nobject objA\nobject objB\nobjA --> objB\n@enduml",
            },
            "sequence_diagram": {
                "description": "Shows interactions between objects over time.",
                "syntax": "@startuml\nAlice -> Bob : Hello\nBob --> Alice : Response\n@enduml",
            },
            "use_case_diagram": {
                "description": "Models actors and system use cases.",
                "syntax": "@startuml\nactor User\nUser --> (Login)\n@enduml",
            },
            "activity_diagram": {
                "description": "Flow-based workflow modeling using activities and branching.",
                "syntax": "@startuml\nstart\n:Do task;\nif (Choice?) then (yes)\n  :Action A;\nelse (no)\n  :Action B;\nendif\nstop\n@enduml",
            },
            "state_diagram": {
                "description": "Describes states and transitions.",
                "syntax": "@startuml\n[*] --> Idle\nIdle --> Running : start\nRunning --> Idle : stop\n@enduml",
            },
            "component_diagram": {
                "description": "Shows components and their interfaces.",
                "syntax": "@startuml\ncomponent API\ncomponent DB\nAPI --> DB\n@enduml",
            },
            "deployment_diagram": {
                "description": "Models hardware nodes and deployed artifacts.",
                "syntax": "@startuml\nnode Server {\n  component App\n}\n@enduml",
            },
            "package_diagram": {
                "description": "Groups elements into packages.",
                "syntax": "@startuml\npackage Core {\n  class A\n}\n@enduml",
            },
        },
        "behavioral_and_flow": {
            "flowchart": {
                "description": "General-purpose flow diagrams.",
                "syntax": "@startuml\nstart\n:Step 1;\nif (Condition?) then (yes)\n  :Action;\nelse (no)\n  :Alternate;\nendif\nstop\n@enduml",
            },
            "timing_diagram": {
                "description": "Shows lifelines and state changes over time.",
                "syntax": "@startuml\ntiming\n  robust \"A\" as A\n  A @0 is Idle\n  A @10 is Active\nend timing\n@enduml",
            },
            "activity_beta": {
                "description": "Alternative activity diagram syntax (beta).",
                "syntax": "@startuml\nstart\n-> Action1\n-> Action2\nstop\n@enduml",
            },
        },
        "data_and_structure": {
            "entity_relationship_diagram": {
                "description": "ER-style data modeling.",
                "syntax": "@startuml\nentity User {\n  *id\n  name\n}\nentity Order {\n  *id\n  amount\n}\nUser ||--o{ Order\n@enduml",
            },
            "json_diagram": {
                "description": "Renders JSON structures.",
                "syntax": "@startjson\n{\n  \"user\": {\n    \"id\": 1,\n    \"name\": \"Alice\"\n  }\n}\n@endjson",
            },
            "yaml_diagram": {
                "description": "Renders YAML structures.",
                "syntax": "@startyaml\nuser:\n  id: 1\n  name: Alice\n@endyaml",
            },
        },
        "project_and_hierarchy": {
            "gantt_diagram": {
                "description": "Project timelines and scheduling.",
                "syntax": "@startgantt\n[Task] lasts 5 days\n@endgantt",
            },
            "wbs_diagram": {
                "description": "Work Breakdown Structure diagrams.",
                "syntax": "@startwbs\n+ Project\n++ Phase 1\n+++ Task A\n@endwbs",
            },
            "mindmap": {
                "description": "Hierarchical mind mapping.",
                "syntax": "@startmindmap\n* Root\n** Branch\n*** Leaf\n@endmindmap",
            },
        },
        "specialized": {
            "salt_diagram": {
                "description": "Simple UI layout diagrams.",
                "syntax": "@startsalt\n{+\n  Submit\n}\n@endsalt",
            },
            "wireframe": {
                "description": "Wireframe UI mockups (built-in).",
                "syntax": "@startuml\nrectangle \"Login Form\" {\n  label Username\n  label Password\n  button Submit\n}\n@enduml",
            },
            "card_diagram": {
                "description": "Structured card-like blocks.",
                "syntax": "@startuml\ncard UserCard {\n  Name: Alice\n  Role: Admin\n}\n@enduml",
            },
            "matrix_diagram": {
                "description": "Grid relationship mapping.",
                "syntax": "@startuml\nmatrix {\n  [A]\n  [B]\n  [A] -- [B] : link\n}\n@enduml",
            },
            "graphic_syntax": {
                "description": "Drawing simple geometric shapes.",
                "syntax": "@startuml\nrectangle R\ncircle C\nR --> C\n@enduml",
            },
            "sprite_support": {
                "description": "Define and reuse ASCII pixel sprites.",
                "syntax": "@startuml\nsprite foo {\n  000FF0\n  00F00F\n}\nrectangle <$foo$> Icon\n@enduml",
            },
        },
        "misc": {
            "latex_math": {
                "description": "Embed LaTeX or AsciiMath expressions.",
                "syntax": "@startuml\n: \\frac{1}{2} ;\n@enduml",
            },
            "notes_and_annotations": {
                "description": "Built-in notes, labels, legends.",
                "syntax": "@startuml\nnote right: This is a note\n@enduml",
            },
        },
    }
}


def build_plantuml_reference_text() -> str:
    sections = PLANTUML_FEATURES.get("plantuml_diagram_types", {})
    lines: list[str] = []
    for category, diagram_types in sections.items():
        lines.append(f"{category.replace('_', ' ').title()}:")
        for name, meta in diagram_types.items():
            description = meta.get("description", "").strip()
            syntax = meta.get("syntax", "").strip()
            lines.append(f"  - {name.replace('_', ' ')}: {description}")
            if syntax:
                lines.append("    Example:")
                syntax_lines = ["      " + line for line in syntax.splitlines()]
                lines.extend(syntax_lines)
    return "\n".join(lines)


PLANTUML_REFERENCE_TEXT = build_plantuml_reference_text()

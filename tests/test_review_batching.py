from __future__ import annotations

from docwriter.config import Settings
from docwriter.stages.core import _build_batch_context, _plan_review_batches


def _sample_sections():
    return {
        "1": "<!-- SECTION:1:START -->One<!-- SECTION:1:END -->",
        "2": "<!-- SECTION:2:START -->Two<!-- SECTION:2:END -->",
        "3": "<!-- SECTION:3:START -->Three<!-- SECTION:3:END -->",
        "4": "<!-- SECTION:4:START -->Four<!-- SECTION:4:END -->",
    }


def test_plan_review_batches_respects_batch_size_and_order():
    sections = _sample_sections()
    outline = [
        {"id": "1", "dependencies": []},
        {"id": "2", "dependencies": ["1"]},
        {"id": "3", "dependencies": ["1"]},
        {"id": "4", "dependencies": ["2"]},
    ]
    id_to_section = {str(s["id"]): s for s in outline}
    ordered_ids = ["1", "2", "3", "4"]
    settings = Settings(review_batch_size=2, review_max_prompt_tokens=5000)

    batches = _plan_review_batches(ordered_ids, set(), sections, id_to_section, {}, settings)

    assert batches == [["1", "2"], ["3", "4"]]


def test_build_batch_context_includes_dependency_stub_once():
    sections = _sample_sections()
    outline = [
        {"id": "1", "dependencies": []},
        {"id": "2", "dependencies": ["1"]},
        {"id": "3", "dependencies": ["1"]},
    ]
    id_to_section = {str(s["id"]): s for s in outline}
    dependency_summaries = {"1": "Short summary of section 1"}

    combined, deps = _build_batch_context(["2", "3"], sections, id_to_section, dependency_summaries)

    assert deps == ["1"]
    assert "Short summary of section 1" in combined
    assert combined.count("SECTION:2:START") == 1
    assert combined.count("SECTION:3:START") == 1

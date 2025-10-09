from __future__ import annotations

import pytest

from docwriter.graph import build_dependency_graph


def test_topological_order_basic():
    outline = [
        {"id": "s1", "dependencies": []},
        {"id": "s2", "dependencies": ["s1"]},
        {"id": "s3", "dependencies": ["s2"]},
    ]
    g = build_dependency_graph(outline)
    order = g.topological_order()
    assert order.index("s1") < order.index("s2") < order.index("s3")


def test_cycle_detection_raises():
    outline = [
        {"id": "a", "dependencies": ["b"]},
        {"id": "b", "dependencies": ["a"]},
    ]
    g = build_dependency_graph(outline)
    with pytest.raises(ValueError) as ei:
        g.topological_order()
    assert "Cycle detected in section dependencies" in str(ei.value)


from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple


class DependencyGraph:
    def __init__(self, nodes: List[str], edges: List[Tuple[str, str]]):
        self.nodes: Set[str] = set(nodes)
        self.adj: Dict[str, Set[str]] = defaultdict(set)
        self.rev: Dict[str, Set[str]] = defaultdict(set)
        for u, v in edges:
            if u not in self.nodes or v not in self.nodes:
                continue
            self.adj[u].add(v)
            self.rev[v].add(u)

    def topological_order(self) -> List[str]:
        indeg: Dict[str, int] = {n: 0 for n in self.nodes}
        for v, preds in self.rev.items():
            indeg[v] = len(preds)
        q = deque([n for n, d in indeg.items() if d == 0])
        order: List[str] = []
        while q:
            u = q.popleft()
            order.append(u)
            for v in self.adj.get(u, ()): 
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
        if len(order) != len(self.nodes):
            raise ValueError("Cycle detected in section dependencies")
        return order

    def layers(self) -> List[List[str]]:
        # Kahn layering
        indeg: Dict[str, int] = {n: 0 for n in self.nodes}
        for v, preds in self.rev.items():
            indeg[v] = len(preds)
        frontier: List[str] = [n for n, d in indeg.items() if d == 0]
        layers: List[List[str]] = []
        seen: Set[str] = set()
        while frontier:
            layer = list(frontier)
            layers.append(layer)
            next_frontier: List[str] = []
            for u in layer:
                seen.add(u)
                for v in self.adj.get(u, ()): 
                    indeg[v] -= 1
                    if indeg[v] == 0:
                        next_frontier.append(v)
            frontier = next_frontier
        if len(seen) != len(self.nodes):
            raise ValueError("Cycle detected in section dependencies")
        return layers


def build_dependency_graph(outline: List[dict]) -> DependencyGraph:
    nodes = [str(s.get("id")) for s in outline if s.get("id") is not None]
    edges: List[Tuple[str, str]] = []
    for s in outline:
        sid = str(s.get("id"))
        for dep in s.get("dependencies", []) or []:
            # edge: dep -> sid (sid depends on dep)
            edges.append((str(dep), sid))
    return DependencyGraph(nodes, edges)


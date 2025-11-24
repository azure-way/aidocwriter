from __future__ import annotations

import heapq
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple

SECTION_TOKEN_RE = re.compile(r"\d+|[^\d]+")


def _section_sort_key(section_id: str, fallback_index: int) -> Tuple[Tuple[int, object], ...]:
    tokens = SECTION_TOKEN_RE.findall(section_id)
    key: List[Tuple[int, object]] = []
    for token in tokens:
        if token.isdigit():
            key.append((0, int(token)))
        else:
            key.append((1, token))
    key.append((2, fallback_index))
    return tuple(key)


class DependencyGraph:
    def __init__(self, nodes: List[str], edges: List[Tuple[str, str]]):
        self.nodes: List[str] = []
        self.node_index: Dict[str, int] = {}
        for node in nodes:
            sid = str(node)
            if sid in self.node_index:
                continue
            self.node_index[sid] = len(self.nodes)
            self.nodes.append(sid)
        self.node_set: Set[str] = set(self.nodes)
        self.adj: Dict[str, Set[str]] = defaultdict(set)
        self.rev: Dict[str, Set[str]] = defaultdict(set)
        for u, v in edges:
            su = str(u)
            sv = str(v)
            if su not in self.node_set or sv not in self.node_set:
                continue
            self.adj[su].add(sv)
            self.rev[sv].add(su)

    def _ordering_key(self, section_id: str) -> Tuple[Tuple[int, object], ...]:
        fallback = self.node_index.get(section_id, len(self.nodes))
        return _section_sort_key(section_id, fallback)

    def topological_order(self) -> List[str]:
        indeg: Dict[str, int] = {n: 0 for n in self.nodes}
        for v, preds in self.rev.items():
            indeg[v] = len(preds)
        heap: List[Tuple[Tuple[Tuple[int, object], ...], str]] = []
        for n, degree in indeg.items():
            if degree == 0:
                heapq.heappush(heap, (self._ordering_key(n), n))
        order: List[str] = []
        while heap:
            _, u = heapq.heappop(heap)
            order.append(u)
            for v in self.adj.get(u, ()):
                indeg[v] -= 1
                if indeg[v] == 0:
                    heapq.heappush(heap, (self._ordering_key(v), v))
        if len(order) != len(self.nodes):
            raise ValueError("Cycle detected in section dependencies")
        return order

    def layers(self) -> List[List[str]]:
        # Kahn layering
        indeg: Dict[str, int] = {n: 0 for n in self.nodes}
        for v, preds in self.rev.items():
            indeg[v] = len(preds)
        key = self._ordering_key
        frontier: List[str] = [n for n, d in indeg.items() if d == 0]
        frontier.sort(key=lambda n: key(n))
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
            # Remove duplicates while preserving order
            deduped: List[str] = []
            seen_in_next: Set[str] = set()
            for item in next_frontier:
                if item in seen_in_next:
                    continue
                seen_in_next.add(item)
                deduped.append(item)
            deduped.sort(key=lambda n: key(n))
            frontier = deduped
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

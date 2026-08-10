from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceEdge:
    source: str
    relation: str
    target: str


class EvidenceGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[EvidenceEdge] = []

    def add_node(self, node_id: str, node_type: str, **attrs: Any) -> None:
        if node_id in self.nodes and self.nodes[node_id].get("node_type") != node_type:
            raise ValueError(f"node type conflict for {node_id}")
        self.nodes[node_id] = {"node_type": node_type, **attrs}

    def add_edge(self, source: str, relation: str, target: str) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise ValueError("edge endpoints must exist")
        edge = EvidenceEdge(source, relation, target)
        if edge not in self.edges:
            self.edges.append(edge)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": dict(sorted(self.nodes.items())),
            "edges": [asdict(edge) for edge in sorted(self.edges, key=lambda e: (e.source, e.relation, e.target))],
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

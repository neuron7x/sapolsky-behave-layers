from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_topology_semantics.py"
spec = importlib.util.spec_from_file_location("audit_topology_semantics", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_exact_edges_global1_matches_manual_small_cases() -> None:
    assert module.exact_edges_global1(4, 3) == 10
    assert module.exact_edges_global1(5, 3) == 15
    assert module.exact_edges_global1(12, 3) == 50
    assert module.exact_edges_global1(16, 3) == 70

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import tempfile
import zipfile
from collections import deque
from pathlib import Path
from typing import Any

import torch
import yaml

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "legacy" / "cognitive-weave-kernel-archive.zip"
LENGTHS = (8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime(archive: Path) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp = tempfile.TemporaryDirectory(prefix="cwc-topology-audit-")
    with zipfile.ZipFile(archive) as handle:
        handle.extractall(temp.name)
    candidates = sorted(Path(temp.name).glob("*/cognitive-weave-kernel"))
    if len(candidates) != 1:
        temp.cleanup()
        raise RuntimeError(f"expected one archived CWK project, found {len(candidates)}")
    return temp, candidates[0]


def exact_edges_global1(n: int, w: int) -> int:
    if n <= w + 1:
        return n * (n + 1) // 2
    return (w + 2) * n - (w + 2) * (w + 1) // 2


def undirected_diameter(mask: torch.Tensor) -> int | None:
    adjacency = (mask | mask.T).cpu()
    n = int(adjacency.shape[0])
    max_distance = 0
    for source in range(n):
        distances = [-1] * n
        distances[source] = 0
        queue: deque[int] = deque([source])
        while queue:
            node = queue.popleft()
            neighbors = torch.nonzero(adjacency[node], as_tuple=False).reshape(-1).tolist()
            for nxt in neighbors:
                if distances[nxt] < 0:
                    distances[nxt] = distances[node] + 1
                    queue.append(nxt)
        if any(distance < 0 for distance in distances):
            return None
        max_distance = max(max_distance, max(distances))
    return max_distance


def slope(xs: list[float], ys: list[float]) -> float:
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / denom


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    temp, project = runtime(args.archive)
    sys.path.insert(0, str(project / "src"))
    try:
        from cwk.topology import local_global_mask, topology_stats

        cfg = yaml.safe_load((project / "configs" / "smoke.yaml").read_text(encoding="utf-8"))
        w = int(cfg["model"]["local_window"])
        g = int(cfg["model"]["global_tokens"])
        rows: list[dict[str, Any]] = []
        exact_formula_all_match = True
        for n in LENGTHS:
            mask = local_global_mask(n, w, g, causal=True)
            stats = topology_stats(mask)
            diameter = undirected_diameter(mask)
            exact = exact_edges_global1(n, w) if g == 1 else None
            match = exact is None or int(stats.directed_edges) == exact
            exact_formula_all_match = exact_formula_all_match and match
            rows.append({
                "sequence_length": n,
                "directed_edges": int(stats.directed_edges),
                "density": float(stats.density),
                "wiring_cost": float(stats.wiring_cost),
                "undirected_diameter": diameter,
                "exact_global1_edges": exact,
                "exact_formula_match": match,
            })
        eligible = [row for row in rows if row["sequence_length"] > w + 1]
        edge_slope = slope(
            [math.log(row["sequence_length"]) for row in eligible],
            [math.log(row["directed_edges"]) for row in eligible],
        )
        density_slope = slope(
            [math.log(row["sequence_length"]) for row in eligible],
            [math.log(row["density"]) for row in eligible],
        )
        all_diameter_le2 = all(
            row["undirected_diameter"] is not None and row["undirected_diameter"] <= 2
            for row in eligible
        )
        payload = {
            "schema_version": "cwc.topology_semantics_audit.v1",
            "archive": str(args.archive),
            "archive_sha256": sha256(args.archive),
            "config": {"local_window": w, "global_tokens": g, "causal": True},
            "lengths": list(LENGTHS),
            "rows": rows,
            "edge_count_loglog_slope": edge_slope,
            "density_loglog_slope": density_slope,
            "exact_global1_formula_all_match": exact_formula_all_match,
            "undirected_diameter_le_2_for_scaling_range": all_diameter_le2,
            "verdict": (
                "GRAPH_DISTANCE_FRACTALITY_NOT_IDENTIFIABLE_GLOBAL_HUB_COLLAPSES_SCALE"
                if all_diameter_le2 else "TOPOLOGY_SCALE_STRUCTURE_UNRESOLVED"
            ),
            "claim_boundary": (
                "The archived topology is a deterministic causal local/global mask. Sparse edge "
                "scaling or a short graph diameter does not establish fractal geometry, cognition, "
                "useful adaptive computation, or physical sparse attention execution."
            ),
            "scientific_ascension_authority": False,
            "via_authority": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({
            "edge_count_loglog_slope": edge_slope,
            "density_loglog_slope": density_slope,
            "exact_formula_all_match": exact_formula_all_match,
            "diameter_le_2": all_diameter_le2,
            "verdict": payload["verdict"],
        }, indent=2, sort_keys=True))
    finally:
        temp.cleanup()


if __name__ == "__main__":
    main()

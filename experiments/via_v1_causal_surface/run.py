"""Normalize already-sealed CWC evidence for the VIA-V1 causal-method audit.

This runner performs **no training** and creates **no new scientific observations**.
It is an adapter from frozen WP18/WP19/AC1 JSON artifacts to one explicit
context×action replicate-matrix contract.  See PREREGISTRATION.md.
"""
from __future__ import annotations

import glob
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/via-v1-causal-surface"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle_digest(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in sorted(paths):
        rel = path.relative_to(ROOT).as_posix()
        h.update(rel.encode())
        h.update(b"\0")
        h.update(_sha256(path).encode())
        h.update(b"\n")
    return h.hexdigest()


def _load_jsons(pattern: str) -> tuple[list[dict[str, Any]], list[Path]]:
    paths = [Path(p) for p in sorted(glob.glob(str(ROOT / pattern)))]
    if not paths:
        raise FileNotFoundError(f"no frozen inputs match {pattern}")
    return [json.loads(p.read_text()) for p in paths], paths


def _wp18(family: str) -> tuple[list[list[list[float]]], list[Path]]:
    runs, paths = _load_jsons(f"artifacts/wp18-real-workload-pilot/raw_runs/seed*_{family}_*.json")
    matrices: list[list[list[float]]] = []
    for run in runs:
        actions = [str(k) for k in run["k_choices"]]
        for shard in run["shards"]:
            matrices.append([
                [-float(shard["loss"][bucket][action]) for action in actions]
                for bucket in run["buckets"]
            ])
    return matrices, paths


def _wp19(family: str) -> tuple[list[list[list[float]]], list[Path]]:
    runs, paths = _load_jsons(f"artifacts/wp19-negative-robustness/raw_runs/{family}_L*.json")
    depths = sorted({int(r["depth"]) for r in runs})
    seeds = sorted({int(r["seed"]) for r in runs})
    contexts = list(runs[0]["buckets"])
    matrices: list[list[list[float]]] = []
    for seed in seeds:
        by_depth = {int(r["depth"]): r for r in runs if int(r["seed"]) == seed}
        if set(by_depth) != set(depths):
            raise ValueError(f"WP19 {family}: incomplete depth set for seed {seed}")
        n_shards = len(by_depth[depths[0]]["shards"])
        if any(len(by_depth[d]["shards"]) != n_shards for d in depths):
            raise ValueError(f"WP19 {family}: shard count differs by depth")
        for shard_index in range(n_shards):
            matrices.append([
                [
                    -float(by_depth[depth]["shards"][shard_index]["loss"][context])
                    for depth in depths
                ]
                for context in contexts
            ])
    return matrices, paths


def _ac1() -> tuple[list[list[list[float]]], list[Path]]:
    runs, paths = _load_jsons("artifacts/wp5-adaptive-compute-identifiability/raw_runs/seed*.json")
    contexts = [str(d) for d in runs[0]["depths"]]
    actions = [str(k) for k in runs[0]["k_choices"]]
    matrices = [
        [[float(run["acc"][context][action]) for action in actions] for context in contexts]
        for run in runs
    ]
    return matrices, paths


def _entry(
    *,
    name: str,
    tier: str,
    contexts: list[str],
    actions: list[str],
    matrices: list[list[list[float]]],
    paths: list[Path],
    frozen_g_lo: float | None,
) -> dict[str, Any]:
    return {
        "name": name,
        "tier": tier,
        "contexts": contexts,
        "actions": actions,
        "n_replicate_matrices": len(matrices),
        "matrices": matrices,
        "source_files": [p.relative_to(ROOT).as_posix() for p in sorted(paths)],
        "source_bundle_sha256": _bundle_digest(paths),
        "frozen_g_lo": frozen_g_lo,
    }


def build() -> dict[str, Any]:
    wp18_verdict_path = ROOT / "artifacts/wp18-real-workload-pilot/verdict.json"
    wp19_verdict_path = ROOT / "artifacts/wp19-negative-robustness/verdict.json"
    wp18_verdict = json.loads(wp18_verdict_path.read_text())
    wp19_verdict = json.loads(wp19_verdict_path.read_text())
    if wp18_verdict["verdict"] != "WP18_KILL_RULE_TRIGGERED_NO_REAL_IDENTIFIABILITY":
        raise ValueError("prior WP18 kill rule is not present; fail closed")
    if wp19_verdict["verdict"] != "NEGATIVE_IS_MECHANISM_SPECIFIC":
        raise ValueError("expected WP19 robustness verdict is not present; fail closed")
    route_cost = float(wp18_verdict["decision"]["c_route"])

    wp18_prose, p18p = _wp18("prose")
    wp18_code, p18c = _wp18("code")
    wp19_prose, p19p = _wp19("prose")
    wp19_code, p19c = _wp19("code")
    ac1, pac1 = _ac1()

    bundles = [
        _entry(
            name="WP18-prose-tiedK", tier="REAL_RETROSPECTIVE",
            contexts=["easy", "med", "hard"], actions=["1", "2", "3"],
            matrices=wp18_prose, paths=p18p,
            frozen_g_lo=float(wp18_verdict["workloads"]["prose"]["g_lo_by_lambda"]["0.0"]),
        ),
        _entry(
            name="WP18-code-tiedK", tier="REAL_RETROSPECTIVE",
            contexts=["easy", "med", "hard"], actions=["1", "2", "3"],
            matrices=wp18_code, paths=p18c,
            frozen_g_lo=float(wp18_verdict["workloads"]["code"]["g_lo_by_lambda"]["0.0"]),
        ),
        _entry(
            name="WP19-prose-untied-depth", tier="REAL_RETROSPECTIVE",
            contexts=["easy", "med", "hard"], actions=["1", "2", "3"],
            matrices=wp19_prose, paths=p19p,
            frozen_g_lo=float(wp19_verdict["workloads"]["prose"]["g_lo_by_lambda"]["0.0"]),
        ),
        _entry(
            name="WP19-code-untied-depth", tier="REAL_RETROSPECTIVE",
            contexts=["easy", "med", "hard"], actions=["1", "2", "3"],
            matrices=wp19_code, paths=p19c,
            frozen_g_lo=float(wp19_verdict["workloads"]["code"]["g_lo_by_lambda"]["0.0"]),
        ),
        _entry(
            name="AC1-synthetic-positive", tier="SYNTHETIC_POSITIVE_CONTROL",
            contexts=["1", "2", "3"], actions=["1", "2", "3"],
            matrices=ac1, paths=pac1, frozen_g_lo=None,
        ),
    ]
    return {
        "schema": "cwc-via-v1/reanalysis-input-1",
        "class": "RETROSPECTIVE_METHOD_VALIDATION_ONLY",
        "ascension_authority": False,
        "prior_kill_rule": wp18_verdict["verdict"],
        "prior_robustness_verdict": wp19_verdict["verdict"],
        "route_cost": route_cost,
        "frozen_verdict_sources": {
            wp18_verdict_path.relative_to(ROOT).as_posix(): _sha256(wp18_verdict_path),
            wp19_verdict_path.relative_to(ROOT).as_posix(): _sha256(wp19_verdict_path),
        },
        "bundles": bundles,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = build()
    path = OUT / "reanalysis_input.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"VIA-V1 NORMALIZE: PASS ({len(payload['bundles'])} frozen bundles -> {path.relative_to(ROOT)})")


if __name__ == "__main__":
    main()

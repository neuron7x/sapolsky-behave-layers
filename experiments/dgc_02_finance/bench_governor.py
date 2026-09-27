from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time
from pathlib import Path

from cwc.governance.budget import BudgetLedger
from cwc.governance.compute_governor import ComputeGovernor
from cwc.governance.compute_value import estimate_voc
from cwc.governance.contracts import CandidateOperation, ComputeDirective

ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _refresh_manifest(artifact_dir: Path) -> None:
    names = ["RESULTS.md", "verdict.json", "governor_microbench.json"]
    if not all((artifact_dir / name).is_file() for name in names):
        return
    manifest = {name: _sha256(artifact_dir / name) for name in names}
    (artifact_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (artifact_dir / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(manifest.items())), encoding="utf-8"
    )


def benchmark(*, iterations: int, repeats: int, warmup: int) -> dict[str, object]:
    if iterations <= 0 or repeats <= 1 or warmup < 0:
        raise ValueError("invalid benchmark parameters")
    budget = BudgetLedger(hard_tokens=1_000_000, hard_money=1_000_000, hard_time=1_000_000)
    ops = (
        CandidateOperation("retrieve", ComputeDirective.RETRIEVE, 0.02, token_cost=1),
        CandidateOperation("critic", ComputeDirective.CRITIC, 0.03, token_cost=1),
        CandidateOperation("probe", ComputeDirective.LOCAL_PROBE, 0.01, token_cost=1),
    )
    estimates = {
        "retrieve": estimate_voc(operation_id="retrieve", gross_value=0.07, total_cost=0.02, gross_lower=0.06, gross_upper=0.08, method="bench"),
        "critic": estimate_voc(operation_id="critic", gross_value=0.06, total_cost=0.03, gross_lower=0.05, gross_upper=0.07, method="bench"),
        "probe": estimate_voc(operation_id="probe", gross_value=0.025, total_cost=0.01, gross_lower=0.02, gross_upper=0.03, method="bench"),
    }
    kwargs = dict(operations=ops, estimates=estimates, budget=budget, decision_digest="benchmark")
    for _ in range(warmup):
        ComputeGovernor.select(**kwargs)
    samples_ns: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(iterations):
            ComputeGovernor.select(**kwargs)
        elapsed = time.perf_counter_ns() - start
        samples_ns.append(elapsed / iterations)
    ordered = sorted(samples_ns)
    p95_index = min(len(ordered) - 1, int(0.95 * len(ordered)))
    return {
        "schema": "dgc-governor-local-microbench/1", "authority": "LOCAL_SHARED_RUNTIME_DIAGNOSTIC_ONLY",
        "python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(),
        "iterations_per_repeat": iterations, "repeats": repeats, "warmup_calls": warmup,
        "candidate_operations": len(ops), "median_ns_per_select": statistics.median(samples_ns),
        "p95_ns_per_select": ordered[p95_index], "min_ns_per_select": min(samples_ns),
        "max_ns_per_select": max(samples_ns),
        "note": "Shared-runtime wall-time diagnostic; not a production latency or USD-cost claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=50_000)
    parser.add_argument("--repeats", type=int, default=21)
    parser.add_argument("--warmup", type=int, default=10_000)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/dgc-02-finance-dev/governor_microbench.json")
    args = parser.parse_args()
    result = benchmark(iterations=args.iterations, repeats=args.repeats, warmup=args.warmup)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _refresh_manifest(args.output.parent)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

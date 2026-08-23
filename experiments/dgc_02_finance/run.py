from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from experiments.dgc_01.baselines import POLICIES
from experiments.dgc_01.workloads import generate_workload
from experiments.dgc_02_finance.analysis import evaluate_financial_gate

ROOT = Path(__file__).resolve().parents[2]
OVERHEAD_SWEEP = (0.0, 0.0025, 0.005, 0.0075, 0.010, 0.0125, 0.015)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(per_regime: int, seed_offset: int) -> dict[str, object]:
    tasks = generate_workload(per_regime, seed_offset=seed_offset)
    ref_costs: list[float] = []
    dgc_costs: list[float] = []
    ref_losses: list[float] = []
    dgc_losses: list[float] = []
    strata: list[str] = []
    baseline_summary: dict[str, dict[str, float]] = {}
    per_policy = {p(tasks[0]).policy: {"cost": 0.0, "loss": 0.0, "compute": 0.0} for p in POLICIES}

    for task in tasks:
        decisions = {p(task).policy: p(task) for p in POLICIES}
        for name, decision in decisions.items():
            if decision.buy_diagnostic:
                cost = task.diagnostic_cost
                loss = 0.0
                comp = 1.0
            else:
                cost = 0.0
                loss = task.realized_loss(task.baseline_action)
                comp = 0.0
            per_policy[name]["cost"] += cost
            per_policy[name]["loss"] += loss
            per_policy[name]["compute"] += comp

        b0 = decisions["B0_FIXED"]
        dgc = decisions["B3_DGC"]
        ref_costs.append(task.diagnostic_cost if b0.buy_diagnostic else 0.0)
        dgc_costs.append(task.diagnostic_cost if dgc.buy_diagnostic else 0.0)
        ref_losses.append(0.0 if b0.buy_diagnostic else task.realized_loss(task.baseline_action))
        dgc_losses.append(0.0 if dgc.buy_diagnostic else task.realized_loss(task.baseline_action))
        strata.append(task.regime)

    n = len(tasks)
    for name, accum in sorted(per_policy.items()):
        baseline_summary[name] = {
            "mean_compute_cost": accum["cost"] / n,
            "mean_decision_loss": accum["loss"] / n,
            "compute_rate": accum["compute"] / n,
        }

    sweep = []
    for overhead in OVERHEAD_SWEEP:
        result = evaluate_financial_gate(
            reference_costs=ref_costs,
            dgc_core_costs=dgc_costs,
            reference_losses=ref_losses,
            dgc_losses=dgc_losses,
            governance_overhead_per_task=overhead,
            strata=strata,
        )
        sweep.append(asdict(result))
    primary = sweep[0]
    return {
        "schema": "dgc-02-financial-development/1",
        "status": "DEVELOPMENT_ONLY_NON_PROMOTING",
        "per_regime": per_regime,
        "seed_offset": seed_offset,
        "tasks": n,
        "reference_policy": "B0_FIXED",
        "threshold": 0.30,
        "baseline_summary": baseline_summary,
        "zero_unmetered_overhead_ceiling": primary,
        "overhead_sensitivity": sweep,
        "development_threshold_status": "DEVELOPMENT_THRESHOLD_MET" if bool(primary["threshold_met"]) else "DEVELOPMENT_THRESHOLD_NOT_MET",
        "commercial_claim_allowed": False,
        "claim_promotion": "PROHIBITED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-regime", type=int, default=20_000)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/dgc-02-finance-dev")
    args = parser.parse_args()
    result = run(args.per_regime, args.seed_offset)
    args.output.mkdir(parents=True, exist_ok=True)
    verdict = args.output / "verdict.json"
    verdict.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    p = result["zero_unmetered_overhead_ceiling"]
    lines = [
        "# DGC-02 Financial Development Verification\n",
        "**Authority:** DEVELOPMENT_ONLY / NON-PROMOTING. The 30% figure is a verification target, not a commercial claim.\n",
        f"Tasks: {result['tasks']} paired synthetic decisions. Reference: `B0_FIXED`.\n",
        "## Zero-unmetered-overhead core-compute ceiling\n",
        f"- aggregate NetInferenceSavings: `{p['net_inference_savings']:.9f}`\n",
        f"- conservative savings LCB: `{p['savings_lcb']:.9f}`\n",
        f"- DeltaQuality: `{p['delta_quality']:.9f}`\n",
        f"- quality LCB: `{p['quality_lcb']:.9f}`\n",
        f"- 30% development threshold: `{'PASS' if p['threshold_met'] else 'FAIL'}`\n",
        f"- max mean governance overhead compatible with 30% point-estimate target: `{p['max_mean_overhead_for_threshold']:.9f}` normalized cost units/task\n",
        "\nThis result is a ceiling because live governor/monitor/provider overhead has not yet been metered in the synthetic scalar-cost model.\n",
        "## Overhead sensitivity\n",
        "| overhead/task | net savings | savings LCB | gate |\n|---:|---:|---:|:---:|\n",
    ]
    for row in result["overhead_sensitivity"]:
        lines.append(f"| {row['mean_governance_overhead']:.4f} | {row['net_inference_savings']:.6f} | {row['savings_lcb']:.6f} | {'PASS' if row['threshold_met'] else 'FAIL'} |\n")
    lines += [
        "\n## Interpretation boundary\n",
        "- Development synthetic evidence only.\n",
        "- No USD/client/ARR claim is authorized.\n",
        "- Live accounting must include governor, monitoring, tools, retries, provider charges and latency penalties.\n",
        "- Untouched confirmatory and client-trace replication remain mandatory.\n",
    ]
    results = args.output / "RESULTS.md"
    results.write_text("".join(lines), encoding="utf-8")
    manifest = {"RESULTS.md": _sha256(results), "verdict.json": _sha256(verdict)}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output / "SHA256SUMS").write_text("".join(f"{v}  {k}\n" for k, v in sorted(manifest.items())), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

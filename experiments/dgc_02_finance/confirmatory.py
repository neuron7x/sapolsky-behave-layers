from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from experiments.dgc_01.baselines import b0_fixed, b3_dgc
from experiments.dgc_01.workloads import generate_workload
from experiments.dgc_02_finance.analysis import evaluate_financial_gate
from experiments.dgc_02_finance.analytic import savings_with_mean_overhead, synthetic_financial_theorem

ROOT = Path(__file__).resolve().parents[2]
PER_REGIME = 20_000
SEED_OFFSET = 200_000_000
OVERHEAD = 0.0125
THRESHOLD = 0.30
EXPECTED_TASKS = 100_000
PREREG_COMMIT = "8e6db42fcb1a12dcf7e3fca54f695e6b05a06e70"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run() -> dict[str, object]:
    tasks = generate_workload(PER_REGIME, seed_offset=SEED_OFFSET)
    if len(tasks) != EXPECTED_TASKS:
        raise RuntimeError("CONFIRMATORY_COVERAGE_CHANGED")
    ref_costs: list[float] = []
    dgc_costs: list[float] = []
    ref_losses: list[float] = []
    dgc_losses: list[float] = []
    strata: list[str] = []
    for task in tasks:
        b0 = b0_fixed(task)
        dgc = b3_dgc(task)
        ref_costs.append(task.diagnostic_cost if b0.buy_diagnostic else 0.0)
        dgc_costs.append(task.diagnostic_cost if dgc.buy_diagnostic else 0.0)
        ref_losses.append(0.0 if b0.buy_diagnostic else task.realized_loss(task.baseline_action))
        dgc_losses.append(0.0 if dgc.buy_diagnostic else task.realized_loss(task.baseline_action))
        strata.append(task.regime)

    result = evaluate_financial_gate(
        reference_costs=ref_costs,
        dgc_core_costs=dgc_costs,
        reference_losses=ref_losses,
        dgc_losses=dgc_losses,
        governance_overhead_per_task=OVERHEAD,
        strata=strata,
        threshold=THRESHOLD,
    )
    theorem = synthetic_financial_theorem(threshold=THRESHOLD)
    analytic_savings = savings_with_mean_overhead(OVERHEAD)
    monte_carlo_gap = abs(result.net_inference_savings - analytic_savings)
    coverage = len(ref_costs) / EXPECTED_TASKS
    passed = (
        result.net_inference_savings >= THRESHOLD
        and result.savings_lcb >= THRESHOLD
        and result.quality_lcb >= 0.0
        and coverage == 1.0
        and monte_carlo_gap <= 0.002
    )
    return {
        "schema": "dgc-02-synthetic-confirmatory/1",
        "authority": "PROSPECTIVE_SYNTHETIC_CONFIRMATION",
        "preregistration_commit": PREREG_COMMIT,
        "per_regime": PER_REGIME,
        "seed_offset": SEED_OFFSET,
        "tasks": len(tasks),
        "coverage": coverage,
        "synthetic_governance_overhead": OVERHEAD,
        "threshold": THRESHOLD,
        "financial_gate": asdict(result),
        "analytic_population_savings_at_overhead": analytic_savings,
        "monte_carlo_gap_to_analytic": monte_carlo_gap,
        "analytic_theorem": asdict(theorem),
        "status": "SYNTHETIC_CONFIRMATORY_THRESHOLD_MET" if passed else "SYNTHETIC_CONFIRMATORY_THRESHOLD_NOT_MET",
        "client_verified": False,
        "commercial_claim_allowed": False,
        "general_superiority_claim_allowed": False,
    }


def main() -> int:
    out = ROOT / "artifacts/dgc-02-finance-confirmatory"
    out.mkdir(parents=True, exist_ok=True)
    result = run()
    verdict = out / "verdict.json"
    verdict.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    f = result["financial_gate"]
    results = out / "RESULTS.md"
    results.write_text(
        "# DGC-02 Prospective Synthetic Financial Confirmation\n\n"
        f"Preregistration commit: `{PREREG_COMMIT}`.\n\n"
        f"Status: **{result['status']}**.\n\n"
        f"- tasks: `{result['tasks']}`; coverage: `{result['coverage']:.6f}`\n"
        f"- synthetic overhead/task: `{OVERHEAD:.6f}` normalized cost units\n"
        f"- NetInferenceSavings: `{f['net_inference_savings']:.9f}`\n"
        f"- stratified fixed-n savings LCB: `{f['savings_lcb']:.9f}`\n"
        f"- DeltaQuality: `{f['delta_quality']:.9f}`; quality LCB: `{f['quality_lcb']:.9f}`\n"
        f"- analytic population savings at same overhead: `{result['analytic_population_savings_at_overhead']:.9f}`\n"
        f"- Monte-Carlo gap to analytic population value: `{result['monte_carlo_gap_to_analytic']:.9f}`\n\n"
        "This confirms only the frozen synthetic model. `client_verified=false`; no fixed-percentage commercial guarantee is authorized.\n",
        encoding="utf-8",
    )
    manifest = {"RESULTS.md": _sha256(results), "verdict.json": _sha256(verdict)}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "SHA256SUMS").write_text("".join(f"{v}  {k}\n" for k, v in sorted(manifest.items())), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "SYNTHETIC_CONFIRMATORY_THRESHOLD_MET" else 2


if __name__ == "__main__":
    raise SystemExit(main())

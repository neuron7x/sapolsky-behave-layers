"""Analyze the frozen Causal Debt Ledger V1 results."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

from cwc.replay.stats import exact_max_t_fwer

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "causal-debt-v1"
PROTOCOL = json.loads((HERE / "protocol.json").read_text())


def _load() -> list[dict]:
    return [json.loads(line) for line in (OUT / "raw_results.jsonl").read_text().splitlines() if line.strip()]


def main() -> int:
    rows = _load()
    index = {(r["seed"], r["budget"], r["policy"]): r for r in rows}
    primary = PROTOCOL["primary_policy"]
    controls = PROTOCOL["matched_cf_controls"]
    seeds = PROTOCOL["seeds"]
    budgets = PROTOCOL["replay_budgets"]

    budget_summary: dict[str, dict[str, dict[str, float]]] = {}
    replication: dict[str, int] = {control: 0 for control in controls}
    for budget in budgets:
        budget_summary[str(budget)] = {}
        for policy in [primary, *controls, "fifo_obs", "rpe_obs", "uncertainty_obs", "oracle_invariant"]:
            cell = [index[(seed, budget, policy)] for seed in seeds]
            budget_summary[str(budget)][policy] = {
                "median_oos_accuracy": median(r["accuracy"]["oos"] for r in cell),
                "false_credit_rate": sum(r["false_credit"] for r in cell) / len(cell),
                "invariant_recall": sum(r["invariant_recall"] for r in cell) / len(cell),
                "median_credit_margin": median(r["credit_margin"] for r in cell),
            }
        for control in controls:
            if (
                budget_summary[str(budget)][primary]["median_oos_accuracy"]
                > budget_summary[str(budget)][control]["median_oos_accuracy"]
            ):
                replication[control] += 1

    paired_diffs: list[list[float]] = []
    for control in controls:
        diffs = []
        for seed in seeds:
            primary_mean = sum(index[(seed, b, primary)]["accuracy"]["oos"] for b in budgets) / len(budgets)
            control_mean = sum(index[(seed, b, control)]["accuracy"]["oos"] for b in budgets) / len(budgets)
            diffs.append(primary_mean - control_mean)
        paired_diffs.append(diffs)
    p_fwer = exact_max_t_fwer(paired_diffs)

    aggregate: dict[str, dict[str, float]] = {}
    for policy in [primary, *controls]:
        cells = [index[(seed, budget, policy)] for seed in seeds for budget in budgets]
        aggregate[policy] = {
            "median_oos_accuracy": median(r["accuracy"]["oos"] for r in cells),
            "false_credit_rate": sum(r["false_credit"] for r in cells) / len(cells),
            "invariant_recall": sum(r["invariant_recall"] for r in cells) / len(cells),
            "median_credit_margin": median(r["credit_margin"] for r in cells),
        }

    checks = {
        "oos_median_beats_uniform_cf": aggregate[primary]["median_oos_accuracy"] > aggregate["uniform_cf"]["median_oos_accuracy"],
        "oos_median_beats_rpe_cf": aggregate[primary]["median_oos_accuracy"] > aggregate["rpe_cf"]["median_oos_accuracy"],
        "fwer_uniform_cf_le_0_05": p_fwer[0] <= PROTOCOL["alpha_familywise"],
        "fwer_rpe_cf_le_0_05": p_fwer[1] <= PROTOCOL["alpha_familywise"],
        "false_credit_below_uniform_cf": aggregate[primary]["false_credit_rate"] < aggregate["uniform_cf"]["false_credit_rate"],
        "false_credit_below_rpe_cf": aggregate[primary]["false_credit_rate"] < aggregate["rpe_cf"]["false_credit_rate"],
        "recall_not_below_uniform_cf": aggregate[primary]["invariant_recall"] >= aggregate["uniform_cf"]["invariant_recall"],
        "recall_not_below_rpe_cf": aggregate[primary]["invariant_recall"] >= aggregate["rpe_cf"]["invariant_recall"],
        "budget_replication_vs_uniform_cf": replication["uniform_cf"] >= PROTOCOL["min_budget_replication"],
        "budget_replication_vs_rpe_cf": replication["rpe_cf"] >= PROTOCOL["min_budget_replication"],
        "synthetic_only_non_authorizing": PROTOCOL["via_ascension_authority"] is False,
    }
    qualified = all(checks.values())
    verdict_name = "CAUSAL_DEBT_CONTROL_QUALIFIED" if qualified else "CAUSAL_DEBT_CONTROL_NOT_QUALIFIED"
    verdict = {
        "schema": "cwc-cdl/verdict-1",
        "verdict": verdict_name,
        "scientific_pass": False,
        "control_qualification": qualified,
        "via_ascension_authorized": False,
        "biological_claim_authorized": False,
        "scope": "synthetic structural causal model only",
        "primary_policy": primary,
        "matched_cf_controls": controls,
        "aggregate": aggregate,
        "budget_summary": budget_summary,
        "budget_replication": replication,
        "paired_fwer_p": dict(zip(controls, p_fwer, strict=True)),
        "checks": checks,
        "interpretation": (
            "A qualification supports only the computational possibility that deferred causal-credit scheduling can be more sample-efficient than matched counterfactual replay controls in this frozen synthetic SCM."
            if qualified
            else "The preregistered synthetic experiment did not satisfy every control-qualification condition; the causal-debt scheduler receives no positive claim."
        ),
    }
    path = OUT / "verdict.json"
    path.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT / "SHA256SUMS.verdict").write_text(f"{digest}  verdict.json\n")
    print(json.dumps({"verdict": verdict_name, "p_fwer": verdict["paired_fwer_p"], "replication": replication, "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

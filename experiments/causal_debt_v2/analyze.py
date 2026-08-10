"""Analyze preregistered Causal Debt V2 control benchmark."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import median

from cwc.replay.stats import exact_max_t_fwer

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "causal-debt-v2"
PROTOCOL = json.loads((HERE / "protocol.json").read_text())


def _load() -> list[dict]:
    return [json.loads(line) for line in (OUT / "raw_results.jsonl").read_text().splitlines() if line]


def main() -> int:
    rows = _load()
    idx = {(r["seed"], r["budget"], r["variant"], r["policy"]): r for r in rows}
    seeds = PROTOCOL["seeds"]
    budgets = PROTOCOL["replay_budgets"]
    variants = PROTOCOL["environment_variants"]
    primary = PROTOCOL["primary_policy"]
    controls = PROTOCOL["matched_cf_controls"]

    # Primary paired subject-level endpoint: mean over frozen environments/budgets.
    comparisons: list[list[float]] = []
    mean_diffs: dict[str, float] = {}
    for control in controls:
        diffs = []
        for seed in seeds:
            p = sum(idx[(seed, b, v, primary)]["accuracy"]["oos"] for b in budgets for v in variants) / (len(budgets) * len(variants))
            c = sum(idx[(seed, b, v, control)]["accuracy"]["oos"] for b in budgets for v in variants) / (len(budgets) * len(variants))
            diffs.append(p - c)
        comparisons.append(diffs)
        mean_diffs[control] = sum(diffs) / len(diffs)
    p_fwer = exact_max_t_fwer(comparisons)

    def aggregate(policy: str, *, variant: str | None = None) -> dict[str, float]:
        cell = [
            idx[(seed, b, v, policy)]
            for seed in seeds
            for b in budgets
            for v in variants
            if variant is None or v == variant
        ]
        return {
            "median_oos_accuracy": median(r["accuracy"]["oos"] for r in cell),
            "mean_oos_accuracy": sum(r["accuracy"]["oos"] for r in cell) / len(cell),
            "false_credit_rate": sum(r["false_credit"] for r in cell) / len(cell),
            "invariant_recall": sum(r["invariant_recall"] for r in cell) / len(cell),
        }

    summary = {policy: aggregate(policy) for policy in [primary, *controls, PROTOCOL["oracle_reference"]]}
    variant_summary = {
        variant: {policy: aggregate(policy, variant=variant) for policy in [primary, *controls, PROTOCOL["oracle_reference"]]}
        for variant in variants
    }

    desc_superiority = 0
    budget_summary: dict[str, dict[str, dict[str, float]]] = {}
    for b in budgets:
        budget_summary[str(b)] = {}
        for policy in [primary, *controls]:
            cell = [idx[(seed, b, "descendant", policy)] for seed in seeds]
            budget_summary[str(b)][policy] = {
                "median_descendant_oos": median(r["accuracy"]["oos"] for r in cell),
                "recall": sum(r["invariant_recall"] for r in cell) / len(cell),
            }
        if budget_summary[str(b)][primary]["median_descendant_oos"] > budget_summary[str(b)]["rpe_cf"]["median_descendant_oos"]:
            desc_superiority += 1

    proxy_primary = variant_summary["proxy"][primary]["median_oos_accuracy"]
    proxy_rpe = variant_summary["proxy"]["rpe_cf"]["median_oos_accuracy"]
    checks = {
        "positive_mean_oos_vs_uniform_cf": mean_diffs["uniform_cf"] > 0.0,
        "positive_mean_oos_vs_rpe_cf": mean_diffs["rpe_cf"] > 0.0,
        "fwer_uniform_cf_le_alpha": p_fwer[0] <= PROTOCOL["alpha_familywise"],
        "fwer_rpe_cf_le_alpha": p_fwer[1] <= PROTOCOL["alpha_familywise"],
        "proxy_noninferior_to_rpe": proxy_primary + PROTOCOL["proxy_noninferiority_margin"] >= proxy_rpe,
        "descendant_budget_superiority": desc_superiority >= PROTOCOL["min_descendant_budget_superiority"],
        "recall_not_below_uniform_cf": summary[primary]["invariant_recall"] >= summary["uniform_cf"]["invariant_recall"],
        "recall_not_below_rpe_cf": summary[primary]["invariant_recall"] >= summary["rpe_cf"]["invariant_recall"],
        "false_credit_within_uniform_margin": summary[primary]["false_credit_rate"] <= summary["uniform_cf"]["false_credit_rate"] + PROTOCOL["false_credit_margin"],
        "false_credit_within_rpe_margin": summary[primary]["false_credit_rate"] <= summary["rpe_cf"]["false_credit_rate"] + PROTOCOL["false_credit_margin"],
        "non_authorizing": PROTOCOL["via_ascension_authority"] is False and PROTOCOL["biological_claim_authority"] is False,
    }
    qualified = all(checks.values())
    verdict_name = "CAUSAL_DEBT_V2_CONTROL_QUALIFIED" if qualified else "CAUSAL_DEBT_V2_CONTROL_NOT_QUALIFIED"
    verdict = {
        "schema": "cwc-cdl-v2/verdict-1",
        "verdict": verdict_name,
        "control_qualification": qualified,
        "scientific_pass": False,
        "via_ascension_authorized": False,
        "biological_claim_authorized": False,
        "parent_verdict": PROTOCOL["parent_verdict"],
        "primary_policy": primary,
        "matched_cf_controls": controls,
        "mean_paired_oos_difference": mean_diffs,
        "paired_fwer_p": dict(zip(controls, p_fwer, strict=True)),
        "aggregate": summary,
        "variant_summary": variant_summary,
        "descendant_budget_superiority_count": desc_superiority,
        "budget_summary": budget_summary,
        "checks": checks,
        "scope": "synthetic SCM control only",
    }
    path = OUT / "verdict.json"
    path.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    (OUT / "SHA256SUMS.verdict").write_text(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  verdict.json\n")
    print(json.dumps({
        "verdict": verdict_name,
        "mean_paired_oos_difference": mean_diffs,
        "paired_fwer_p": verdict["paired_fwer_p"],
        "descendant_budget_superiority_count": desc_superiority,
        "checks": checks,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

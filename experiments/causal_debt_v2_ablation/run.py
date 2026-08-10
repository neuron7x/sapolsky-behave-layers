"""Post-confirmatory mechanism ablation for CDL V2.

This experiment is explicitly exploratory and cannot upgrade the preregistered V2
claim. It decomposes candidate scheduling from context-coverage scheduling.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from cwc.memory.causal_debt import CausalDebtLedger, ReplayEvidence
from cwc.replay.scheduler import choose_candidate, choose_least_covered_context
from experiments.causal_debt_v2.run import (
    PROTOCOL as V2,
    _evaluate,
    counterfactual_probe,
    observational_effect,
    sample_unit,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "causal-debt-v2-ablation"
POLICIES = {
    "debt_balanced": ("causal_debt_v2_cf", True),
    "debt_randomctx": ("causal_debt_v2_cf", False),
    "uniform_balanced": ("uniform_cf", True),
    "uniform_random": ("uniform_cf", False),
    "rpe_balanced": ("rpe_cf", True),
    "rpe_random": ("rpe_cf", False),
}


def _weights(base_policy: str, balanced: bool, *, variant: str, obs: dict[str, float], budget: int, rng: random.Random):
    contexts = tuple(V2["evaluation_regimes"])
    ledger = CausalDebtLedger(min_replays=3, min_contexts=2, min_abs_credit=0.15, z_value=1.64)
    for cid, value in obs.items():
        ledger.register(cid, eligibility=abs(value), observational_credit=value)
    counts = {cid: 0 for cid in ledger.candidate_ids}
    for step in range(budget):
        cid = choose_candidate(
            base_policy,
            ledger=ledger,
            observational_strength=obs,
            replay_counts=counts,
            rng=rng,
            fifo_index=step,
        )
        context = choose_least_covered_context(
            cid,
            contexts=contexts,
            ledger=ledger,
            rng=rng,
            randomize=not balanced,
        )
        unit = sample_unit(rng, variant=variant, context=context)
        probe = counterfactual_probe(unit, cid)
        ledger.append(ReplayEvidence(cid, context, probe.signed_effect, surprise=abs(probe.signed_effect)))
        counts[cid] += 1
    weights = {}
    for cid in ledger.candidate_ids:
        decision = ledger.consolidation(cid)
        if decision.consolidated:
            weights[cid] = decision.credit
    return weights


def run_cell(seed: int, budget: int, variant: str, label: str) -> dict[str, object]:
    acquisition_rng = random.Random(seed * 100_003 + (17 if variant == "proxy" else 19))
    eval_rng = random.Random(seed * 100_003 + (29 if variant == "proxy" else 31))
    policy_rng = random.Random(seed * 7_000_003 + budget * 1013 + sum(map(ord, label + variant)))
    acquisition = [sample_unit(acquisition_rng, variant=variant, context="same") for _ in range(V2["acquisition_samples"])]
    eval_sets = {
        ctx: [sample_unit(eval_rng, variant=variant, context=ctx) for _ in range(V2["evaluation_samples_per_regime"])]
        for ctx in V2["evaluation_regimes"]
    }
    obs = {cid: observational_effect(acquisition, cid) for cid in V2["candidates"]}
    base, balanced = POLICIES[label]
    weights = _weights(base, balanced, variant=variant, obs=obs, budget=budget, rng=policy_rng)
    acc = _evaluate(weights, eval_sets)
    return {
        "seed": seed,
        "budget": budget,
        "variant": variant,
        "policy": label,
        "accuracy": acc,
        "recall": int("C" in weights),
        "false_credit": int("S" in weights or "N" in weights),
    }


def main() -> int:
    rows = [
        run_cell(seed, budget, variant, label)
        for seed in V2["seeds"]
        for budget in V2["replay_budgets"]
        for variant in V2["environment_variants"]
        for label in POLICIES
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / "raw_results.jsonl"
    raw.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    summary = {}
    for label in POLICIES:
        cell = [r for r in rows if r["policy"] == label]
        summary[label] = {
            "mean_oos": sum(r["accuracy"]["oos"] for r in cell) / len(cell),
            "recall": sum(r["recall"] for r in cell) / len(cell),
            "false_credit": sum(r["false_credit"] for r in cell) / len(cell),
        }
    result = {
        "schema": "cwc-cdl-v2/ablation-1",
        "confirmatory": False,
        "claim_upgrade_authority": False,
        "rows": len(rows),
        "summary": summary,
        "contrasts": {
            "context_coverage_with_debt": summary["debt_balanced"]["mean_oos"] - summary["debt_randomctx"]["mean_oos"],
            "debt_vs_rpe_random_context": summary["debt_randomctx"]["mean_oos"] - summary["rpe_random"]["mean_oos"],
            "debt_vs_uniform_random_context": summary["debt_randomctx"]["mean_oos"] - summary["uniform_random"]["mean_oos"],
            "context_coverage_with_uniform": summary["uniform_balanced"]["mean_oos"] - summary["uniform_random"]["mean_oos"],
            "context_coverage_with_rpe": summary["rpe_balanced"]["mean_oos"] - summary["rpe_random"]["mean_oos"],
        },
    }
    verdict = OUT / "ablation.json"
    verdict.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUT / "SHA256SUMS").write_text(
        "\n".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
            for p in (raw, verdict)
        ) + "\n"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

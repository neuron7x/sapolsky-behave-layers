"""Execute the preregistered resolution-aware causal-debt V2 benchmark."""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from cwc.memory.causal_debt import CausalDebtLedger, ReplayEvidence
from cwc.replay.perturb import CounterfactualProbe
from cwc.replay.scheduler import choose_candidate, choose_least_covered_context

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "causal-debt-v2"
PROTOCOL = json.loads((HERE / "protocol.json").read_text())


@dataclass(frozen=True, slots=True)
class Unit:
    variant: str
    context: str
    c: int
    s: int
    n: int
    outcome_noise: int

    @property
    def y(self) -> int:
        return self.c ^ self.outcome_noise

    def feature(self, candidate: str) -> int:
        return {"C": self.c, "S": self.s, "N": self.n}[candidate]


def _bern(rng: random.Random, p: float) -> int:
    return int(rng.random() < p)


def sample_unit(rng: random.Random, *, variant: str, context: str) -> Unit:
    c = _bern(rng, 0.5)
    n = _bern(rng, 0.5)
    outcome_noise = _bern(rng, 0.10)
    y = c ^ outcome_noise

    if variant == "proxy":
        flip = {"same": 0.05, "decorrelated": 0.50, "reversed": 0.95}[context]
        s = c ^ _bern(rng, flip)
    elif variant == "descendant":
        if context == "same":
            s = y ^ _bern(rng, 0.02)
        elif context == "decorrelated":
            s = _bern(rng, 0.5)
        elif context == "reversed":
            s = (1 - y) ^ _bern(rng, 0.02)
        else:
            raise ValueError(context)
    else:
        raise ValueError(variant)
    return Unit(variant=variant, context=context, c=c, s=s, n=n, outcome_noise=outcome_noise)


def observational_effect(units: list[Unit], candidate: str) -> float:
    return sum((2 * u.feature(candidate) - 1) * (2 * u.y - 1) for u in units) / len(units)


def counterfactual_probe(unit: Unit, candidate: str) -> CounterfactualProbe:
    factual = unit.y
    if candidate == "C":
        cf_outcome = (1 - unit.c) ^ unit.outcome_noise
    elif candidate in {"S", "N"}:
        cf_outcome = factual
    else:
        raise ValueError(candidate)
    effect = float((factual - cf_outcome) * (2 * unit.feature(candidate) - 1))
    return CounterfactualProbe(candidate, unit.context, factual, cf_outcome, effect)


def _predict(unit: Unit, weights: dict[str, float]) -> int:
    score = 0.0
    for cid, direction in weights.items():
        if direction:
            score += math.copysign(1.0, direction) * (2 * unit.feature(cid) - 1)
    return int(score > 0.0)


def _evaluate(weights: dict[str, float], eval_sets: dict[str, list[Unit]]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for context, units in eval_sets.items():
        metrics[context] = sum(_predict(u, weights) == u.y for u in units) / len(units)
    metrics["oos"] = (metrics["decorrelated"] + metrics["reversed"]) / 2.0
    return metrics


def _cf_weights(
    policy: str,
    *,
    variant: str,
    observational_strength: dict[str, float],
    budget: int,
    rng: random.Random,
) -> tuple[dict[str, float], dict[str, dict[str, object]]]:
    contexts = tuple(PROTOCOL["evaluation_regimes"])
    ledger = CausalDebtLedger(min_replays=3, min_contexts=2, min_abs_credit=0.15, z_value=1.64)
    for cid, obs in observational_strength.items():
        ledger.register(cid, eligibility=abs(obs), observational_credit=obs)
    counts = {cid: 0 for cid in ledger.candidate_ids}

    for step in range(budget):
        cid = choose_candidate(
            policy,
            ledger=ledger,
            observational_strength=observational_strength,
            replay_counts=counts,
            rng=rng,
            fifo_index=step,
        )
        context = choose_least_covered_context(
            cid,
            contexts=contexts,
            ledger=ledger,
            rng=rng,
            randomize=policy != "causal_debt_v2_cf",
        )
        unit = sample_unit(rng, variant=variant, context=context)
        probe = counterfactual_probe(unit, cid)
        ledger.append(ReplayEvidence(cid, context, probe.signed_effect, surprise=abs(probe.signed_effect)))
        counts[cid] += 1

    weights: dict[str, float] = {}
    snapshots: dict[str, dict[str, object]] = {}
    for cid in ledger.candidate_ids:
        decision = ledger.consolidation(cid)
        snap = ledger.snapshot(cid)
        snapshots[cid] = {
            "replays": snap.replay_count,
            "contexts": snap.context_count,
            "causal_credit": snap.causal_credit,
            "lower_confidence": snap.lower_confidence,
            "invariance": snap.invariance,
            "v1_debt": snap.debt,
            "v2_debt": ledger.resolution_aware_debt(cid),
            "consolidated": decision.consolidated,
            "reason": decision.reason,
        }
        if decision.consolidated:
            weights[cid] = decision.credit
    return weights, snapshots


def run_cell(seed: int, budget: int, variant: str, policy: str) -> dict[str, object]:
    acquisition_rng = random.Random(seed * 100_003 + (17 if variant == "proxy" else 19))
    eval_rng = random.Random(seed * 100_003 + (29 if variant == "proxy" else 31))
    policy_rng = random.Random(seed * 1_000_003 + budget * 1009 + sum(map(ord, policy + variant)))

    acquisition = [
        sample_unit(acquisition_rng, variant=variant, context="same")
        for _ in range(PROTOCOL["acquisition_samples"])
    ]
    eval_sets = {
        ctx: [
            sample_unit(eval_rng, variant=variant, context=ctx)
            for _ in range(PROTOCOL["evaluation_samples_per_regime"])
        ]
        for ctx in PROTOCOL["evaluation_regimes"]
    }
    obs = {cid: observational_effect(acquisition, cid) for cid in PROTOCOL["candidates"]}

    snapshots = None
    if policy == "oracle_invariant":
        weights = {"C": 1.0}
    else:
        weights, snapshots = _cf_weights(
            policy,
            variant=variant,
            observational_strength=obs,
            budget=budget,
            rng=policy_rng,
        )
    metrics = _evaluate(weights, eval_sets)
    consolidated = set(weights)
    return {
        "seed": seed,
        "budget": budget,
        "variant": variant,
        "policy": policy,
        "observational_strength": obs,
        "weights": weights,
        "false_credit": int("S" in consolidated or "N" in consolidated),
        "invariant_recall": int("C" in consolidated),
        "accuracy": metrics,
        "snapshots": snapshots,
    }


def main() -> int:
    parent = json.loads((ROOT / "artifacts/causal-debt-v1/verdict.json").read_text())
    if parent.get("verdict") != PROTOCOL["parent_verdict"]:
        raise SystemExit("binding V1 parent verdict changed")
    policies = [PROTOCOL["primary_policy"], *PROTOCOL["matched_cf_controls"], PROTOCOL["oracle_reference"]]
    rows = [
        run_cell(seed, budget, variant, policy)
        for seed in PROTOCOL["seeds"]
        for budget in PROTOCOL["replay_budgets"]
        for variant in PROTOCOL["environment_variants"]
        for policy in policies
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / "raw_results.jsonl"
    raw.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    manifest = {
        "schema": "cwc-cdl-v2/raw-manifest-1",
        "row_count": len(rows),
        "policies": policies,
        "seeds": PROTOCOL["seeds"],
        "budgets": PROTOCOL["replay_budgets"],
        "variants": PROTOCOL["environment_variants"],
        "scope": "synthetic SCM control only",
        "parent_verdict": parent["verdict"],
        "via_ascension_authority": False,
    }
    mp = OUT / "manifest.json"
    mp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}" for p in (raw, mp)]
    (OUT / "SHA256SUMS.raw").write_text("\n".join(lines) + "\n")
    print(json.dumps({"rows": len(rows), "artifact": str(raw.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the preregistered synthetic deferred-causal-credit benchmark."""
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
OUT = ROOT / "artifacts" / "causal-debt-v1"
PROTOCOL = json.loads((HERE / "protocol.json").read_text())


@dataclass(frozen=True, slots=True)
class Unit:
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


def _bernoulli(rng: random.Random, p: float) -> int:
    return int(rng.random() < p)


def sample_unit(rng: random.Random, context: str) -> Unit:
    c = _bernoulli(rng, 0.5)
    n = _bernoulli(rng, 0.5)
    if context == "same":
        spur_flip = _bernoulli(rng, 0.05)
    elif context == "decorrelated":
        spur_flip = _bernoulli(rng, 0.5)
    elif context == "reversed":
        spur_flip = _bernoulli(rng, 0.95)
    else:
        raise ValueError(context)
    s = c ^ spur_flip
    outcome_noise = _bernoulli(rng, 0.10)
    return Unit(context=context, c=c, s=s, n=n, outcome_noise=outcome_noise)


def observational_effect(units: list[Unit], candidate: str) -> float:
    values = []
    for unit in units:
        x_signed = 2 * unit.feature(candidate) - 1
        y_signed = 2 * unit.y - 1
        values.append(float(x_signed * y_signed))
    return sum(values) / len(values)


def counterfactual_probe(unit: Unit, candidate: str) -> CounterfactualProbe:
    factual = unit.y
    if candidate == "C":
        cf_outcome = (1 - unit.c) ^ unit.outcome_noise
    elif candidate in {"S", "N"}:
        # S and N are not parents of Y in the frozen SCM.
        cf_outcome = factual
    else:
        raise ValueError(candidate)
    x_signed = 2 * unit.feature(candidate) - 1
    signed_effect = float((factual - cf_outcome) * x_signed)
    return CounterfactualProbe(
        candidate_id=candidate,
        context_id=unit.context,
        factual_outcome=factual,
        counterfactual_outcome=cf_outcome,
        signed_effect=signed_effect,
    )


def _predict(features: Unit, weights: dict[str, float]) -> int:
    # Equal-authority voting intentionally exposes false consolidation instead of
    # allowing a slightly larger observational coefficient to hide it.
    score = 0.0
    for candidate, signed_direction in weights.items():
        if signed_direction == 0.0:
            continue
        score += math.copysign(1.0, signed_direction) * (2 * features.feature(candidate) - 1)
    return int(score > 0.0)


def _evaluate(weights: dict[str, float], eval_sets: dict[str, list[Unit]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for context, units in eval_sets.items():
        correct = sum(_predict(unit, weights) == unit.y for unit in units)
        out[context] = correct / len(units)
    out["oos"] = (out["decorrelated"] + out["reversed"]) / 2.0
    return out


def _observational_policy_weights(
    policy: str,
    *,
    acquisition: list[Unit],
    observational_strength: dict[str, float],
    budget: int,
    rng: random.Random,
) -> dict[str, float]:
    candidate_ids = tuple(sorted(observational_strength))
    samples: dict[str, list[float]] = {cid: [] for cid in candidate_ids}
    counts = {cid: 0 for cid in candidate_ids}
    ledger = CausalDebtLedger()
    for cid in candidate_ids:
        ledger.register(cid, eligibility=abs(observational_strength[cid]), observational_credit=observational_strength[cid])

    for step in range(budget):
        cid = choose_candidate(
            policy,
            ledger=ledger,
            observational_strength=observational_strength,
            replay_counts=counts,
            rng=rng,
            fifo_index=step,
        )
        unit = rng.choice(acquisition)
        x_signed = 2 * unit.feature(cid) - 1
        y_signed = 2 * unit.y - 1
        samples[cid].append(float(x_signed * y_signed))
        counts[cid] += 1

    weights: dict[str, float] = {}
    for cid in candidate_ids:
        # Eligibility is already known from the acquisition phase. Replay may refine
        # it but cannot transform observational association into causal authority.
        estimate = (
            sum(samples[cid]) / len(samples[cid])
            if samples[cid]
            else observational_strength[cid]
        )
        if abs(estimate) >= 0.15 and abs(observational_strength[cid]) >= 0.15:
            weights[cid] = estimate
    return weights


def _counterfactual_policy_weights(
    policy: str,
    *,
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
            randomize=policy != "causal_debt_cf",
        )
        unit = sample_unit(rng, context)
        probe = counterfactual_probe(unit, cid)
        surprise = abs(probe.factual_outcome - int(probe.factual_outcome == probe.counterfactual_outcome))
        ledger.append(
            ReplayEvidence(
                candidate_id=cid,
                context_id=context,
                effect=probe.signed_effect,
                surprise=float(surprise),
            )
        )
        counts[cid] += 1

    weights: dict[str, float] = {}
    snapshots: dict[str, dict[str, object]] = {}
    for cid in ledger.candidate_ids:
        snap = ledger.snapshot(cid)
        decision = ledger.consolidation(cid)
        snapshots[cid] = {
            "eligibility": snap.eligibility,
            "observational_credit": snap.observational_credit,
            "causal_credit": snap.causal_credit,
            "uncertainty": snap.uncertainty,
            "lower_confidence": snap.lower_confidence,
            "context_count": snap.context_count,
            "replay_count": snap.replay_count,
            "invariance": snap.invariance,
            "debt": snap.debt,
            "consolidated": snap.consolidated,
            "reason": decision.reason,
        }
        if decision.consolidated:
            weights[cid] = decision.credit
    return weights, snapshots


def run_cell(seed: int, budget: int, policy: str) -> dict[str, object]:
    # Separate deterministic streams prevent one policy's scheduling from changing
    # another policy's acquisition/evaluation samples.
    acquisition_rng = random.Random(seed * 100_003 + 17)
    eval_rng = random.Random(seed * 100_003 + 29)
    policy_rng = random.Random(seed * 1_000_003 + budget * 1009 + sum(map(ord, policy)))

    acquisition = [sample_unit(acquisition_rng, "same") for _ in range(PROTOCOL["acquisition_samples"])]
    eval_sets = {
        context: [sample_unit(eval_rng, context) for _ in range(PROTOCOL["evaluation_samples_per_regime"])]
        for context in PROTOCOL["evaluation_regimes"]
    }
    obs = {cid: observational_effect(acquisition, cid) for cid in PROTOCOL["candidates"]}

    snapshots: dict[str, dict[str, object]] | None = None
    if policy == "oracle_invariant":
        weights = {"C": 1.0}
    elif policy.endswith("_obs"):
        weights = _observational_policy_weights(
            policy,
            acquisition=acquisition,
            observational_strength=obs,
            budget=budget,
            rng=policy_rng,
        )
    elif policy.endswith("_cf"):
        weights, snapshots = _counterfactual_policy_weights(
            policy,
            observational_strength=obs,
            budget=budget,
            rng=policy_rng,
        )
    else:
        raise ValueError(policy)

    metrics = _evaluate(weights, eval_sets)
    consolidated = set(weights)
    return {
        "seed": seed,
        "budget": budget,
        "policy": policy,
        "observational_strength": obs,
        "weights": weights,
        "consolidated": sorted(consolidated),
        "false_credit": int("S" in consolidated or "N" in consolidated),
        "invariant_recall": int("C" in consolidated),
        "credit_margin": abs(weights.get("C", 0.0)) - max(abs(weights.get("S", 0.0)), abs(weights.get("N", 0.0))),
        "accuracy": metrics,
        "snapshots": snapshots,
    }


def main() -> int:
    rows = [
        run_cell(seed, budget, policy)
        for seed in PROTOCOL["seeds"]
        for budget in PROTOCOL["replay_budgets"]
        for policy in PROTOCOL["policies"]
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / "raw_results.jsonl"
    raw.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    manifest = {
        "schema": "cwc-cdl/raw-manifest-1",
        "row_count": len(rows),
        "seeds": PROTOCOL["seeds"],
        "budgets": PROTOCOL["replay_budgets"],
        "policies": PROTOCOL["policies"],
        "scope": "synthetic SCM control only",
        "via_ascension_authority": False,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    sums = []
    for path in (raw, OUT / "manifest.json"):
        sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (OUT / "SHA256SUMS.raw").write_text("\n".join(sums) + "\n")
    print(json.dumps({"rows": len(rows), "artifact": str(raw.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

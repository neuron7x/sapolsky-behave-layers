from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random
from typing import Iterable, Mapping, Sequence

import numpy as np

from cwc.counterfactual.adequacy import InterventionProbe, InterventionSupport, evaluate_intervention_adequacy
from cwc.counterfactual.model import CANDIDATES, fit_counterfactual_ensemble
from cwc.credit.estimator import estimate_credit_envelope
from cwc.inference.abstention import AbstentionPolicy, decide_causal_authority

TRAIN_N = 256
SUPPORT_N_PER_CANDIDATE = 64
EVAL_N = 128
BOOTSTRAPS_PER_FAMILY = 4
NOISE_SD = 0.15

CALIBRATION_FAMILIES = (
    "M0_CORRECT_STRUCTURE",
    "M1_SPURIOUS_EDGE",
    "M2_MISSING_TRUE_EDGE",
    "M3_WRONG_COEFFICIENT",
    "M4_SIGN_ERROR",
    "M5_NONLINEAR_INTERACTION",
    "N0_ZERO_CAUSE",
)
CONFIRMATORY_FAMILIES = (
    "M6_REDUNDANT_CAUSES",
    "M7_SYNERGISTIC_CAUSES",
    "M8_VARIABLE_DELAY",
    "M9_LATENT_CONFOUNDER_SHIFT",
    "M10_CONTEXT_DEPENDENT_CAUSALITY",
    "M11_SHARED_MODEL_CLASS_MISSPECIFICATION",
    "N0_ZERO_CAUSE",
)

TRUE_CAUSAL_SETS = {
    "M0_CORRECT_STRUCTURE": {"A"},
    "M1_SPURIOUS_EDGE": {"A"},
    "M2_MISSING_TRUE_EDGE": {"A"},
    "M3_WRONG_COEFFICIENT": {"A"},
    "M4_SIGN_ERROR": {"A"},
    "M5_NONLINEAR_INTERACTION": {"A", "C", "D"},
    "M6_REDUNDANT_CAUSES": {"A", "B"},
    "M7_SYNERGISTIC_CAUSES": {"A", "B"},
    "M8_VARIABLE_DELAY": {"A", "B"},
    "M9_LATENT_CONFOUNDER_SHIFT": {"A"},
    "M10_CONTEXT_DEPENDENT_CAUSALITY": {"A", "D"},
    "M11_SHARED_MODEL_CLASS_MISSPECIFICATION": {"A"},
    "N0_ZERO_CAUSE": set(),
}

FAULTS = {
    "M2_MISSING_TRUE_EDGE": "MISSING_TRUE_EDGE",
    "M3_WRONG_COEFFICIENT": "WRONG_COEFFICIENT",
    "M4_SIGN_ERROR": "SIGN_ERROR",
    "M11_SHARED_MODEL_CLASS_MISSPECIFICATION": "SHARED_SPURIOUS_EDGE",
}


@dataclass(frozen=True, slots=True)
class CaseData:
    seed: int
    family: str
    train_rows: tuple[dict[str, float], ...]
    train_y: tuple[float, ...]
    support: InterventionSupport
    eval_rows: tuple[dict[str, float], ...]
    eval_y: tuple[float, ...]
    true_causal_set: tuple[str, ...]
    model_fault: str
    data_version: str


@dataclass(frozen=True, slots=True)
class RawCaseMetrics:
    seed: int
    family: str
    true_causal_set: tuple[str, ...]
    provisional_candidate: str
    no_abstention_false_authority: bool
    no_abstention_correct: bool
    mean_false_credit_mass: float
    rank_stability: float
    model_disagreement: float
    context_stability: float
    intervention_nrmse: float
    ood_score: float
    min_intervention_support: int
    max_observed_effect: float
    factual_rmse: float
    credit_intervals: dict[str, dict[str, float]]
    observed_effect_magnitudes: dict[str, float]
    structural_evaluations: int
    epistemic_uncertainty: dict[str, float]


def stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _draw_binary(rng: random.Random, p_positive: float = 0.5) -> float:
    return 1.0 if rng.random() < p_positive else -1.0


def _observed_row(seed: int, family: str, phase: str, index: int) -> dict[str, float]:
    rng = random.Random(stable_seed(seed, family, phase, index, "row"))
    A = _draw_binary(rng)
    U = _draw_binary(rng)

    if family in {"M2_MISSING_TRUE_EDGE", "M11_SHARED_MODEL_CLASS_MISSPECIFICATION"}:
        C = A if rng.random() < 0.97 else -A
    elif family == "M9_LATENT_CONFOUNDER_SHIFT" and phase != "train":
        C = -U if rng.random() < 0.92 else U
    else:
        C = U if rng.random() < 0.92 else -U

    B = A if rng.random() < 0.80 else -A
    D = _draw_binary(rng)
    if family == "M8_VARIABLE_DELAY":
        context = _draw_binary(rng, p_positive=0.20)  # -1 chooses A 80% of the time
    elif family == "M10_CONTEXT_DEPENDENT_CAUSALITY":
        context = _draw_binary(rng, p_positive=0.25)  # -1 chooses A 75% of the time
    else:
        context = _draw_binary(rng)
    return {"A": A, "C": C, "D": D, "B": B, "context": context, "U": U}


def structural_mean(row: Mapping[str, float], family: str) -> float:
    A, C, D, B = (float(row[name]) for name in CANDIDATES)
    context = float(row["context"])
    U = float(row.get("U", 0.0))
    if family == "M0_CORRECT_STRUCTURE":
        return A + 0.15 * context
    if family == "M1_SPURIOUS_EDGE":
        return A + 1.8 * U
    if family in {"M2_MISSING_TRUE_EDGE", "M3_WRONG_COEFFICIENT", "M4_SIGN_ERROR", "M11_SHARED_MODEL_CLASS_MISSPECIFICATION"}:
        return A
    if family == "M5_NONLINEAR_INTERACTION":
        return 1.0 * A * C + 0.25 * D
    if family == "M6_REDUNDANT_CAUSES":
        return 1.0 * A + 0.30 * B
    if family == "M7_SYNERGISTIC_CAUSES":
        return 1.10 * A * B
    if family == "M8_VARIABLE_DELAY":
        return A if context < 0 else B
    if family == "M9_LATENT_CONFOUNDER_SHIFT":
        return A + 1.8 * U
    if family == "M10_CONTEXT_DEPENDENT_CAUSALITY":
        return A if context < 0 else D
    if family == "N0_ZERO_CAUSE":
        return 1.8 * U
    raise KeyError(family)


def _factual_outcome(row: Mapping[str, float], family: str, *, seed: int, phase: str, index: int) -> float:
    rng = random.Random(stable_seed(seed, family, phase, index, "outcome-noise"))
    return structural_mean(row, family) + rng.gauss(0.0, NOISE_SD)


def _intervention_support(seed: int, family: str) -> InterventionSupport:
    probes: list[InterventionProbe] = []
    for candidate in CANDIDATES:
        for index in range(SUPPORT_N_PER_CANDIDATE):
            base = _observed_row(seed, family, "support", index + 1000 * CANDIDATES.index(candidate))
            plus = dict(base)
            minus = dict(base)
            plus[candidate] = 1.0
            minus[candidate] = -1.0
            half_effect = 0.5 * (structural_mean(plus, family) - structural_mean(minus, family))
            probes.append(InterventionProbe(candidate, base, half_effect))
    return InterventionSupport(tuple(probes))


def generate_case(seed: int, family: str) -> CaseData:
    if family not in TRUE_CAUSAL_SETS:
        raise KeyError(family)
    train_rows = tuple(_observed_row(seed, family, "train", i) for i in range(TRAIN_N))
    train_y = tuple(_factual_outcome(row, family, seed=seed, phase="train", index=i) for i, row in enumerate(train_rows))
    eval_rows = tuple(_observed_row(seed, family, "eval", i) for i in range(EVAL_N))
    eval_y = tuple(_factual_outcome(row, family, seed=seed, phase="eval", index=i) for i, row in enumerate(eval_rows))
    version_payload = json.dumps({"seed": seed, "family": family, "train_n": TRAIN_N, "support_n": SUPPORT_N_PER_CANDIDATE, "eval_n": EVAL_N}, sort_keys=True)
    return CaseData(
        seed=seed,
        family=family,
        train_rows=train_rows,
        train_y=train_y,
        support=_intervention_support(seed, family),
        eval_rows=eval_rows,
        eval_y=eval_y,
        true_causal_set=tuple(sorted(TRUE_CAUSAL_SETS[family])),
        model_fault=FAULTS.get(family, "NONE"),
        data_version=hashlib.sha256(version_payload.encode()).hexdigest(),
    )


def evaluate_raw_case(case: CaseData) -> RawCaseMetrics:
    models = fit_counterfactual_ensemble(
        case.train_rows,
        case.train_y,
        seed=case.seed,
        fault=case.model_fault,
        bootstraps_per_family=BOOTSTRAPS_PER_FAMILY,
    )
    predictions = np.mean(np.asarray([m.predict(case.eval_rows) for m in models], dtype=float), axis=0)
    factual_rmse = float(np.sqrt(np.mean((predictions - np.asarray(case.eval_y, dtype=float)) ** 2)))
    residual_sd = float(np.std(np.asarray(case.eval_y, dtype=float) - predictions))
    envelope = estimate_credit_envelope(
        models,
        case.eval_rows,
        case.support,
        data_version=case.data_version,
        factual_residual_sd=residual_sd,
    )
    credits = {item.candidate: item for item in envelope.credits}
    total_credit = sum(item.mean_abs_credit for item in envelope.credits)
    false_credit = sum(item.mean_abs_credit for item in envelope.credits if item.candidate not in case.true_causal_set)
    false_credit_mass = 0.0 if total_credit <= 1e-12 else false_credit / total_credit
    no_abstain_correct = envelope.provisional_candidate in case.true_causal_set
    return RawCaseMetrics(
        seed=case.seed,
        family=case.family,
        true_causal_set=case.true_causal_set,
        provisional_candidate=envelope.provisional_candidate,
        no_abstention_false_authority=not no_abstain_correct,
        no_abstention_correct=no_abstain_correct,
        mean_false_credit_mass=float(false_credit_mass),
        rank_stability=envelope.rank_stability,
        model_disagreement=envelope.model_disagreement,
        context_stability=envelope.context_stability,
        intervention_nrmse=envelope.intervention_nrmse,
        ood_score=envelope.ood_score,
        min_intervention_support=min(envelope.intervention_support.values()),
        max_observed_effect=max(envelope.observed_effect_magnitudes.values()),
        factual_rmse=factual_rmse,
        credit_intervals={
            name: {
                "mean": credits[name].mean_abs_credit,
                "lower": credits[name].lower,
                "upper": credits[name].upper,
                "mean_signed": credits[name].mean_signed_credit,
                "sign_stability": credits[name].sign_stability,
            }
            for name in CANDIDATES
        },
        observed_effect_magnitudes=dict(envelope.observed_effect_magnitudes),
        structural_evaluations=len(models) * EVAL_N * 15,  # polynomial exact-Shapley term accounting proxy
        epistemic_uncertainty=dict(envelope.epistemic_uncertainty),
    )


def raw_case_to_envelope_proxy(raw: RawCaseMetrics):
    """Rebuild the immutable decision surface without refitting models during policy search."""
    from cwc.counterfactual.uncertainty import CounterfactualPredictionEnvelope, CreditInterval

    credits = tuple(
        CreditInterval(
            candidate=name,
            mean_abs_credit=raw.credit_intervals[name]["mean"],
            lower=raw.credit_intervals[name]["lower"],
            upper=raw.credit_intervals[name]["upper"],
            mean_signed_credit=raw.credit_intervals[name]["mean_signed"],
            sign_stability=raw.credit_intervals[name]["sign_stability"],
        )
        for name in CANDIDATES
    )
    return CounterfactualPredictionEnvelope(
        prediction={name: raw.credit_intervals[name]["mean"] for name in CANDIDATES},
        epistemic_uncertainty=dict(raw.epistemic_uncertainty),
        aleatoric_uncertainty={"factual_residual_sd": raw.factual_rmse},
        training_support={"rows": TRAIN_N},
        intervention_support={name: raw.min_intervention_support for name in CANDIDATES},
        ood_score=raw.ood_score,
        model_family=("SUMMARY",),
        model_version=("SUMMARY",),
        data_version=f"summary:{raw.seed}:{raw.family}",
        credits=credits,
        provisional_candidate=raw.provisional_candidate,
        rank_stability=raw.rank_stability,
        model_disagreement=raw.model_disagreement,
        context_stability=raw.context_stability,
        intervention_nrmse=raw.intervention_nrmse,
        observed_effect_magnitudes=dict(raw.observed_effect_magnitudes),
    )


def decide_raw(raw: RawCaseMetrics, policy: AbstentionPolicy):
    return decide_causal_authority(
        raw_case_to_envelope_proxy(raw),
        policy,
        structural_evaluations=raw.structural_evaluations,
        max_structural_evaluations=100_000,
    )


def score_cases(raw_cases: Sequence[RawCaseMetrics], policy: AbstentionPolicy) -> dict[str, object]:
    accepted = 0
    false_authority = 0
    accepted_correct = 0
    false_mass: list[float] = []
    states: dict[str, int] = {}
    by_family: dict[str, dict[str, int]] = {}
    decisions: list[dict[str, object]] = []
    for raw in raw_cases:
        decision = decide_raw(raw, policy)
        states[decision.state] = states.get(decision.state, 0) + 1
        family = by_family.setdefault(raw.family, {"n": 0, "accepted": 0, "false_authority": 0})
        family["n"] += 1
        is_accept = decision.state == "ACCEPT_CAUSAL_CREDIT"
        is_correct = is_accept and decision.candidate in raw.true_causal_set
        is_false = is_accept and not is_correct
        if is_accept:
            accepted += 1
            family["accepted"] += 1
            false_mass.append(raw.mean_false_credit_mass)
        if is_correct:
            accepted_correct += 1
        if is_false:
            false_authority += 1
            family["false_authority"] += 1
        decisions.append({
            "seed": raw.seed,
            "family": raw.family,
            "state": decision.state,
            "candidate": decision.candidate,
            "reason": decision.reason,
            "true_causal_set": list(raw.true_causal_set),
            "false_authority": is_false,
        })
    n = len(raw_cases)
    no_abstain_false = sum(int(r.no_abstention_false_authority) for r in raw_cases)
    family_rates = {
        name: {
            **stats,
            "coverage": stats["accepted"] / stats["n"],
            "false_authority_rate": stats["false_authority"] / stats["n"],
        }
        for name, stats in sorted(by_family.items())
    }
    return {
        "n": n,
        "accepted": accepted,
        "coverage": accepted / n if n else 0.0,
        "selective_false_causal_authority": false_authority / n if n else 0.0,
        "false_authority_count": false_authority,
        "causal_rank_accuracy_given_accept": accepted_correct / accepted if accepted else 0.0,
        "mean_false_credit_mass_given_accept": float(np.mean(false_mass)) if false_mass else 0.0,
        "no_abstention_false_causal_authority": no_abstain_false / n if n else 0.0,
        "no_abstention_false_count": no_abstain_false,
        "state_counts": states,
        "by_family": family_rates,
        "decisions": decisions,
    }


def serialize_raw(raw: RawCaseMetrics) -> dict[str, object]:
    return asdict(raw)


def policy_to_dict(policy: AbstentionPolicy) -> dict[str, object]:
    return asdict(policy)

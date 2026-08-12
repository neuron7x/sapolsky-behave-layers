from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from .adequacy import AdequacyMetrics
from .model import CANDIDATES, FittedCounterfactualModel


@dataclass(frozen=True, slots=True)
class CreditInterval:
    candidate: str
    mean_abs_credit: float
    lower: float
    upper: float
    mean_signed_credit: float
    sign_stability: float


@dataclass(frozen=True, slots=True)
class CounterfactualPredictionEnvelope:
    prediction: dict[str, float]
    epistemic_uncertainty: dict[str, float]
    aleatoric_uncertainty: dict[str, float]
    training_support: dict[str, int]
    intervention_support: dict[str, int]
    ood_score: float
    model_family: tuple[str, ...]
    model_version: tuple[str, ...]
    data_version: str
    credits: tuple[CreditInterval, ...]
    provisional_candidate: str
    rank_stability: float
    model_disagreement: float
    context_stability: float
    intervention_nrmse: float
    observed_effect_magnitudes: dict[str, float]

    def credit(self, candidate: str) -> CreditInterval:
        for item in self.credits:
            if item.candidate == candidate:
                return item
        raise KeyError(candidate)


def _quantile(values: Sequence[float], q: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), q, method="linear"))


def _top(scores: Mapping[str, float]) -> str:
    return max(CANDIDATES, key=lambda name: (scores[name], -CANDIDATES.index(name)))


def build_prediction_envelope(
    models: Sequence[FittedCounterfactualModel],
    eval_rows: Sequence[Mapping[str, float]],
    adequacy: AdequacyMetrics,
    *,
    data_version: str,
    factual_residual_sd: float,
) -> CounterfactualPredictionEnvelope:
    if not models or not eval_rows:
        raise ValueError("models and evaluation rows are required")
    abs_by_model: list[dict[str, float]] = []
    signed_by_model: list[dict[str, float]] = []
    for model in models:
        abs_credit, signed_credit = model.mean_credit(eval_rows)
        abs_by_model.append(abs_credit)
        signed_by_model.append(signed_credit)

    intervals: list[CreditInterval] = []
    means: dict[str, float] = {}
    for candidate in CANDIDATES:
        values = [entry[candidate] for entry in abs_by_model]
        signed = [entry[candidate] for entry in signed_by_model]
        mean_abs = float(np.mean(values))
        means[candidate] = mean_abs
        signs = [0 if abs(v) <= 1e-12 else (1 if v > 0 else -1) for v in signed]
        nonzero = [s for s in signs if s]
        sign_stability = 1.0 if not nonzero else max(nonzero.count(1), nonzero.count(-1)) / len(nonzero)
        intervals.append(
            CreditInterval(
                candidate=candidate,
                mean_abs_credit=mean_abs,
                lower=max(0.0, _quantile(values, 0.10)),
                upper=_quantile(values, 0.90),
                mean_signed_credit=float(np.mean(signed)),
                sign_stability=float(sign_stability),
            )
        )
    top = _top(means)
    model_tops = [_top(scores) for scores in abs_by_model]
    rank_stability = model_tops.count(top) / len(model_tops)
    top_values = np.asarray([scores[top] for scores in abs_by_model], dtype=float)
    model_disagreement = float(np.std(top_values) / max(np.mean(top_values), 1e-9))

    context_tops: list[str] = []
    for context in (-1.0, 1.0):
        subset = [row for row in eval_rows if float(row.get("context", 1.0)) == context]
        if not subset:
            continue
        scores = dict.fromkeys(CANDIDATES, 0.0)
        for model in models:
            abs_credit, _ = model.mean_credit(subset)
            for name in CANDIDATES:
                scores[name] += abs_credit[name] / len(models)
        context_tops.append(_top(scores))
    context_stability = 1.0 if not context_tops else context_tops.count(top) / len(context_tops)

    # Mean configuration surprisal under every fitted model. This is a data/context OOD
    # signal only; it is intentionally not treated as structural adequacy.
    surprisals = []
    for row in eval_rows:
        probs = [max(model.config_probability(row), 1e-12) for model in models]
        surprisals.append(-math.log(float(np.mean(probs))))
    ood_score = float(np.mean(surprisals))

    family_means: dict[str, list[float]] = {}
    for model, scores in zip(models, abs_by_model, strict=True):
        family_means.setdefault(model.family, []).append(scores[top])
    family_centers = [float(np.mean(v)) for v in family_means.values()]
    family_uncertainty = float(np.std(family_centers))
    within_family = [float(np.std(v)) for v in family_means.values()]

    return CounterfactualPredictionEnvelope(
        prediction=means,
        epistemic_uncertainty={
            "parameter_data": float(np.mean(within_family)),
            "model_family": family_uncertainty,
            "structural_intervention_nrmse": adequacy.median_nrmse,
            "context_ood_surprisal": ood_score,
        },
        aleatoric_uncertainty={"factual_residual_sd": float(factual_residual_sd)},
        training_support={"rows": models[0].train_rows},
        intervention_support=adequacy.support_counts,
        ood_score=ood_score,
        model_family=tuple(model.family for model in models),
        model_version=tuple(model.version for model in models),
        data_version=data_version,
        credits=tuple(intervals),
        provisional_candidate=top,
        rank_stability=float(rank_stability),
        model_disagreement=model_disagreement,
        context_stability=float(context_stability),
        intervention_nrmse=adequacy.median_nrmse,
        observed_effect_magnitudes=adequacy.observed_effect_magnitudes,
    )

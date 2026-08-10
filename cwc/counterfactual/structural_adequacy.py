from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from .model import CANDIDATES, FittedCounterfactualModel


@dataclass(frozen=True, slots=True)
class EmpiricalInterventionProbe:
    candidate: str
    context: float
    base: Mapping[str, float]
    split_effect_a: float
    split_effect_b: float

    @property
    def effect(self) -> float:
        return 0.5 * (self.split_effect_a + self.split_effect_b)


@dataclass(frozen=True, slots=True)
class FamilyInterventionalAudit:
    family: str
    idr: float
    max_cell_idr: float
    effect_rmse: float
    noise_floor_rmse: float
    cells: dict[str, float]
    support_cells: dict[str, int]


@dataclass(frozen=True, slots=True)
class ContextEffectAudit:
    candidate: str
    effect_negative_context: float
    effect_positive_context: float
    absolute_difference: float
    sign_flip: bool
    standardized_difference: float
    support_negative: int
    support_positive: int


@dataclass(frozen=True, slots=True)
class GraphSensitivity:
    candidate: str
    factual_delta_mse: float
    intervention_delta_mse: float


def _group_models(models: Sequence[FittedCounterfactualModel]) -> dict[str, tuple[FittedCounterfactualModel, ...]]:
    grouped: dict[str, list[FittedCounterfactualModel]] = {}
    for model in models:
        grouped.setdefault(model.family, []).append(model)
    return {family: tuple(items) for family, items in grouped.items()}


def _mean_effect(models: Sequence[FittedCounterfactualModel], probe: EmpiricalInterventionProbe) -> float:
    return float(np.mean([model.intervention_effect(probe.base, probe.candidate) for model in models]))


def _cell_key(candidate: str, context: float) -> str:
    return f"{candidate}|ctx={int(context):+d}"


def interventional_divergence_audit(
    models: Sequence[FittedCounterfactualModel],
    probes: Sequence[EmpiricalInterventionProbe],
    *,
    epsilon: float = 1e-12,
) -> tuple[FamilyInterventionalAudit, ...]:
    """Noise-normalized interventional model check.

    IDR is calibrated to the empirical intervention noise floor rather than factual loss.
    For split estimates d1,d2 and their average d, the expected squared error of d due only
    to measurement noise is estimated by 1/4 E[(d1-d2)^2].  Under an interventionally
    correct model IDR should therefore be O(1), with finite-sample thresholds calibrated
    prospectively rather than treated as a universal constant.
    """
    if not models:
        raise ValueError("models required")
    if not probes:
        raise ValueError("probes required")
    grouped = _group_models(models)
    audits: list[FamilyInterventionalAudit] = []
    for family, family_models in sorted(grouped.items()):
        errors = []
        split_noise = []
        cell_errors: dict[str, list[float]] = {}
        cell_noise: dict[str, list[float]] = {}
        for probe in probes:
            prediction = _mean_effect(family_models, probe)
            error = (probe.effect - prediction) ** 2
            noise = 0.25 * (probe.split_effect_a - probe.split_effect_b) ** 2
            errors.append(error)
            split_noise.append(noise)
            key = _cell_key(probe.candidate, probe.context)
            cell_errors.setdefault(key, []).append(error)
            cell_noise.setdefault(key, []).append(noise)
        numerator = float(np.mean(errors))
        denominator = float(np.mean(split_noise))
        idr = numerator / max(denominator, epsilon)
        cells: dict[str, float] = {}
        supports: dict[str, int] = {}
        for key in sorted(cell_errors):
            cells[key] = float(np.mean(cell_errors[key]) / max(denominator, epsilon))
            supports[key] = len(cell_errors[key])
        audits.append(
            FamilyInterventionalAudit(
                family=family,
                idr=idr,
                max_cell_idr=max(cells.values()),
                effect_rmse=float(np.sqrt(numerator)),
                noise_floor_rmse=float(np.sqrt(max(denominator, 0.0))),
                cells=cells,
                support_cells=supports,
            )
        )
    return tuple(audits)


def best_family_audit(audits: Sequence[FamilyInterventionalAudit]) -> FamilyInterventionalAudit:
    if not audits:
        raise ValueError("audits required")
    return min(audits, key=lambda item: (item.max_cell_idr, item.idr, item.family))


def context_effect_audits(probes: Sequence[EmpiricalInterventionProbe], *, epsilon: float = 1e-12) -> tuple[ContextEffectAudit, ...]:
    out: list[ContextEffectAudit] = []
    for candidate in CANDIDATES:
        by_context: dict[float, list[EmpiricalInterventionProbe]] = {-1.0: [], 1.0: []}
        for probe in probes:
            if probe.candidate == candidate and probe.context in by_context:
                by_context[probe.context].append(probe)
        neg = by_context[-1.0]
        pos = by_context[1.0]
        if not neg or not pos:
            continue
        neg_effects = np.asarray([p.effect for p in neg], dtype=float)
        pos_effects = np.asarray([p.effect for p in pos], dtype=float)
        mneg = float(np.mean(neg_effects))
        mpos = float(np.mean(pos_effects))
        var_neg = float(np.var(neg_effects, ddof=1)) if len(neg_effects) > 1 else 0.0
        var_pos = float(np.var(pos_effects, ddof=1)) if len(pos_effects) > 1 else 0.0
        se = float(np.sqrt(var_neg / max(len(neg_effects), 1) + var_pos / max(len(pos_effects), 1)))
        diff = abs(mpos - mneg)
        out.append(
            ContextEffectAudit(
                candidate=candidate,
                effect_negative_context=mneg,
                effect_positive_context=mpos,
                absolute_difference=diff,
                sign_flip=(mneg * mpos < 0.0),
                standardized_difference=diff / max(se, epsilon),
                support_negative=len(neg_effects),
                support_positive=len(pos_effects),
            )
        )
    return tuple(out)


def graph_structural_sensitivity(
    models: Sequence[FittedCounterfactualModel],
    eval_rows: Sequence[Mapping[str, float]],
    eval_y: Sequence[float],
    probes: Sequence[EmpiricalInterventionProbe],
) -> tuple[GraphSensitivity, ...]:
    """Internal edge-ablation sensitivity; diagnostic only, never causal authority.

    The function measures reliance on terms containing a candidate.  Reliance can be high
    for a spurious edge under collinearity, so this surface is intentionally separated from
    interventional adequacy.
    """
    if not models or not eval_rows:
        raise ValueError("models/eval_rows required")
    y = np.asarray(eval_y, dtype=float)
    base_pred = np.mean(np.asarray([m.predict(eval_rows) for m in models], dtype=float), axis=0)
    base_mse = float(np.mean((base_pred - y) ** 2))
    empirical = np.asarray([p.effect for p in probes], dtype=float)
    base_intervention_pred = np.asarray([
        float(np.mean([m.intervention_effect(p.base, p.candidate) for m in models])) for p in probes
    ])
    base_intervention_mse = float(np.mean((base_intervention_pred - empirical) ** 2))
    out = []
    for candidate in CANDIDATES:
        model_preds = []
        intervention_preds = []
        for model in models:
            coefs = np.asarray(model.coefficients, dtype=float).copy()
            for idx, term in enumerate(model.terms):
                if candidate in term.players:
                    coefs[idx] = 0.0
            # direct prediction with ablated coefficients
            pred = np.zeros(len(eval_rows), dtype=float)
            for coef, term in zip(coefs, model.terms, strict=True):
                pred += coef * np.asarray([term.evaluate(r) for r in eval_rows], dtype=float)
            model_preds.append(pred)
            per_probe = []
            for probe in probes:
                if probe.candidate != candidate:
                    per_probe.append(model.intervention_effect(probe.base, probe.candidate))
                    continue
                # all terms involving the ablated candidate are zero -> zero direct effect
                per_probe.append(0.0)
            intervention_preds.append(per_probe)
        pred = np.mean(np.asarray(model_preds), axis=0)
        int_pred = np.mean(np.asarray(intervention_preds), axis=0)
        out.append(GraphSensitivity(
            candidate=candidate,
            factual_delta_mse=float(np.mean((pred - y) ** 2) - base_mse),
            intervention_delta_mse=float(np.mean((int_pred - empirical) ** 2) - base_intervention_mse),
        ))
    return tuple(out)

from __future__ import annotations

from typing import Mapping, Sequence

from cwc.counterfactual.adequacy import InterventionSupport, evaluate_intervention_adequacy
from cwc.counterfactual.model import FittedCounterfactualModel
from cwc.counterfactual.uncertainty import CounterfactualPredictionEnvelope, build_prediction_envelope


def estimate_credit_envelope(
    models: Sequence[FittedCounterfactualModel],
    eval_rows: Sequence[Mapping[str, float]],
    support: InterventionSupport,
    *,
    data_version: str,
    factual_residual_sd: float,
) -> CounterfactualPredictionEnvelope:
    adequacy = evaluate_intervention_adequacy(models, support)
    return build_prediction_envelope(
        models,
        eval_rows,
        adequacy,
        data_version=data_version,
        factual_residual_sd=factual_residual_sd,
    )

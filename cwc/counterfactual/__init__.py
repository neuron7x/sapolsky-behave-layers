"""Counterfactual-model runtime primitives with explicit uncertainty boundaries."""

from .model import FittedCounterfactualModel, fit_counterfactual_ensemble
from .uncertainty import CounterfactualPredictionEnvelope, build_prediction_envelope
from .adequacy import InterventionSupport, evaluate_intervention_adequacy

__all__ = [
    "FittedCounterfactualModel",
    "fit_counterfactual_ensemble",
    "CounterfactualPredictionEnvelope",
    "build_prediction_envelope",
    "InterventionSupport",
    "evaluate_intervention_adequacy",
]

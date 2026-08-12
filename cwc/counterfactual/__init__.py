"""Counterfactual-model runtime primitives with explicit uncertainty boundaries."""

from .adequacy import InterventionSupport, evaluate_intervention_adequacy
from .model import FittedCounterfactualModel, fit_counterfactual_ensemble
from .uncertainty import CounterfactualPredictionEnvelope, build_prediction_envelope

__all__ = [
    "CounterfactualPredictionEnvelope",
    "FittedCounterfactualModel",
    "InterventionSupport",
    "build_prediction_envelope",
    "evaluate_intervention_adequacy",
    "fit_counterfactual_ensemble",
]

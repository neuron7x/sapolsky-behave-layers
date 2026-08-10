"""Inference-side epistemic gates. Active causal control is intentionally absent."""
from .abstention import AbstentionPolicy, decide_causal_authority
from .trace import InferenceTrace

__all__ = ["AbstentionPolicy", "decide_causal_authority", "InferenceTrace"]

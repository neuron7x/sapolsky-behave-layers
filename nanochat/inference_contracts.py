"""Fail-closed contracts for generation inputs and model outputs."""
from __future__ import annotations

import math
from numbers import Real
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    from torch import Tensor


MAX_SEED = 2**63 - 1


def validate_generation_request(
    tokens: Any,
    *,
    num_samples: Any,
    max_tokens: Any,
    temperature: Any,
    top_k: Any,
    seed: Any,
    sequence_len: int,
    vocab_size: int,
) -> None:
    """Reject ambiguous or unsafe generation requests before allocating a KV cache."""
    if not isinstance(tokens, list) or not tokens:
        raise ValueError("tokens must be a non-empty list of token ids")
    if any(not isinstance(token, int) or isinstance(token, bool) for token in tokens):
        raise TypeError("every token id must be an integer")
    if any(token < 0 or token >= vocab_size for token in tokens):
        raise ValueError(f"token ids must be in [0, {vocab_size})")
    if not isinstance(num_samples, int) or isinstance(num_samples, bool) or num_samples < 1:
        raise ValueError("num_samples must be a positive integer")
    if max_tokens is not None and (
        not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 0
    ):
        raise ValueError("max_tokens must be None or a non-negative integer")
    if len(tokens) > sequence_len:
        raise ValueError("prompt exceeds the model sequence length")
    requested = sequence_len - len(tokens) if max_tokens is None else max_tokens
    if len(tokens) + requested > sequence_len:
        raise ValueError("prompt plus max_tokens exceeds the model sequence length")
    if not isinstance(temperature, Real) or isinstance(temperature, bool):
        raise TypeError("temperature must be a real number")
    if not math.isfinite(float(temperature)) or temperature < 0:
        raise ValueError("temperature must be finite and non-negative")
    if top_k is not None and (
        not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 0
    ):
        raise ValueError("top_k must be None or a non-negative integer")
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= MAX_SEED:
        raise ValueError(f"seed must be an integer in [0, {MAX_SEED}]")


def validate_logits(logits: Tensor) -> None:
    """Require a finite, non-empty (batch, vocabulary) sampling surface."""
    if logits.ndim != 2 or logits.shape[0] < 1 or logits.shape[1] < 1:
        raise ValueError("logits must have shape (batch, non-empty vocabulary)")
    if not logits.is_floating_point():
        raise TypeError("logits must use a floating-point dtype")
    if not torch.isfinite(logits).all():
        raise FloatingPointError("logits contain NaN or infinity")

"""In-context associative recall (induction) task generator.

A sequence is a stream of (key, value) pairs, then a query token, then a query
key that appeared earlier; the target at the final position is that key's
most-recent value. Depth is causally load-bearing: solving this needs an
induction-head mechanism composed across specific layers, so *which* blocks
execute matters — the point of the routing experiment.

Deterministic given a seed. No external data.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class TaskConfig:
    vocab_size: int = 64
    seq_len: int = 128
    n_pairs: int = 24
    key_lo: int = 4
    key_hi: int = 34
    value_lo: int = 34
    value_hi: int = 64
    query_token: int = 1
    pad_token: int = 0


def generate_batch(
    cfg: TaskConfig, batch_size: int, generator: torch.Generator, device: str = "cpu"
) -> tuple[torch.Tensor, torch.Tensor]:
    """Returns (inputs, targets), both (batch, seq_len) int64.

    Layout per sequence: [k0 v0 k1 v1 ... k_{n-1} v_{n-1} QUERY qk PAD...],
    target is pad everywhere except the position AFTER qk, which holds the
    most-recent value bound to qk. Loss is masked to that single query position
    (see query_position_mask). Non-query targets are pad_token and masked out.
    """
    n = cfg.n_pairs
    span = 2 * n + 2  # pairs + query_token + query_key
    assert span + 1 <= cfg.seq_len, "seq_len too small for n_pairs"

    inputs = torch.full((batch_size, cfg.seq_len), cfg.pad_token, dtype=torch.long)
    targets = torch.full((batch_size, cfg.seq_len), cfg.pad_token, dtype=torch.long)

    n_keys = cfg.key_hi - cfg.key_lo
    for b in range(batch_size):
        # sample n distinct keys so "most-recent value" is unambiguous per key
        perm = torch.randperm(n_keys, generator=generator)[:n]
        keys = perm + cfg.key_lo
        values = torch.randint(
            cfg.value_lo, cfg.value_hi, (n,), generator=generator
        )
        seq = torch.empty(span, dtype=torch.long)
        seq[0:2 * n:2] = keys
        seq[1:2 * n:2] = values
        seq[2 * n] = cfg.query_token
        qi = int(torch.randint(0, n, (1,), generator=generator).item())
        seq[2 * n + 1] = keys[qi]
        inputs[b, :span] = seq
        # target at the position AFTER the query key = that key's value
        targets[b, span - 1] = values[qi]
    return inputs.to(device), targets.to(device)


def query_position_mask(
    cfg: TaskConfig, batch_size: int, device: str = "cpu"
) -> torch.Tensor:
    """Boolean mask (batch, seq_len): True only at the single query answer
    position (index 2*n_pairs+1). The discriminative loss is evaluated here.
    """
    span = 2 * cfg.n_pairs + 2
    mask = torch.zeros((batch_size, cfg.seq_len), dtype=torch.bool, device=device)
    mask[:, span - 1] = True
    return mask

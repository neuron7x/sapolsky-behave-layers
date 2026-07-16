"""Heterogeneous two-mode task where per-sequence routing is causally useful.

Each sequence is one of two types, marked by a flag token at position 0:
- RECALL: in-context associative recall (needs induction: composition across
  ≥2 specific blocks).
- COPY: output the token at a fixed early position (needs a single retrieval
  head: shallow).

At a BINDING budget (K small), a static block selection must compromise
between the two mechanisms; an adaptive controller that routes by type can
serve both. This is the task where learned routing CAN beat static — the
decisive test WP-2 v1 RESULTS called for. If learned still collapses here, the
negative is strong (adaptivity provably could have helped and did not).

Deterministic given a seed. No external data.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class MixedTaskConfig:
    vocab_size: int = 64
    seq_len: int = 64
    n_pairs: int = 6
    key_lo: int = 4
    key_hi: int = 34
    value_lo: int = 34
    value_hi: int = 64
    pad_token: int = 0
    query_token: int = 1
    recall_flag: int = 2
    copy_flag: int = 3
    p_recall: float = 0.5


def generate_batch(
    cfg: MixedTaskConfig, batch_size: int, generator: torch.Generator, device: str = "cpu"
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Returns (inputs, targets, is_recall) — inputs/targets (B, seq_len) int64,
    is_recall (B,) bool. Loss is masked to the single answer position.

    RECALL layout: [RECALL_FLAG, k0,v0,...,QUERY, qk] target after qk = value.
    COPY   layout: [COPY_FLAG, x, fillers..., QUERY, x] target after QUERY = x.
    Both end their content at the same span so batching/eval align.
    """
    n = cfg.n_pairs
    span = 2 * n + 3  # flag + pairs + QUERY + last token
    assert span <= cfg.seq_len

    inputs = torch.full((batch_size, cfg.seq_len), cfg.pad_token, dtype=torch.long)
    targets = torch.full((batch_size, cfg.seq_len), cfg.pad_token, dtype=torch.long)
    is_recall = torch.zeros(batch_size, dtype=torch.bool)
    n_keys = cfg.key_hi - cfg.key_lo

    for b in range(batch_size):
        recall = bool(torch.rand(1, generator=generator).item() < cfg.p_recall)
        is_recall[b] = recall
        seq = torch.full((span,), cfg.pad_token, dtype=torch.long)
        if recall:
            seq[0] = cfg.recall_flag
            perm = torch.randperm(n_keys, generator=generator)[:n] + cfg.key_lo
            values = torch.randint(cfg.value_lo, cfg.value_hi, (n,), generator=generator)
            seq[1:1 + 2 * n:2] = perm
            seq[2:1 + 2 * n:2] = values
            seq[1 + 2 * n] = cfg.query_token
            qi = int(torch.randint(0, n, (1,), generator=generator).item())
            seq[2 + 2 * n] = perm[qi]
            targets[b, span - 1] = values[qi]
        else:
            seq[0] = cfg.copy_flag
            x = int(torch.randint(cfg.value_lo, cfg.value_hi, (1,), generator=generator).item())
            seq[1] = x
            # random filler content (keys) so the model can't shortcut on pads
            fill = torch.randint(cfg.key_lo, cfg.key_hi, (2 * n - 1,), generator=generator)
            seq[2:1 + 2 * n] = fill
            seq[1 + 2 * n] = cfg.query_token
            seq[2 + 2 * n] = cfg.pad_token
            targets[b, span - 1] = x
        inputs[b, :span] = seq
    return inputs.to(device), targets.to(device), is_recall.to(device)


def answer_mask(cfg: MixedTaskConfig, batch_size: int, device: str = "cpu") -> torch.Tensor:
    span = 2 * cfg.n_pairs + 3
    mask = torch.zeros((batch_size, cfg.seq_len), dtype=torch.bool, device=device)
    mask[:, span - 1] = True
    return mask

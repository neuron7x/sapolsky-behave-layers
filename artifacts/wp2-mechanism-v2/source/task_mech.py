"""Two mechanism-separable task families (Act A2).

LOCAL: answer (at the query position) = the token immediately before it (t-1).
       Solvable only by a local operator (E_A).
FAR:   answer (at the query position) = the token at position 1.
       Solvable only by a far/global operator (E_B); a local window cannot
       reach position 1 from the far query position.

Stage A (has_marker=True): position 0 is an explicit task flag.
Stage B (has_marker=False): no flag; task type must be inferred from the
       content range of position 1 (far uses value-range, local uses key-range).
"""
from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class MechTaskConfig:
    vocab_size: int = 64
    seq_len: int = 32
    content_len: int = 20      # query at content_len-1
    pad_token: int = 0
    query_token: int = 1
    flag_local: int = 2
    flag_far: int = 3
    key_lo: int = 4
    key_hi: int = 34           # local content range
    val_lo: int = 34
    val_hi: int = 64           # far pos-1 range
    p_far: float = 0.5


def generate_batch(cfg: MechTaskConfig, batch_size: int, generator, device="cpu", has_marker=True):
    """Returns inputs (B,T), targets (B,T), task_label (B,) with 0=LOCAL 1=FAR.
    Loss masked to the query position (content_len-1)."""
    T = cfg.seq_len
    span = cfg.content_len
    qpos = span - 1
    inputs = torch.full((batch_size, T), cfg.pad_token, dtype=torch.long)
    targets = torch.full((batch_size, T), cfg.pad_token, dtype=torch.long)
    labels = torch.zeros(batch_size, dtype=torch.long)

    for b in range(batch_size):
        far = bool(torch.rand(1, generator=generator).item() < cfg.p_far)
        labels[b] = 1 if far else 0
        # fill content positions 1..qpos-1 with random key-range tokens
        body = torch.randint(cfg.key_lo, cfg.key_hi, (span,), generator=generator)
        if far:
            # position 1 carries the far payload (value range); answer = it
            body[1] = int(torch.randint(cfg.val_lo, cfg.val_hi, (1,), generator=generator).item())
            targets[b, qpos] = body[1]
        else:
            # answer = token at qpos-1 (immediate neighbour, key range)
            targets[b, qpos] = body[qpos - 1]
        body[qpos] = cfg.query_token
        if has_marker:
            body[0] = cfg.flag_far if far else cfg.flag_local
        else:
            # Stage B: no dedicated flag; pos 0 is neutral content. The type is
            # inferable from whether pos 1 is in the value-range (far) or not.
            body[0] = int(torch.randint(cfg.key_lo, cfg.key_hi, (1,), generator=generator).item())
            if not far:
                # ensure pos1 stays in key-range for local (already is)
                pass
        inputs[b, :span] = body
    return inputs.to(device), targets.to(device), labels.to(device)


def answer_mask(cfg: MechTaskConfig, batch_size: int, device="cpu"):
    m = torch.zeros((batch_size, cfg.seq_len), dtype=torch.bool, device=device)
    m[:, cfg.content_len - 1] = True
    return m

"""Active-FLOP accounting for compute parity (Act §9). Counts MACs*2 for the
per-block matmuls and attention, times active blocks, plus controller FLOPs.
Logical (not kernel-measured) — the parity comparison is between configs
computed the same way, so any fixed convention cancels.
"""
from __future__ import annotations

from .model import ModelConfig


def block_flops(cfg: ModelConfig, seq_len: int) -> int:
    """FLOPs for one block's F_l over a sequence (per sequence, batch=1)."""
    d, ff, T, H = cfg.d_model, cfg.d_ff, seq_len, cfg.n_head
    dh = d // H
    # attention: qkv proj (3*d*d), attn scores+av (2 * H * T * dh * T), out proj (d*d)
    qkv = 2 * T * (3 * d * d)
    attn_core = 2 * (2 * H * T * T * dh)   # QK^T and AV
    outp = 2 * T * (d * d)
    # mlp: fc (d*ff), proj (ff*d), squared relu elementwise negligible
    mlp = 2 * T * (d * ff + ff * d)
    return qkv + attn_core + outp + mlp


def active_inference_flops(cfg: ModelConfig, seq_len: int, active_blocks: int, controller: bool) -> int:
    total = active_blocks * block_flops(cfg, seq_len)
    total += 2 * seq_len * (cfg.d_model * cfg.vocab_size)  # lm head
    if controller:
        total += cfg.n_layer * 2 * ((cfg.d_model + 1) * 64 + 64 * 1)
    return total


def parity_ratio(a: int, b: int) -> float:
    return abs(a - b) / max(a, b)

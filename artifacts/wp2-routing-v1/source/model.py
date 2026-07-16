"""Minimal self-contained transformer with fixed-topology hard-budget block
routing. Five configs share one backbone class; only the block-selection
policy differs. See ADR-0002 and PREREGISTRATION.md.

Invariants (tested in tests/):
- RoutingMode.DENSE == plain all-L forward (bit-exact).
- Skipped block == exact residual identity.
- Hard budget: exactly K active blocks per sequence at eval; never exceeded.
- Deterministic eval (argmax top-K, no sampling).
"""
from __future__ import annotations

import enum
import math
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


class RoutingMode(enum.Enum):
    DENSE = "dense"          # all L blocks (quality ceiling)
    RANDOM = "random"        # K blocks, seeded per-sequence RNG
    FROZEN = "frozen"        # learned-arch controller, weights frozen
    LEARNED = "learned"      # K blocks, controller trained
    FIXED_DEPTH = "fixed_depth"  # first K blocks, deterministic


@dataclass(frozen=True)
class ModelConfig:
    vocab_size: int = 64
    seq_len: int = 128
    n_layer: int = 8       # L
    d_model: int = 128
    n_head: int = 4
    d_ff: int = 512
    budget_k: int = 4      # K


def _rmsnorm(x: torch.Tensor) -> torch.Tensor:
    return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + 1e-6)


class Attention(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.n_head = cfg.n_head
        self.d_head = cfg.d_model // cfg.n_head
        self.qkv = nn.Linear(cfg.d_model, 3 * cfg.d_model, bias=False)
        self.proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, self.n_head, self.d_head).transpose(1, 2)
        k = k.view(B, T, self.n_head, self.d_head).transpose(1, 2)
        v = v.view(B, T, self.n_head, self.d_head).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(y)


class MLP(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.fc = nn.Linear(cfg.d_model, cfg.d_ff, bias=False)
        self.proj = nn.Linear(cfg.d_ff, cfg.d_model, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.proj(F.relu(self.fc(x)).square())


class Block(nn.Module):
    """Standard pre-norm residual block. F_l(h) = attn + mlp contribution."""

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.attn = Attention(cfg)
        self.mlp = MLP(cfg)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # returns the CONTRIBUTION F_l(x), not x + F_l(x), so the router can
        # gate it: h_{l+1} = h_l + g_l * F_l(h_l).
        a = self.attn(_rmsnorm(x))
        h = x + a
        m = self.mlp(_rmsnorm(h))
        return a + m  # F_l(x) = attn(x) + mlp(x+attn(x))


class BlockController(nn.Module):
    """Scores each of L blocks from a per-sequence summary + layer index.
    Global top-K over the L scores realizes the exact hard budget K.
    """

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.n_layer = cfg.n_layer
        # input per block: [pooled_hidden (d_model), norm_layer_index (1)]
        self.net = nn.Sequential(
            nn.Linear(cfg.d_model + 1, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def scores(self, pooled: torch.Tensor) -> torch.Tensor:
        # pooled: (B, d_model) -> scores (B, L)
        B = pooled.shape[0]
        idx = torch.arange(self.n_layer, device=pooled.device, dtype=pooled.dtype)
        idx = (idx / max(self.n_layer - 1, 1)).view(1, self.n_layer, 1).expand(B, -1, 1)
        p = pooled.unsqueeze(1).expand(B, self.n_layer, -1)
        feat = torch.cat([p, idx], dim=-1)          # (B, L, d_model+1)
        return self.net(feat).squeeze(-1)           # (B, L)

    def flops_per_sequence(self, d_model: int) -> int:
        # two linear layers: (d_model+1)*64 + 64*1, times L blocks, x2 (MAC)
        return self.n_layer * 2 * ((d_model + 1) * 64 + 64 * 1)


def _topk_mask(scores: torch.Tensor, k: int) -> torch.Tensor:
    """Hard 0/1 mask (B, L) with exactly k ones per row at the top-k scores."""
    B, L = scores.shape
    idx = scores.topk(k, dim=1).indices
    mask = torch.zeros_like(scores)
    mask.scatter_(1, idx, 1.0)
    return mask


class RoutedTransformer(nn.Module):
    def __init__(self, cfg: ModelConfig, mode: RoutingMode):
        super().__init__()
        self.cfg = cfg
        self.mode = mode
        self.embed = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.pos = nn.Embedding(cfg.seq_len, cfg.d_model)  # learned positions
        self.blocks = nn.ModuleList([Block(cfg) for _ in range(cfg.n_layer)])
        self.head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        self.controller = BlockController(cfg) if mode in (RoutingMode.LEARNED, RoutingMode.FROZEN) else None
        if mode == RoutingMode.FROZEN and self.controller is not None:
            for p in self.controller.parameters():
                p.requires_grad_(False)
        self._last_mask: torch.Tensor | None = None

    def _select_mask(self, x_emb: torch.Tensor, seq_seed: int | None) -> torch.Tensor:
        B = x_emb.shape[0]
        L, K = self.cfg.n_layer, self.cfg.budget_k
        if self.mode == RoutingMode.DENSE:
            return torch.ones(B, L, device=x_emb.device)
        if self.mode == RoutingMode.FIXED_DEPTH:
            m = torch.zeros(B, L, device=x_emb.device)
            m[:, :K] = 1.0
            return m
        if self.mode == RoutingMode.RANDOM:
            # deterministic per (seq_seed, row): stable across train/eval
            g = torch.Generator(device="cpu")
            g.manual_seed((seq_seed or 0) * 1_000_003 + B)
            m = torch.zeros(B, L)
            for b in range(B):
                idx = torch.randperm(L, generator=g)[:K]
                m[b, idx] = 1.0
            return m.to(x_emb.device)
        # LEARNED / FROZEN
        pooled = x_emb.mean(dim=1)               # (B, d_model), per-sequence
        scores = self.controller.scores(pooled)  # (B, L)
        hard = _topk_mask(scores, K)
        if self.training:
            # straight-through: value = hard, gradient via softmax prob
            soft = torch.softmax(scores, dim=1)
            return hard + (soft - soft.detach())
        return hard

    def forward(self, idx: torch.Tensor, seq_seed: int | None = None) -> torch.Tensor:
        T = idx.shape[1]
        pos = torch.arange(T, device=idx.device)
        x = self.embed(idx) + self.pos(pos).unsqueeze(0)
        mask = self._select_mask(x, seq_seed)     # (B, L), differentiable for learned/train
        self._last_mask = (mask.detach() > 0.5).float()
        hard = self._last_mask
        for l, block in enumerate(self.blocks):
            g = mask[:, l].view(-1, 1, 1)          # (B,1,1)
            if self.training or self.mode in (RoutingMode.DENSE,):
                # train: compute all blocks, gate contribution (equal train FLOPs)
                x = x + g * block(x)
            else:
                # eval: real skip for rows where this block is inactive.
                active = hard[:, l] > 0.5
                if active.all():
                    x = x + block(x)
                elif active.any():
                    contrib = block(x[active])
                    x = x.clone()
                    x[active] = x[active] + contrib
                # else: no row uses this block -> skip entirely (identity)
        return self.head(_rmsnorm(x))

    def last_active_counts(self) -> torch.Tensor:
        assert self._last_mask is not None
        return self._last_mask.sum(dim=1)          # (B,)

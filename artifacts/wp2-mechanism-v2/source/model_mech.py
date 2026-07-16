"""Mechanism-separable model (Act A2/A3). Two structurally non-substitutable
operator types, so a fixed route MUST fail one task family — making adaptive
routing identifiable (unlike WP-2 v1/v1.1 where any block solved everything).

- E_A LocalOp: causal attention restricted to a local window [t-w, t]. Can copy
  a neighbour (t-1); CANNOT reach a far position by construction.
- E_B FarOp:  causal attention restricted to the far context [0, t-w-1]
  (the local window is masked OUT). Can retrieve a far position; CANNOT see a
  neighbour by construction.

Task LOCAL (answer = token at t-1) is solvable only via E_A.
Task FAR  (answer = token at position 1) is solvable only via E_B.
K=1 active block over {one E_A, one E_B}: a fixed route fails one family; the
oracle (route by true task) solves both. That oracle gap is the A2 gate.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

LOCAL_WINDOW = 2  # w


class Mode(enum.Enum):
    DENSE = "dense"          # both blocks
    RANDOM = "random"        # 1 random block per sequence
    FROZEN = "frozen"        # learned-arch controller, frozen
    FIXED = "fixed"          # always block 0 (E_A)
    ORACLE = "oracle"        # route by TRUE task label (benchmark control)
    LEARNED = "learned"      # controller trained


@dataclass(frozen=True)
class MechConfig:
    vocab_size: int = 64
    seq_len: int = 32
    d_model: int = 64
    n_head: int = 4
    d_ff: int = 128
    # two blocks: index 0 = E_A (local), index 1 = E_B (far). K=1.


def _rms(x):
    return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + 1e-6)


def _local_mask(T: int, w: int, device) -> torch.Tensor:
    i = torch.arange(T, device=device).view(T, 1)
    j = torch.arange(T, device=device).view(1, T)
    return (j <= i) & (j >= i - w)          # [t-w, t]


def _far_mask(T: int, w: int, device) -> torch.Tensor:
    i = torch.arange(T, device=device).view(T, 1)
    j = torch.arange(T, device=device).view(1, T)
    allow = (j <= i - w - 1)                  # [0, t-w-1]
    allow[:, 0] = True                        # anchor pos 0 to avoid empty rows
    allow[0, 0] = True
    return allow


class MaskedAttn(nn.Module):
    def __init__(self, cfg: MechConfig, kind: str):
        super().__init__()
        self.kind = kind
        self.n_head = cfg.n_head
        self.dh = cfg.d_model // cfg.n_head
        self.qkv = nn.Linear(cfg.d_model, 3 * cfg.d_model, bias=False)
        self.proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)

    def forward(self, x):
        B, T, C = x.shape
        allow = _local_mask(T, LOCAL_WINDOW, x.device) if self.kind == "local" else _far_mask(T, LOCAL_WINDOW, x.device)
        bias = torch.zeros(T, T, device=x.device, dtype=x.dtype)
        bias.masked_fill_(~allow, float("-inf"))
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, self.n_head, self.dh).transpose(1, 2)
        k = k.view(B, T, self.n_head, self.dh).transpose(1, 2)
        v = v.view(B, T, self.n_head, self.dh).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, attn_mask=bias.view(1, 1, T, T))
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(y)


class MechBlock(nn.Module):
    def __init__(self, cfg: MechConfig, kind: str):
        super().__init__()
        self.attn = MaskedAttn(cfg, kind)
        self.fc = nn.Linear(cfg.d_model, cfg.d_ff, bias=False)
        self.proj = nn.Linear(cfg.d_ff, cfg.d_model, bias=False)

    def forward(self, x):
        a = self.attn(_rms(x))
        h = x + a
        m = self.proj(F.relu(self.fc(_rms(h))).square())
        return a + m       # contribution F(x)


class Controller(nn.Module):
    """Scores the 2 blocks from a per-sequence pooled summary. Global top-1."""

    def __init__(self, cfg: MechConfig):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(cfg.d_model, 32), nn.ReLU(), nn.Linear(32, 2))

    def forward(self, pooled):
        return self.net(pooled)   # (B, 2)


class MechModel(nn.Module):
    def __init__(self, cfg: MechConfig, mode: Mode, fixed_block: int = 0):
        super().__init__()
        self.cfg = cfg
        self.mode = mode
        self.fixed_block = fixed_block
        self.embed = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.pos = nn.Embedding(cfg.seq_len, cfg.d_model)
        self.block_a = MechBlock(cfg, "local")   # E_A index 0
        self.block_b = MechBlock(cfg, "far")     # E_B index 1
        self.head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        self.ctrl = Controller(cfg) if mode in (Mode.LEARNED, Mode.FROZEN) else None
        if mode == Mode.FROZEN and self.ctrl is not None:
            for p in self.ctrl.parameters():
                p.requires_grad_(False)
        self._last_route: torch.Tensor | None = None  # (B,) chosen block idx

    def _route(self, pooled, task_label, seq_seed):
        B = pooled.shape[0]
        dev = pooled.device
        if self.mode == Mode.DENSE:
            return None  # both
        if self.mode == Mode.FIXED:
            return torch.full((B,), self.fixed_block, dtype=torch.long, device=dev)
        if self.mode == Mode.ORACLE:
            assert task_label is not None
            return task_label.long()  # 0=local->E_A, 1=far->E_B
        if self.mode == Mode.RANDOM:
            g = torch.Generator(device="cpu").manual_seed((seq_seed or 0) * 7919 + B)
            return torch.randint(0, 2, (B,), generator=g).to(dev)
        # LEARNED / FROZEN
        scores = self.ctrl(pooled)             # (B,2)
        hard = scores.argmax(dim=1)
        if self.training:
            soft = F.softmax(scores, dim=1)
            self._soft = soft
        self._scores = scores
        return hard

    def forward(self, idx, task_label=None, seq_seed=None, forced_route=None, swap_modules=False):
        T = idx.shape[1]
        x = self.embed(idx) + self.pos(torch.arange(T, device=idx.device)).unsqueeze(0)
        pooled = x.mean(dim=1)
        route = forced_route if forced_route is not None else self._route(pooled, task_label, seq_seed)
        if route is None:  # dense
            x = x + self.block_a(x) + self.block_b(x)
            self._last_route = torch.full((idx.shape[0],), -1, device=idx.device)
            return self.head_out(x)
        self._last_route = route
        use_a = route == 0
        block_a, block_b = (self.block_b, self.block_a) if swap_modules else (self.block_a, self.block_b)
        out = x.clone()
        if self.training and self.mode in (Mode.LEARNED,):
            # straight-through: run both, gate by soft prob for gradient
            ga = self._soft[:, 0].view(-1, 1, 1)
            gb = self._soft[:, 1].view(-1, 1, 1)
            hard_a = use_a.float().view(-1, 1, 1)
            hard_b = (~use_a).float().view(-1, 1, 1)
            g_a = hard_a + (ga - ga.detach())
            g_b = hard_b + (gb - gb.detach())
            x = x + g_a * self.block_a(x) + g_b * self.block_b(x)
            return self.head_out(x)
        # eval / non-learned: real single-block execution
        if use_a.any():
            out[use_a] = x[use_a] + block_a(x[use_a])
        if (~use_a).any():
            out[~use_a] = x[~use_a] + block_b(x[~use_a])
        return self.head_out(out)

    def head_out(self, x):
        return self.head(_rms(x))

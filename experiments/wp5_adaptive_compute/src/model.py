"""Weight-tied recurrent block for the adaptive-COMPUTE mechanism (WP5).

A single shared (attn+mlp) block applied K times = K units of compute. Trained to be a
clean shift-by-1 operator, so K iterations compute a shift-by-K. Difficulty (required shift
distance d) then determines the compute a correct answer needs — the identifiability premise
on the COMPUTE axis, not the parameter-allocation axis (WP3 plasticity).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

VOCAB = 16
SEQ_LEN = 12
D_MODEL = 32
N_HEAD = 4


class Block(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.qkv = nn.Linear(D_MODEL, 3 * D_MODEL, bias=False)
        self.proj = nn.Linear(D_MODEL, D_MODEL, bias=False)
        self.fc = nn.Linear(D_MODEL, 4 * D_MODEL, bias=False)
        self.fout = nn.Linear(4 * D_MODEL, D_MODEL, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, N_HEAD, C // N_HEAD).transpose(1, 2)
        k = k.view(B, T, N_HEAD, C // N_HEAD).transpose(1, 2)
        v = v.view(B, T, N_HEAD, C // N_HEAD).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v)          # non-causal: can attend anywhere
        x = x + self.proj(y.transpose(1, 2).contiguous().view(B, T, C))
        return x + self.fout(F.relu(self.fc(x)))


class RecurrentModel(nn.Module):
    """embed -> (shared Block) x K -> head. K is the per-forward compute budget."""

    def __init__(self) -> None:
        super().__init__()
        self.embed = nn.Embedding(VOCAB, D_MODEL)
        self.pos = nn.Embedding(SEQ_LEN, D_MODEL)
        self.block = Block()
        self.head = nn.Linear(D_MODEL, VOCAB, bias=False)

    def forward(self, x: torch.Tensor, k_iter: int) -> torch.Tensor:
        T = x.shape[1]
        h = self.embed(x) + self.pos(torch.arange(T, device=x.device)).unsqueeze(0)
        for _ in range(k_iter):
            h = self.block(h)
        return self.head(h)

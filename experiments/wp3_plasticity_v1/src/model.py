"""Small named-group transformer for the plasticity oracle-gap experiment.
Module names match the registry patterns (attn.qkv/attn.proj/mlp.fc/mlp.proj/
head/embed) so parameter groups are structurally addressable."""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

VOCAB = 16
SEQ_LEN = 8
D_MODEL = 32
N_HEAD = 4


class Attn(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.qkv = nn.Linear(D_MODEL, 3 * D_MODEL, bias=False)
        self.proj = nn.Linear(D_MODEL, D_MODEL, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, N_HEAD, C // N_HEAD).transpose(1, 2)
        k = k.view(B, T, N_HEAD, C // N_HEAD).transpose(1, 2)
        v = v.view(B, T, N_HEAD, C // N_HEAD).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        return self.proj(y.transpose(1, 2).contiguous().view(B, T, C))


class Mlp(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.fc = nn.Linear(D_MODEL, 4 * D_MODEL, bias=False)
        self.proj = nn.Linear(4 * D_MODEL, D_MODEL, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.proj(F.relu(self.fc(x)))


class GroupedModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.embed = nn.Embedding(VOCAB, D_MODEL)
        self.pos = nn.Embedding(SEQ_LEN, D_MODEL)
        self.attn = Attn()
        self.mlp = Mlp()
        self.head = nn.Linear(D_MODEL, VOCAB, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        T = x.shape[1]
        h = self.embed(x) + self.pos(torch.arange(T, device=x.device)).unsqueeze(0)
        h = h + self.attn(h)
        h = h + self.mlp(h)
        return self.head(h)

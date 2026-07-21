"""Byte-level weight-tied recurrent language model for the real-data boundary test (WP6).

Same adaptive-compute mechanism as WP5 (K shared-block iterations), but next-BYTE prediction on
real English prose (a frozen corpus of the repo's stable docs) instead of a synthetic shift task.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

VOCAB = 256          # byte-level
D_MODEL = 64
N_HEAD = 4
SEQ_LEN = 64


class Block(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.qkv = nn.Linear(D_MODEL, 3 * D_MODEL, bias=False)
        self.proj = nn.Linear(D_MODEL, D_MODEL, bias=False)
        self.fc = nn.Linear(D_MODEL, 4 * D_MODEL, bias=False)
        self.fout = nn.Linear(4 * D_MODEL, D_MODEL, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, c = x.shape
        q, k, v = self.qkv(x).split(c, dim=2)
        q = q.view(b, t, N_HEAD, c // N_HEAD).transpose(1, 2)
        k = k.view(b, t, N_HEAD, c // N_HEAD).transpose(1, 2)
        v = v.view(b, t, N_HEAD, c // N_HEAD).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        x = x + self.proj(y.transpose(1, 2).contiguous().view(b, t, c))
        return x + self.fout(F.relu(self.fc(x)))


class ByteRecurrentLM(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.emb = nn.Embedding(VOCAB, D_MODEL)
        self.pos = nn.Embedding(SEQ_LEN, D_MODEL)
        self.block = Block()
        self.head = nn.Linear(D_MODEL, VOCAB, bias=False)

    def forward(self, x: torch.Tensor, k_iter: int) -> torch.Tensor:
        h = self.emb(x) + self.pos(torch.arange(x.shape[1], device=x.device)).unsqueeze(0)
        for _ in range(k_iter):
            h = self.block(h)
        return self.head(h)

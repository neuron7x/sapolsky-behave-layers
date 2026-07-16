"""Two physically different paths (Act §5). A different block index is not a
different mechanism — these are structurally distinct, and the distinction is a
hard *architectural* constraint, not a difference in training.

DirectPath    : one LOCAL-attention block (window LOCAL_W = ±1, see below) whose L_OUT
                output heads read positions 0..L_OUT-1. Because attention is masked to a
                ±1 neighbourhood, a head *cannot* route information from tokens farther
                away, no matter how it is trained -> it is structurally incapable of the
                HARD task (which places the decisive content out of window). This is what
                makes the benchmark mechanism-separable: HARD failure is by construction.
SemanticParser: GLOBAL attention -> mean-pool -> 4 supervised field heads (S,R,O,polarity)
                + a confidence scalar; comprehension is unconstrained in range.
SemanticRenderer: emits canonical tokens from the discrete SemanticState ONLY — it never
                sees the raw input, so it cannot leak surface form into the output.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from experiments.wp2_routing_v2.src.contracts import VOCAB_SIZE, SemanticState
from experiments.wp2_routing_v2.src.task_semantic_route import L_OUT, SEQ_LEN

D_MODEL = 64
N_HEAD = 4
LOCAL_W = 1  # ±1 window: DirectPath heads at positions 0-3 cannot reach HARD
             # content placed farther away, so it structurally fails HARD.


def _rms(x):
    return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + 1e-6)


class _Attn(nn.Module):
    """Multi-head self-attention, optionally *masked to a local ±LOCAL_W window*.
    The mask is the load-bearing part: when `local=True`, positions farther than
    LOCAL_W apart are set to -inf before softmax, so the block has literally zero
    weight on distant tokens. This is a structural capacity limit (a property of the
    architecture), which is why DirectPath's HARD failure cannot be trained away."""

    def __init__(self, local: bool):
        super().__init__()
        self.local = local
        self.qkv = nn.Linear(D_MODEL, 3 * D_MODEL, bias=False)
        self.proj = nn.Linear(D_MODEL, D_MODEL, bias=False)

    def forward(self, x):
        B, T, C = x.shape
        mask = None
        if self.local:
            i = torch.arange(T, device=x.device).view(T, 1)
            j = torch.arange(T, device=x.device).view(1, T)
            allow = (j - i).abs() <= LOCAL_W
            mask = torch.zeros(T, T, device=x.device).masked_fill(~allow, float("-inf")).view(1, 1, T, T)
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, N_HEAD, C // N_HEAD).transpose(1, 2)
        k = k.view(B, T, N_HEAD, C // N_HEAD).transpose(1, 2)
        v = v.view(B, T, N_HEAD, C // N_HEAD).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, attn_mask=mask)
        return self.proj(y.transpose(1, 2).contiguous().view(B, T, C))


class _Embed(nn.Module):
    def __init__(self):
        super().__init__()
        self.tok = nn.Embedding(VOCAB_SIZE, D_MODEL)
        self.pos = nn.Embedding(SEQ_LEN, D_MODEL)

    def forward(self, tokens):
        T = tokens.shape[1]
        return self.tok(tokens) + self.pos(torch.arange(T, device=tokens.device)).unsqueeze(0)


class DirectPath(nn.Module):
    """Cheap LOCAL path: embed -> one ±LOCAL_W attention block -> MLP -> one head per
    output position. Its receptive field is bounded by the local mask, so it solves EASY
    (in-window content) but is structurally unable to solve HARD (out-of-window content).
    Returns per-position vocab logits `[B, L_OUT, VOCAB_SIZE]`."""

    def __init__(self):
        super().__init__()
        self.embed = _Embed()
        self.attn = _Attn(local=True)
        self.mlp = nn.Sequential(nn.Linear(D_MODEL, 128), nn.ReLU(), nn.Linear(128, D_MODEL))
        self.heads = nn.ModuleList([nn.Linear(D_MODEL, VOCAB_SIZE) for _ in range(L_OUT)])

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        x = self.embed(tokens)
        x = x + self.attn(_rms(x))
        x = x + self.mlp(_rms(x))
        return torch.stack([self.heads[i](x[:, i]) for i in range(L_OUT)], dim=1)  # [B,L_OUT,vocab]


class SemanticParser(nn.Module):
    """Global comprehension -> discrete SemanticState. Field heads are supervised."""

    def __init__(self):
        super().__init__()
        self.embed = _Embed()
        self.attn = _Attn(local=False)
        self.mlp = nn.Sequential(nn.Linear(D_MODEL, 128), nn.ReLU(), nn.Linear(128, D_MODEL))
        self.h_subj = nn.Linear(D_MODEL, VOCAB_SIZE)
        self.h_rel = nn.Linear(D_MODEL, VOCAB_SIZE)
        self.h_obj = nn.Linear(D_MODEL, VOCAB_SIZE)
        self.h_pol = nn.Linear(D_MODEL, 2)
        self.h_conf = nn.Linear(D_MODEL, 1)

    def logits(self, tokens):
        x = self.embed(tokens)
        x = x + self.attn(_rms(x))
        x = x + self.mlp(_rms(x))
        pooled = x.mean(dim=1)
        return (self.h_subj(pooled), self.h_rel(pooled), self.h_obj(pooled),
                self.h_pol(pooled), self.h_conf(pooled).squeeze(-1))

    def forward(self, tokens: torch.Tensor) -> SemanticState:
        ls, lr, lo, lp, lc = self.logits(tokens)
        return SemanticState(subject=ls.argmax(-1), relation=lr.argmax(-1), object=lo.argmax(-1),
                             polarity=lp.argmax(-1), confidence=torch.sigmoid(lc))


class SemanticRenderer(nn.Module):
    """Canonical tokens from SemanticState only (no raw input tokens)."""

    def __init__(self):
        super().__init__()
        self.subj_e = nn.Embedding(VOCAB_SIZE, D_MODEL)
        self.rel_e = nn.Embedding(VOCAB_SIZE, D_MODEL)
        self.obj_e = nn.Embedding(VOCAB_SIZE, D_MODEL)
        self.pol_e = nn.Embedding(2, D_MODEL)
        self.heads = nn.ModuleList([nn.Linear(4 * D_MODEL, VOCAB_SIZE) for _ in range(L_OUT)])

    def forward(self, state: SemanticState) -> torch.Tensor:
        feat = torch.cat([self.subj_e(state.subject), self.rel_e(state.relation),
                          self.obj_e(state.object), self.pol_e(state.polarity)], dim=-1)
        return torch.stack([h(feat) for h in self.heads], dim=1)  # [B,L_OUT,vocab]


class SemanticPath(nn.Module):
    """The expensive path = parse-then-render: global comprehension into a discrete
    SemanticState, then canonical output from that state alone. The intermediate state
    is returned alongside the logits so lesion studies (typed_graph) can corrupt a single
    field (polarity, subject/object, ...) and observe the predicted downstream failure —
    the composition is what makes the mechanism *inspectable*, not a black box."""

    def __init__(self):
        super().__init__()
        self.parser = SemanticParser()
        self.renderer = SemanticRenderer()

    def forward(self, tokens: torch.Tensor) -> tuple[torch.Tensor, SemanticState]:
        state = self.parser(tokens)
        return self.renderer(state), state

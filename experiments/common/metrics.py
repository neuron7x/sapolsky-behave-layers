"""Correct information + ranking metrics (P0.7). Fixes two bugs found in review:
- the old NMI divided MI by H(T) only (task-normalized MI, NOT symmetric NMI);
- the old AUROC did not use AVERAGE ranks for tied scores.
Each metric is named precisely and validated against reference cases in the test.
"""
from __future__ import annotations

import math

import torch


def _counts(x: torch.Tensor, k: int) -> torch.Tensor:
    """Occupancy counts of integer labels in [0, k) as float — the empirical histogram
    the entropy/MI estimators are built on (`minlength=k` keeps empty classes present so
    the support is fixed, not data-dependent)."""
    return torch.bincount(x.long(), minlength=k).float()


def entropy(x: torch.Tensor, k: int) -> float:
    """Shannon entropy H(X) in nats over k classes, from the empirical distribution.
    Zero-probability classes are dropped before the log (0*log0 := 0). This is the
    normalizer that makes NMI comparable across variables of different base rates."""
    p = _counts(x, k)
    p = p / p.sum().clamp_min(1e-12)
    return float(-(p[p > 0] * p[p > 0].log()).sum())


def mutual_information(r: torch.Tensor, t: torch.Tensor, kr: int, kt: int) -> float:
    """Mutual information I(R;T) in nats from the empirical joint, summed over the
    kr x kt cells with the standard `p_rt * log(p_rt / (p_r p_t))` term (cells with any
    zero marginal/joint contribute 0). Symmetric in R and T; the building block of both
    NMI variants below."""
    mi = 0.0
    for rv in range(kr):
        for tv in range(kt):
            p_rt = ((r == rv) & (t == tv)).float().mean().item()
            p_r = (r == rv).float().mean().item()
            p_t = (t == tv).float().mean().item()
            if p_rt > 0 and p_r > 0 and p_t > 0:
                mi += p_rt * math.log(p_rt / (p_r * p_t))
    return mi


def symmetric_nmi(r: torch.Tensor, t: torch.Tensor, kr: int = 2, kt: int = 2) -> float:
    """Standard symmetric NMI = MI / sqrt(H(R) H(T)) ∈ [0, 1]."""
    hr, ht = entropy(r, kr), entropy(t, kt)
    denom = math.sqrt(hr * ht)
    return (mutual_information(r, t, kr, kt) / denom) if denom > 0 else 0.0


def task_normalized_mi(r: torch.Tensor, t: torch.Tensor, kr: int = 2, kt: int = 2) -> float:
    """MI / H(T) — the quantity the OLD code computed (kept, correctly named)."""
    ht = entropy(t, kt)
    return (mutual_information(r, t, kr, kt) / ht) if ht > 0 else 0.0


def auroc(score: torch.Tensor, label: torch.Tensor) -> float:
    """Mann–Whitney AUROC with AVERAGE ranks for ties. label ∈ {0,1}."""
    s = score.float().flatten()
    y = label.long().flatten()
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = torch.argsort(s)
    s_sorted = s[order]
    ranks = torch.empty_like(s_sorted)
    i = 0
    n = s_sorted.numel()
    while i < n:
        j = i
        while j + 1 < n and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0            # average rank for the tie block
        ranks[i:j + 1] = avg_rank
        i = j + 1
    rank_of = torch.empty_like(ranks)
    rank_of[order] = ranks
    sum_pos = float(rank_of[y == 1].sum().item())
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)

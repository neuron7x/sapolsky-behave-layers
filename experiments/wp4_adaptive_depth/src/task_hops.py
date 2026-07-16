"""Depth-necessity task: pointer-chase to an absorbing fixed point.

Each example is a random functional graph on N nodes: node i -> succ[i], with a
single absorbing node (succ[absorber]=absorber, a self-loop) that every node
reaches. Each node carries a random value. The target is the VALUE at the
absorber reached from a start node. m(x) = hops from start to the absorber.

Properties (why depth is genuinely necessary, not a lookup):
- the answer is val[ succ^d(start) ] read at depth d; it equals the target iff
  d >= m(x) (the absorber self-loops -> once reached, it stays -> MONOTONE);
- succ and val are random per example -> no memorizable table;
- following k random pointers has no shortcut -> needs k sequential hops.

Static depth-K accuracy therefore equals P(m <= K) by construction — the
signature of depth necessity, and the basis for the Jensen gap G = P(m > K).
"""
from __future__ import annotations

from dataclasses import dataclass

import torch

N_NODES = 24          # graph size (also the value/label vocabulary)
MAX_M = 8             # max chain length; also the max useful depth L


@dataclass(frozen=True)
class HopTaskConfig:
    n_nodes: int = N_NODES
    max_m: int = MAX_M


def generate_batch(batch_size: int, gen: torch.Generator, device: str = "cpu",
                   m_weights: torch.Tensor | None = None):
    """Returns:
      table_succ  (B, N)  int64 : succ[i] for each node
      values      (B, N)  int64 : val[i] for each node
      start       (B,)    int64 : start node
      target      (B,)    int64 : val[absorber] (the correct answer)
      m           (B,)    int64 : hops start->absorber (true required depth)
    The chain from start has a preregistered length distribution via m_weights
    (over 1..MAX_M); absorber and off-chain nodes are randomised.
    """
    N = N_NODES
    if m_weights is None:
        m_weights = torch.ones(MAX_M)   # uniform over 1..MAX_M
    table = torch.zeros(batch_size, N, dtype=torch.long)
    values = torch.zeros(batch_size, N, dtype=torch.long)
    start = torch.zeros(batch_size, dtype=torch.long)
    target = torch.zeros(batch_size, dtype=torch.long)
    m = torch.zeros(batch_size, dtype=torch.long)

    for b in range(batch_size):
        perm = torch.randperm(N, generator=gen)
        vals = torch.randint(0, N, (N,), generator=gen)
        k = int(torch.multinomial(m_weights, 1, generator=gen).item()) + 1  # 1..MAX_M
        # chain of k+1 distinct nodes: c0(start) -> c1 -> ... -> ck(absorber)
        chain = perm[: k + 1]
        succ = torch.empty(N, dtype=torch.long)
        # off-chain nodes point randomly onto the chain (they never affect the
        # start's path, but keep the table full and non-trivial)
        for i in range(N):
            succ[i] = chain[int(torch.randint(0, k + 1, (1,), generator=gen).item())]
        for j in range(k):
            succ[chain[j]] = chain[j + 1]          # c_j -> c_{j+1}
        succ[chain[k]] = chain[k]                  # absorber self-loops
        table[b] = succ
        values[b] = vals
        start[b] = chain[0]
        target[b] = vals[chain[k]]
        m[b] = k
    return (table.to(device), values.to(device), start.to(device),
            target.to(device), m.to(device))


def required_depth_cdf(m: torch.Tensor, K: int) -> float:
    """Empirical P(m <= K)."""
    return (m <= K).float().mean().item()

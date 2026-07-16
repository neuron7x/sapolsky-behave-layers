"""Exact hop substrate + depth-allocation policies (spec: isolate ALLOCATION).

The hop operator is an exact successor lookup — the identical "capable
primitive" for every policy, so per-hop compute and capacity are matched by
construction. The ONLY free variable is how many hops each input receives:

- static_K:      K hops for every input (best fixed allocation).
- random_avgK:   a random number of hops per input with mean K (variable depth
                 that IGNORES the input -> control for "any variability helps").
- adaptive_halt: hop until the node stops changing (reached the absorbing
                 fixed point) -> uses the per-input HALT signal = information
                 about m(x). This is the mechanism under test.
- oracle:        exactly m(x) hops (ceiling).

`solved` = reached the absorber (analytically P(m<=allocated)); `acc` also counts
chance value-collisions. The causal claim rests on `solved`, where static gives
exactly P(m<=K) and adaptive gives 1 at avg compute E[m], gap = P(m>K).
"""
from __future__ import annotations

import torch

from experiments.wp4_adaptive_depth.src.task_hops import MAX_M


def _final_node(table: torch.Tensor, start: torch.Tensor, hops: torch.Tensor) -> torch.Tensor:
    """Follow succ per-input `hops` times (exact)."""
    B = start.shape[0]
    cur = start.clone()
    idx = torch.arange(B, device=start.device)
    for t in range(int(hops.max().item())):
        step = (hops > t)
        nxt = table[idx, cur]
        cur = torch.where(step, nxt, cur)
    return cur


def _metrics(cur, values, target, m, alloc):
    """Score a finished run. Two distinct quantities, deliberately not merged:
      - `solved` = fraction that reached the absorbing fixed point = mean(m <= alloc).
        This is the CAUSAL metric: it is a pure function of the allocation vs difficulty
        and cannot be inflated by luck, so the Jensen-gap claim rests on it.
      - `acc`    = fraction whose read-out value matches the target. `acc >= solved`
        because an unsolved input can still collide with the right value by chance; `acc`
        is reported for transparency but is NOT the basis of the claim.
    `avg_hops` = mean allocated compute, the x-axis of the compute/quality trade-off.
    """
    B = cur.shape[0]
    idx = torch.arange(B, device=cur.device)
    pred = values[idx, cur]
    solved = (m <= alloc).float().mean().item()       # reached absorber
    acc = (pred == target).float().mean().item()
    return {"acc": acc, "solved": solved, "avg_hops": alloc.float().mean().item()}


def run_policy(policy: str, K: int, table, values, start, target, m, gen) -> dict:
    """Allocate hops by `policy`, run the exact operator, and score.

    The operator is identical across policies, so the ONLY thing that varies is the
    per-input hop count `alloc` — this is what isolates *allocation* from capacity or
    operator quality. The four policies form the causal ladder:
      - "static":   alloc = K everywhere -> solved = P(m <= K) exactly (best fixed).
      - "oracle":   alloc = m(x)         -> solved = 1 at the minimum sufficient compute.
      - "random":   alloc ~ U[1, 2K-1], mean ~K, INPUT-BLIND -> the control proving that
                    mere depth *variability* does not help; only variability correlated
                    with m(x) does.
      - "adaptive": halt-on-convergence -> alloc = m(x) realized WITHOUT being told m,
                    by hopping until the successor is a self-loop (the absorber). This is
                    the mechanism under test; at equal average compute E[m] it lifts
                    solved from P(m<=K) to 1, i.e. by exactly the Jensen gap P(m>K).
    Returns the `_metrics` dict; `gen` seeds only the random policy.
    """
    B = start.shape[0]
    if policy == "static":
        alloc = torch.full((B,), K, dtype=torch.long, device=start.device)
    elif policy == "oracle":
        alloc = m.clone()
    elif policy == "random":
        # random per-input depth in [1, 2K-1] with mean ~K (ignores the input)
        alloc = torch.randint(1, 2 * K, (B,), generator=gen).to(start.device)
    elif policy == "adaptive":
        # halt-on-convergence: number of hops until the node stops changing,
        # i.e. exactly m(x). Realised by following until the self-loop.
        cur = start.clone(); idx = torch.arange(B, device=start.device)
        hops = torch.zeros(B, dtype=torch.long, device=start.device)
        active = torch.ones(B, dtype=torch.bool, device=start.device)
        for _ in range(MAX_M + 2):
            nxt = table[idx, cur]
            moved = (nxt != cur) & active
            hops += moved.long()
            active = moved
            cur = torch.where(moved, nxt, cur)
            if not active.any():
                break
        alloc = hops
    else:
        raise ValueError(policy)
    cur = _final_node(table, start, alloc)
    return _metrics(cur, values, target, m, alloc)

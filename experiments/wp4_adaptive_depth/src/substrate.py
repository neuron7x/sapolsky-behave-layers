"""Exact hop substrate + depth-allocation policies (spec: isolate ALLOCATION).

The hop operator is an exact successor lookup — the identical "capable
primitive" for every policy, so per-hop compute and capacity are matched by
construction. The ONLY free variable is how many hops each input receives:

- static_K:      K hops for every input (best fixed allocation).
- random_avgK:   a random number of hops per input with mean K (variable depth
                 that IGNORES the input -> control for "any variability helps").
- random_exact:  input-blind floor/ceiling allocation whose TOTAL hops exactly
                 match a caller-supplied budget; assignment is randomly permuted.
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


def allocate_input_blind_exact(
    batch_size: int,
    total_hops: int,
    gen: torch.Generator,
    device: torch.device,
) -> torch.Tensor:
    """Allocate an integer total exactly without observing per-input difficulty."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if total_hops < 0:
        raise ValueError("total_hops must be non-negative")
    base, remainder = divmod(total_hops, batch_size)
    alloc = torch.full((batch_size,), base, dtype=torch.long)
    if remainder:
        alloc[:remainder] += 1
    permutation = torch.randperm(batch_size, generator=gen)
    return alloc[permutation].to(device)


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
    return {
        "acc": acc,
        "solved": solved,
        "avg_hops": alloc.float().mean().item(),
        "total_hops": int(alloc.sum().item()),
    }


def run_policy(
    policy: str,
    K: int,
    table,
    values,
    start,
    target,
    m,
    gen,
    *,
    total_hops: int | None = None,
    halt_false_positive_rate: float = 0.0,
) -> dict:
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
    if not 0.0 <= halt_false_positive_rate <= 1.0:
        raise ValueError("halt_false_positive_rate must be in [0,1]")
    B = start.shape[0]
    halt_evaluations = 0
    if policy == "static":
        alloc = torch.full((B,), K, dtype=torch.long, device=start.device)
    elif policy == "oracle":
        alloc = m.clone()
    elif policy == "random":
        # random per-input depth in [1, 2K-1] with mean ~K (ignores the input)
        alloc = torch.randint(1, 2 * K, (B,), generator=gen).to(start.device)
    elif policy == "random_exact":
        if total_hops is None:
            raise ValueError("random_exact requires total_hops")
        alloc = allocate_input_blind_exact(B, total_hops, gen, start.device)
    elif policy == "adaptive_budgeted":
        if total_hops is None:
            raise ValueError("adaptive_budgeted requires total_hops")
        cur = start.clone()
        idx = torch.arange(B, device=start.device)
        hops = torch.zeros(B, dtype=torch.long, device=start.device)
        active = torch.ones(B, dtype=torch.bool, device=start.device)
        remaining = total_hops
        for _ in range(MAX_M + 2):
            if remaining == 0 or not active.any():
                break
            halt_evaluations += int(active.sum().item())
            nxt = table[idx, cur]
            candidates = (nxt != cur) & active
            candidate_indices = torch.nonzero(candidates, as_tuple=False).flatten()
            if len(candidate_indices) > remaining:
                order = torch.randperm(len(candidate_indices), generator=gen).to(start.device)
                chosen_indices = candidate_indices[order[:remaining]]
                chosen = torch.zeros(B, dtype=torch.bool, device=start.device)
                chosen[chosen_indices] = True
            else:
                chosen = candidates
            spent = int(chosen.sum().item())
            hops += chosen.long()
            cur = torch.where(chosen, nxt, cur)
            remaining -= spent
            if spent < len(candidate_indices):
                break
            active = candidates
        if remaining > 0:
            if active.any():
                raise RuntimeError("adaptive_budgeted failed to spend budget before convergence")
            # All items converged; surplus is explicitly billed as self-loop no-op work.
            hops += allocate_input_blind_exact(B, remaining, gen, start.device)
            remaining = 0
        if int(hops.sum().item()) != total_hops:
            raise RuntimeError("adaptive_budgeted total-hop invariant violated")
        alloc = hops
    elif policy in {"adaptive", "adaptive_noisy"}:
        # halt-on-convergence: number of hops until the node stops changing,
        # i.e. exactly m(x). Realised by following until the self-loop.
        cur = start.clone()
        idx = torch.arange(B, device=start.device)
        hops = torch.zeros(B, dtype=torch.long, device=start.device)
        active = torch.ones(B, dtype=torch.bool, device=start.device)
        for _ in range(MAX_M + 2):
            halt_evaluations += int(active.sum().item())
            nxt = table[idx, cur]
            moved = (nxt != cur) & active
            if policy == "adaptive_noisy" and halt_false_positive_rate > 0.0:
                false_halt = (
                    torch.rand(B, generator=gen).to(start.device) < halt_false_positive_rate
                ) & moved
                moved &= ~false_halt
            hops += moved.long()
            active = moved
            cur = torch.where(moved, nxt, cur)
            if not active.any():
                break
        if policy == "adaptive" and active.any():
            raise RuntimeError(
                f"adaptive halt did not converge for {int(active.sum().item())} inputs"
            )
        alloc = hops
    else:
        raise ValueError(policy)
    cur = _final_node(table, start, alloc)
    result = _metrics(cur, values, target, m, alloc)
    result["halt_evaluations"] = halt_evaluations
    return result

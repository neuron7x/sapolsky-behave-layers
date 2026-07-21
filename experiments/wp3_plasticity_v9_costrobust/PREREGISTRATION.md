# PREREGISTRATION — L4g Robustness to the Cost Model

**Committed before the run.** L4 defined utility as `new_acc − λ·(params/params_max)` — a
**linear** cost normalization. A validity threat: is the oracle gap an artifact of that specific
cost shape? This tests whether identifiability and governor recovery survive alternative
monotone cost transforms at the same budget.

## Design (frozen)

- Real measured `new_acc` and `cost_params` from the 16 confirmatory seeds
  (`artifacts/wp3-plasticity-v2-confirmatory/raw_runs`), contexts {lexical, relational}, arms
  {attn, mlp, head, embed}.
- **Cost transforms** `f`, each normalized by `f(params_max)`:
  `linear` `f(x)=x`; `sqrt` `f(x)=√x`; `log` `f(x)=log(1+x)`; `square` `f(x)=x²`.
  (These span sub- to super-linear curvature; `log` even makes the cheap `head` group expensive,
  penalty 0.69.)
- Utility `U_f[t,a] = new_acc[t,a] − λ·f(cost_a)/f(params_max)`, `λ=1` fixed.
- For each transform: (a) aggregate certificate `G_lo` (`identifiability_inference`, δ=0.05,
  se from the 16 seeds); (b) a reward-only REINFORCE governor's held-out recovery (train seeds
  5–12, eval 13–20, 8 controller seeds, worst reported).

## Decision rule (FROZEN)

- **L4G_ROBUST** iff, for **all four** transforms: `G_lo > 0` (still identifiable) AND worst
  governor recovery `≥ 0.8` (still recoverable).
- **L4G_COST_SHAPE_DEPENDENT** — at least one monotone transform drops `G_lo ≤ 0` or governor
  recovery `< 0.8`: the L4 result depends on the cost-shape choice (a real validity limitation
  to record).

## Scope / prohibited

Tier `SYNTHETIC`. A robustness/validity check of the L4 identifiability claim, not a new
capability. New claim `CWC-L4g-cost-robust`. Does not establish real-workload behavior, L7,
energy/latency, or independent replication.

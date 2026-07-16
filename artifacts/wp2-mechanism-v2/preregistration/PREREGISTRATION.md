# WP-2 Mechanism-Separable Routing (Act v2.0 A2+A3) — PREREGISTRATION

Registered 2026-07-16 before the 8-seed run; committed before analysis.
Authority: CWC Remediation & Evidence-Closure Act v2.0, packages A2 and A3.

## Why this experiment
WP-2 v1/v1.1 returned NOT_SUPPORTED/COLLAPSE, but with a proven limitation:
the tasks were label-heterogeneous, not MECHANISM-heterogeneous — any block
solved any subtask, so routing was unidentifiable (no oracle gap). Act A2
requires a benchmark where a fixed route MUST fail one family, validated by an
oracle gap BEFORE training a learned router.

## Benchmark (A2)
Two structurally non-substitutable operators:
- **E_A (local)**: causal attention restricted to window [t−2, t]. Solves
  LOCAL (copy t−1); cannot reach a far position.
- **E_B (far)**: causal attention restricted to [0, t−3] (local window masked
  out). Solves FAR (copy position 1); cannot see a neighbour.
Tasks: LOCAL (answer = token at t−1), FAR (answer = token at position 1),
p=0.5. K=1 active block over {E_A, E_B}. A fixed route fails one family.

### A2 oracle-gap gate (must pass BEFORE routing claims)
`G = (L_best_fixed − L_oracle) / L_best_fixed`. PASS iff mean relative gain
≥ 0.10, lower 95% CI > 0.05, oracle acc > 0.9 on BOTH families. If FAIL →
routing BLOCKED, redesign benchmark (do NOT touch the controller).
Prior validation (1 seed, pre-registration): fixed-E_A LOCAL=1.0/FAR=0.0,
fixed-E_B LOCAL=0.05/FAR=1.0, oracle=1.0/1.0 — gap ≈ 99% (gate expected to
pass at 8 seeds).

## Routing causality (A3)
Controls: dense (ceiling), random, frozen, fixed, oracle (benchmark control),
learned. Two stages:
- **Stage A (marker)**: explicit task flag at position 0. Tests optimization/
  capacity.
- **Stage B (inferred)**: no flag; type inferred from position-1 content range.

### Hypotheses
- H_R1: `ce(learned) < ce(frozen)`; H_R2: `ce(learned) < ce(fixed)`;
  also `< ce(random)`. Upper paired 95% CI < 0.
- H_R3: `I_norm(R;T) ≥ 0.25`, lower bootstrap 95% CI ≥ 0.15,
  permutation-test p ≤ 0.01 (R = chosen block, T = task family).

### Causal interventions (learned, eval)
force-correct (route = label) → approaches oracle; force-incorrect (inverted)
→ ce spikes (ratio incorrect/correct ≥ 1.5); route-permute → destroys
advantage; module-swap (E_A↔E_B, keep routes) → predicted failure.

### A3 verdict
`ROUTING_CAUSALITY_SUPPORTED` iff learned beats random+frozen+fixed AND MI gate
AND intervention gate AND ≥8 seeds. Else NOT_SUPPORTED / SUPPORTED_WEAK.

## Fixed design
Model: d_model=64, n_head=4, d_ff=128, 2 blocks, K=1. Task seq_len=32,
content_len=20. Train 1500 steps, AdamW lr=1e-3, batch=64. Val=1024 fixed
(Generator 999_999). Seeds 0..7 (8, claim tier). Energy EXCLUDED
(INSTRUMENT_INVALID). No threshold changed after seeing results. NULL is a
valid completion (Act §15).

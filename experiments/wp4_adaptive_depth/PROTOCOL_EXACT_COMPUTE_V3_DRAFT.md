# WP4 Exact-Compute v3 — DRAFT PROTOCOL, NOT REGISTERED

Status: `DRAFT_DO_NOT_RUN_CONFIRMATORY`.

This file must be reviewed, assigned a final power calculation, committed in a
dedicated protocol-only commit, and externally timestamped before confirmatory
data generation.

## Research question

At identical total executed operator steps, does allocation conditioned on a
halt signal improve solved rate over the strongest input-blind allocation, and
how does that value degrade when the halt signal is noisy or costly?

## Estimand and unit

- Primary estimand: paired difference in solved rate,
  `adaptive_net - input_blind_exact`, per data seed.
- `adaptive_net` charges controller/halt cost in operator-step equivalents.
- Statistical unit: independently generated data seed.
- Allocation permutations are nested Monte Carlo replicates, not independent
  statistical units.

## Arms

1. `input_blind_exact`: floor/ceiling depths, randomly permuted, exact total hops.
2. `adaptive_exact_halt`: current positive-control oracle.
3. `adaptive_noisy_halt`: false-positive and false-negative halt grids fixed below.
4. `adaptive_cost_charged`: halt/controller cost deducted from its hop budget.
5. `oracle_m`: descriptive ceiling only; cannot win a claim.

## Fixed stress grid

- Distributions: uniform, easy-skew, hard-skew, bimodal, plus held-out shifted
  mixtures fixed before registration.
- Halt false-positive rates: `{0.01, 0.05, 0.10}`.
- Halt delay rates: `{0.01, 0.05, 0.10}`.
- Controller costs: `{0.01, 0.05, 0.10, 0.25}` operator-step equivalents per
  decision, charged to total compute.
- Sequence/task sizes: at least three preregistered `(N_NODES, MAX_M)` scales.

## Compute contract

For every paired cell, all claim-bearing arms must satisfy:

`abs(total_ops_arm - total_ops_control) / total_ops_control <= 0.01`.

`total_ops` includes operator steps, halt evaluations, controller forward cost,
padding/wasted dispatch, and retries. A missing cost component invalidates the
cell; it is never imputed as zero.

## Leakage and information boundary

- The input-blind arm may know only the global preregistered budget, not batch
  labels or realized per-item difficulties.
- Any budget estimated from a pilot distribution is frozen before confirmatory
  generation and applied unchanged to held-out data.
- Halt-signal generation and corruption use independently seeded streams.

## Statistics

- Final seed count must be computed from the exploratory pilot using a frozen
  minimum meaningful effect and conservative variance estimate.
- Paired exact randomization test is primary; hierarchical bootstrap is
  descriptive.
- Holm correction across the fixed stress-grid primary contrasts.
- Report median, MAD, CI, worst seed, and collapse/failure probability.

## Fail-closed decision

`SUPPORTED_NARROWED` only if the compute contract passes in every primary cell,
the corrected lower confidence bound exceeds the preregistered meaningful effect,
and the advantage survives at least one non-zero halt-noise and non-zero-cost
condition. Otherwise `NOT_SUPPORTED`, `NOT_IDENTIFIABLE`, or
`MEASUREMENT_INVALID` according to the failed gate.

## Prohibited interpretation

Even a positive result cannot establish real-workload utility, neural-controller
learnability, architectural novelty, energy efficiency, scaling, or independent
replication.

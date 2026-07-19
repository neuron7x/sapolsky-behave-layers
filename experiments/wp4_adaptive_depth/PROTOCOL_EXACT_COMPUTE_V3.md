# WP4 Exact-Compute v3 — INTERNAL PROTOCOL FREEZE

Status: `INTERNAL_PROTOCOL_GIT_TIMESTAMP_ONLY`.

This protocol is frozen in a dedicated protocol-only Git commit before result
generation. No external immutable timestamp or independent operator is available;
therefore the resulting run may be called **internal confirmatory** only, never
externally preregistered or independently replicated.

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
3. `adaptive_noisy_halt`: false-positive halt grid fixed below; secondary stress arm.
4. `adaptive_cost_charged`: halt/controller cost recorded in milli-hop equivalents;
   secondary accounting arm, not claim-bearing until a real controller exists.
5. `oracle_m`: descriptive ceiling only; cannot win a claim.

## Fixed stress grid

- Development distributions: uniform, easy-skew, hard-skew, bimodal.
- Held-out shifts fixed here: `extreme_easy=[12,8,4,2,1,1,1,1]`,
  `extreme_hard=[1,1,1,1,2,4,8,12]`, `mid_peak=[1,2,6,10,10,6,2,1]`.
- Halt false-positive rates: `{0.01, 0.05, 0.10}`.
- Halt delay rates: `{0.01, 0.05, 0.10}`.
- Controller costs: `{0.01, 0.05, 0.10, 0.25}` operator-step equivalents per
  decision, charged to total compute.
- Task size is fixed at the current `(N_NODES=24, MAX_M=8)`; no scaling claim.

## Compute contract

For every paired primary cell, all claim-bearing arms must satisfy exact integer
operator-hop equality:

`total_operator_hops_arm == total_operator_hops_control`.

Secondary cost arms additionally report halt evaluations in integer milli-hop
equivalents. They cannot support a Pareto claim because no learned controller is
present. A missing cost component invalidates that arm; it is never imputed as zero.

## Leakage and information boundary

- The input-blind arm may know only the global preregistered budget, not batch
  labels or realized per-item difficulties.
- Any budget estimated from a pilot distribution is frozen before confirmatory
  generation and applied unchanged to held-out data.
- Halt-signal generation and corruption use independently seeded streams.

## Statistics

- Pilot seeds `0..7` are excluded. Internal confirmatory data seeds are exactly
  `100..115` (16 seeds), with 32 nested input-blind allocation permutations and
  batch size 4096 per distribution/seed.
- Pilot maximum seed-level SD was 0.01330. With two-sided alpha 0.05, power 0.80,
  and minimum meaningful paired solved-rate effect 0.05, the normal approximation
  gives `n=1`. We deliberately use 16 because pilot variance is synthetic and
  anti-conservative for held-out/noisy conditions; nested permutations are not
  counted as independent units.
- Paired exact randomization test is primary; hierarchical bootstrap is
  descriptive.
- Holm correction across the fixed stress-grid primary contrasts.
- Report median, MAD, CI, worst seed, and collapse/failure probability.

## Fail-closed decision

`SUPPORTED_NARROWED_INTERNAL` only if the exact-hop contract passes in every
primary cell and Holm-corrected paired randomization lower bounds exceed the
minimum meaningful effect 0.05 on all four development distributions and at
least two of three held-out shifts. No noisy/cost arm can raise the claim.
Otherwise `NOT_SUPPORTED`, `NOT_IDENTIFIABLE`, or
`MEASUREMENT_INVALID` according to the failed gate.

## Prohibited interpretation

Even a positive result cannot establish external preregistration, real-workload utility, neural-controller
learnability, architectural novelty, energy efficiency, scaling, or independent
replication.

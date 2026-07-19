# WP4 Epistemic Correction — 2026-07-19

## Status

This record **supersedes the interpretation**, but not the immutable files, in
`artifacts/wp4-adaptive-depth/`.

## What the evidence establishes

On the exact synthetic pointer-chase substrate, a policy that runs until the
absorbing state solves every item, while a fixed integer-depth policy solves
exactly the items with `m <= K`. Therefore the observed solved-rate difference
equals the empirical tail mass `P_sample(m > K)`. The implementation reproduces
this identity and the associated controls.

## What the evidence does not establish

1. The equality is an executable algebraic identity of the benchmark, not an
   independent empirical prediction: both sides are computed from the same
   sampled `m` values.
2. Compute is not exactly matched. Adaptive compute is `E_sample[m]`; static
   compute is integer `K = round(E_sample[m])`. The archived runs differ by
   approximately 0.095--0.223 hops depending on the regime.
3. The adaptive policy receives an exact convergence signal. No learned stopping
   rule, noisy halt signal, controller cost, or real workload is validated.
4. The original protocol and results first entered Git history in the same
   commit. The theory commit predates the run, but the experiment document is not
   an independently timestamped preregistration.

## Correct claim boundary

**SUPPORTED_NARROWED:** the code verifies the synthetic tail-mass identity under
an exact halt oracle. This is a unit test of allocation logic and a positive
control for the identifiability framework.

**NOT TESTED:** compute-equivalent Pareto advantage, learned adaptive stopping,
robustness to noisy/expensive halt signals, real-workload generalization, novelty,
and independent replication.

## Required successor experiment

Use an exactly matched total-operation ledger (relative mismatch <= 1%), a
learned controller whose inference cost is charged, a prediction defined from a
pilot distribution and evaluated on a fresh held-out sample, separately committed
preregistration, strong adaptive baselines, and external reproduction.

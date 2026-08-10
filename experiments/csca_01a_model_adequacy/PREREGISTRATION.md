# CSCA-01A — Counterfactual Model Adequacy Attack

**Status:** FROZEN AFTER CSCA-01, BEFORE CSCA-01A EXECUTION  
**Purpose:** attack the weakest assumption exposed by CSCA-01: oracle-quality counterfactual simulation.

## Question

If the counterfactual evaluator itself contains a spurious structural edge `C -> Y`, does exact
Shapley credit correctly reveal that *model's* attribution rather than the true environment's
causality? If yes, causal-credit quality is bounded by counterfactual-model adequacy.

## True environment

`Y = beta*A + gamma*U + epsilon`, with `C` a non-causal observed proxy.

## Misspecified counterfactual model

`Y_hat = beta_hat*A + alpha*C + gamma*U + epsilon`.

Candidate baseline for `A,C` is symmetric `{-1,+1}`.

## Analytic prediction

For symmetric baseline and linear additive `Y_hat`:

- `|phi_A| = |beta_hat|`;
- `|phi_C| = |alpha|`;
- normalized false-credit mass = `|alpha| / (|beta_hat| + |alpha|)`;
- `C` outranks `A` iff `|alpha| > |beta_hat|`.

## Frozen grid

- `beta_hat in {1.0, 0.5}`;
- `alpha in {0.0, 0.1, 0.25, 0.5, 1.0, 1.25}`;
- exhaustive `A,C in {-1,+1}`.

## Failure predicate

Implementation is rejected if any enumerated Shapley value, false-credit mass, or ranking boundary
differs from the analytic prediction by more than `1e-12`.

## Interpretation boundary

A PASS is **not** support for Shapley robustness. It establishes the opposite boundary: exact credit
faithfully explains the counterfactual model it is given, so a structurally wrong simulator can
create structurally wrong causal credit. The next practical gate must measure counterfactual-model
error/uncertainty rather than assuming it away.

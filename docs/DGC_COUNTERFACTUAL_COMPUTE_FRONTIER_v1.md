# DGC Counterfactual Compute Frontier (CCF) v1

Date: 2026-08-23

## Purpose

CCF is an **offline audit oracle**, not a production routing policy and not a novelty claim.

Given a frozen set of per-task compute alternatives observed under an identical evaluation harness,
CCF solves the finite multi-resource allocation problem exactly:

\[
\max_{a_1,\ldots,a_n}\sum_i V_i(a_i)
\]

subject to

\[
\sum_i C_i(a_i)\le B_C,\qquad
\sum_i L_i(a_i)\le B_L,\qquad
\sum_i R_i(a_i)\le B_R,
\]

with exactly one compute option selected per task.

Costs, values, latency and risk use integer audit units. No floating-point discretization is performed inside
the oracle. The implementation performs exact finite dynamic programming with Pareto dominance pruning.

## Why this matters

A router can look strong against weak heuristics while still leaving large economically avoidable compute on
the table. CCF creates a same-workload upper-bound audit:

- `value_regret_units = oracle_value - policy_value`;
- `avoidable_cost_units = policy_cost - minimum_cost_for_policy_value`, with no worse latency/risk;
- a SHA-256 certificate binds the frozen option table, budgets and selected allocation.

This distinguishes three different statements that must not be conflated:

1. DGC beats a fixed-compute baseline.
2. DGC beats contemporary learned/sequential routers.
3. DGC is close to the best allocation available in the frozen counterfactual option set.

Only (3) is addressed by CCF, and only for the observed finite option set.

## Relationship to prior art

The optimization problem is a finite multi-choice / multi-resource knapsack-style allocation problem.
CCF does **not** claim novelty for that optimization family. Its role in DGC is evidentiary: provide a
deterministic, hash-bound, exact oracle baseline for compute-economics experiments.

Contemporary adaptive-compute work makes this oracle discipline necessary. BEST-Route (ICML 2025) jointly
selects model and sample count and reports large cost reductions at small quality loss; 2026 constrained
test-time allocation work explicitly solves accuracy-vs-budget allocation and learns an amortized policy.
Therefore a DGC product claim must be benchmarked against strong adaptive allocation, not merely uniform
compute or threshold heuristics.

## Validity boundary

CCF is exact only for:

- the frozen tasks included in the option table;
- the frozen options actually measured for each task;
- the declared integer-valued objective/resources;
- additive task-level value and resource accounting;
- hard aggregate resource constraints.

It does not prove:

- that unobserved compute actions are inferior;
- causal transport to new workloads;
- production safety;
- calibrated client economics;
- global optimality of a sequential metareasoning policy under unobserved futures.

## Falsification

`scripts/dgc_product_counterfactual_oracle_gate.py` contains a ratio-greedy counterexample:
a locally attractive high value/cost upgrade blocks two jointly superior upgrades. The exact oracle must
recover value 18 while the greedy allocator obtains 12.

The unit suite also compares the Pareto-DP result against exhaustive enumeration on 100 seeded random
small multi-resource instances.

## Product integration rule

CCF is an **audit oracle outside B0-B3**. It must not replace the frozen real baselines:

- B0 fixed compute;
- B1 uncertainty router;
- B2 learned cost-quality router;
- B3 sequential verification.

External qualification should report both:
`DGC vs B0-B3` and `DGC vs CCF oracle headroom`.

## Robust verification value

The same observable signal can have incompatible implications under two
plausible causal models. A policy must commit to one signal-to-action mapping
before the model is known. For a finite registered set of deterministic
policies, score each policy by its minimum expected net improvement over the
declared no-verification action. Authorize verification when the maximum of
these minima is strictly positive. This is a finite decision problem in the
sense of [Blackwell](https://doi.org/10.1214/aoms/1177729032), with an explicit
worst-case comparison over multiple models.

Inputs are integer incremental utilities, integer joint masses over latent
states and observable signals for each model, a fixed verification cost in the
same units, and precomputed admissible actions for each signal. Normalize each
joint mass array by its own positive total. Action zero is the fallback with
zero incremental utility in every state. Include its constant policy in the
candidate set. Resolve ties by lexicographic order and decline at zero.

### Falsification cases

Fix two equally likely states and a fallback whose utility is zero. Action one
yields +10 in state one and −10 in state zero. Charge one unit. With the state
revealed, intervene only in state one and obtain net +4. Add a model in which
the signal labels are reversed. Each model individually still offers +4, but
no common deterministic policy yields positive net value. The robust optimum
is −1. If only the fallback remains admissible, even the original perfect
signal yields −1. Charging five units instead makes the original informed
policy break even and verification is declined.

The certificate is conditional on the declared models, strategy set, utility
baseline and admissibility sets. The input author must establish coverage of
decision-relevant shifts, justify utilities as intervention consequences,
and account for all incremental costs. If the declared fallback is weak, a
positive value can reflect an available action change without information.
Use an independently established no-verification baseline before interpreting
the result as value caused by a signal. The evaluator is a research oracle.
It has no deployment authority and does not modify the live router.

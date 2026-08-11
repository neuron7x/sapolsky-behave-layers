# CAB-01-Q1-R1 — Leakage-Null Repair Execution Report

**Date:** 2026-08-11  
**Parent CAB design commit:** `a849b63`  
**Parent Q1 negative evidence commit:** `2d3bec65972a213dcdb0f24ef53a4edf4b3f0ec2`  
**R1 preregistration commit:** `fdd89e4c6ef578647e8522035a6bbbb62185c33f`  
**Frozen generator implementation commit:** `a8ed935f1140eb5dba2e971dcf20229831fd1e12`  
**R1 evaluation implementation commit:** `66f04a33993b910d9d035b0722d2aeb4682a34cc`  
**Verdict:** `CAB01_Q1_R1_BENCHMARK_QUALIFIED_SYNTHETIC`

## What R1 tested

R1 was a preregistered repair of the Q1 *leakage-null evaluator only*. The benchmark
families, construction semantics, decision labels, query economics, policy interfaces,
baselines, Pareto criterion and frozen generator implementation were unchanged from Q1.
Fresh seed namespaces were used: `510811` for PRIMARY_R1 and `610811` for
REPLICATION_R1.

The repaired leakage gate was conjunctive:

1. the complete cohort must contain exactly one `surface_signature`; and
2. a deterministic held-out surface-only classifier must not outperform the majority
   class rate of that same held-out fold, up to the frozen `1e-12` numerical tolerance.

This directly attacks the Q1 harness failure without reclassifying or deleting the Q1
negative.

## Confirmatory result

Both PRIMARY_R1 and REPLICATION_R1 executed `1792` cases:

- F0-F10: `128` cases per family;
- F11: `128` mutation groups, each containing ACT/QUERY/ABSTAIN variants (`384` cases);
- construction/analytic/runtime label disagreements: `0`;
- F11 triad violations: `0`;
- unique surface signatures: `1`;
- held-out size: `359`;
- held-out surface-only accuracy: `0.28690807799442897`;
- held-out majority-class rate: `0.28690807799442897`;
- full-cohort majority-class rate, reported but not used as the R1 null:
  `0.2857142857142857`;
- byte regeneration/replay hashes matched independently in both cohorts.

Both constant policies remained Pareto-dominated by the non-oracle
`robust_worst_case_no_query` policy, satisfying the frozen non-degeneracy requirement.
No qualification error remained.

## Baseline observations

The following are properties of this synthetic benchmark and nothing broader:

- `decision_relevant_information` matched the benchmark construction labels on every
  generated case, with terminal accuracy `1.0`, necessary-query recall `1.0`, false
  causal-authority rate `0.0`, wrong irreversible-action rate `0.0`, and unnecessary
  query cost `0.0` in both cohorts;
- `robust_worst_case_no_query` achieved terminal accuracy `0.7142857142857143` with
  necessary-query recall `0.0` and zero query cost;
- `full_model_maximin` achieved terminal accuracy `0.7142857142857143`, necessary-query
  recall `0.0`, and query cost `0.07142857142857142` per case;
- `always_act` had terminal accuracy `0.21428571428571427` and false causal-authority
  rate `0.7857142857142857`;
- `always_abstain` had terminal accuracy `0.2857142857142857`.

The exact match of `decision_relevant_information` is a benchmark/software coherence
result because the benchmark semantics and runtime governor are deliberately aligned. It
is not independent evidence of general cognitive performance.

## Null attack and interpretation

R1 falsifies the specific alternative explanation that Q1's leakage failure came from a
surface feature that encoded the terminal class: the entire R1 cohort again had one
surface signature, and the held-out classifier equalled its own held-out majority null.
It does **not** falsify semantic leakage through generator design, shared abstractions,
benchmark-family knowledge, privileged structured inputs or task-construction bias.
Those require later natural-language contamination tests, independently authored task
instances and public/external transfer.

The Q1 negative remains immutable and scientifically useful: it exposed an invalid null
comparison across different class priors. R1 qualifies the repaired synthetic benchmark
harness; it does not retroactively turn Q1 into a pass.

## Authority boundary

`CAB01_Q1_R1_BENCHMARK_QUALIFIED_SYNTHETIC` licenses only the statement that the frozen
synthetic CAB-01 qualification harness satisfies its R1 construction, replay, oracle,
mutation, leakage and baseline non-degeneracy gates under two fresh internal cohorts.

Still forbidden:

- CWC superiority;
- semantic causal truth;
- real-model transfer;
- natural-language contamination resistance;
- large-model matched-compute Pareto advantage;
- external independent replication;
- flagship-result promotion.

Novelty remains `UNKNOWN_OVERLAP_CONCEDED`.

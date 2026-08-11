# CAB-01-Q1 — Causal Authority Benchmark Qualification Execution Report

**Date:** 2026-08-11  
**Parent design commit:** `a849b63`  
**Execution preregistration commit:** `f55fde0f7eee54f88f6f0443d3de48dbbb582afe`  
**Implementation commit:** `a8ed935f1140eb5dba2e971dcf20229831fd1e12`  
**Verdict:** `CAB01_Q1_NOT_QUALIFIED`

## Frozen result

Q1 did not satisfy its preregistered benchmark-qualification conjunction. The failure is
preserved as evidence and is not reclassified as a pass.

Both PRIMARY and REPLICATION executed `1792` cases: `128` instances for each of F0-F10
plus `128` F11 mutation groups, each containing ACT/QUERY/ABSTAIN variants. In both
cohorts:

- deterministic regeneration hashes matched byte-for-byte;
- family counts matched the frozen protocol;
- construction labels, the independent analytic oracle and the CWC runtime oracle had
  `0` disagreements;
- every F11 mutation group contained exactly one ACT, one QUERY and one ABSTAIN terminal
  class with the same surface-shape signature;
- always-ACT and always-ABSTAIN were each Pareto-dominated by the non-oracle
  `robust_worst_case_no_query` baseline.

The only qualification failure was the surface-leakage threshold:

- preregistered cohort-majority reference: `0.2857142857142857`;
- held-out surface-only classifier accuracy: `0.28690807799442897`;
- result: FAIL in PRIMARY and again FAIL in REPLICATION.

## Null attack on the failure

Post-result diagnosis found exactly **one unique surface signature** in each full cohort.
Therefore the surface-only classifier had no feature capable of separating states. Its
held-out prediction collapsed to the training-fold majority class. The held-out fold's
own majority-class rate was exactly `0.28690807799442897`, matching the observed
classifier accuracy. The preregistered comparison used the *full-cohort* majority rate,
so deterministic modulo-5 splitting introduced a small class-prior mismatch.

This diagnosis does not alter the Q1 verdict. It identifies a qualification-harness
problem: the null reference and evaluation fold were drawn from different class priors.

## Baseline observations

These are benchmark-internal descriptive results, not external model claims:

- `decision_relevant_information` matched the hidden-state construction labels on all
  generated cases in both cohorts, with zero false causal authority and zero unnecessary
  query cost under the Q1 generator;
- `full_model_maximin` terminal accuracy was `0.7142857142857143` in both cohorts and its
  necessary-query recall was `0`; F8 explicitly separates model-information and
  decision-information selection;
- `generic_predictive_uncertainty` over-queried high-aleatoric F4 cases and produced
  nonzero false-action/error rates;
- the hidden-state oracle is a ceiling and licenses no CWC superiority claim.

Because the generator and the decision-relevant policy share declared benchmark
semantics, the exact synthetic match is a software/benchmark coherence result, not an
independent cognitive-performance result.

## Immutable boundary

Q1 remains `NOT_QUALIFIED`. No threshold is repaired in place. Any retry must use a new
preregistration, fresh seed namespaces and an explicit leakage null that compares held-out
accuracy to the held-out class prior (plus a structural unique-signature check).

Still unlicensed: CWC superiority, real-model transfer, natural-language contamination
resistance, semantic causal truth, large-model Pareto advantage, external replication and
CAB-01 flagship promotion.

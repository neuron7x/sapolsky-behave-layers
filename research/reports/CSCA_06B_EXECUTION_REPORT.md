# CSCA-06B-OP — Intervention-Operator Family Robustness

**Date:** 2026-08-10  
**Verdict:** `OPERATOR_FAMILY_ROBUSTNESS_QUALIFIED_NARROWED`  
**Architectural utility:** `BLOCKED_RECENCY_DOMINATED_ZERO_NONRECENT_ROBUST_CASES`

## Why this experiment was necessary

CSCA-05 qualified only `do(span=ASCII_SPACE)`, then a post-confirmatory diagnostic showed top-candidate invariance `0.84375` and sign invariance `0.71875` across SPACE/ZERO/0xFF/REVERSE. Treating those arbitrary corruptions as interchangeable implementations of one semantic `do()` would be invalid.

CSCA-06B therefore changed the question. It defined two explicit stochastic **soft-intervention kernels** and tested robustness across that declared family. It does not assert latent semantic equivalence.

## Operator family

For every ablated 4-byte player span, exact utility is the arithmetic expectation of `log P(y*)` over eight hash-frozen non-identical contiguous same-context donor assignments.

- `K_TRAIN_CONTIG8`: donor bytes from the same-context training corpus;
- `K_COHORT_CONTIG8`: donor bytes from the same-context held-out cohort corpus.

The expectation is finite and exactly evaluated; exact ablation-Shapley is then computed on the expected coalition game. Eight donor realizations are batched physically but remain eight logical intervention realizations.

Legacy ASCII_SPACE is diagnostic only.

## Pre-execution integrity

The first CLI attempt failed at import before model/data evaluation. Amendment 001 repaired only repository-root import hermeticity.

The next calibration attempt exceeded 300 seconds before producing any artifact. Amendment 002 batched the same eight intervention realizations into one tensor forward per coalition. No prompt, donor, threshold, cohort or scientific rule changed. The successful calibration produced the first scientific output.

Calibration was then committed before PRIMARY. It froze:

`q10(min operator-family top gap) = 1.66525005325675`

and, by the preregistered clipped rule,

`delta = 0.25`.

## PRIMARY

48 fresh prompt units, 24 PROSE + 24 CODE, zero prompt-hash overlap with CSCA-05.

Pooled:

- top-candidate agreement between the two admissible kernels: `48/48 = 1.0`;
- sign agreement: `48/48 = 1.0`;
- robust-authority coverage: `48/48 = 1.0`;
- model-state mutations: `0`;
- robust non-recent cases: `0/48`;
- robust `A_RECENT` cases: `48/48`;
- legacy SPACE top agreement on robust cases: `44/48 = 0.9166667`;
- median L1 credit-vector distance between the two admissible kernels: `0.17969038`.

PROSE and CODE separately satisfy all frozen `>=0.90` agreement and `>=0.50` coverage predicates.

**PRIMARY PASS.**

## Independent REPLICATION

A separately trained frozen nanochat checkpoint and the replication document partition:

- top agreement: `48/48 = 1.0`;
- sign agreement: `48/48 = 1.0`;
- robust coverage: `48/48 = 1.0`;
- model-state mutations: `0`;
- prompt overlap with CSCA-05: `0`;
- robust non-recent cases: `0/48`;
- robust `A_RECENT`: `48/48`;
- legacy SPACE agreement: `46/48 = 0.9583333`.

**REPLICATION PASS.**

## Positive result

The narrow operator-specific defect from CSCA-05 is reduced: when “content erasure” is implemented as two different explicitly declared same-context donor-resampling kernels, the exact top causal-credit candidate and its sign are invariant on every tested fresh PRIMARY and replication prompt.

## Decisive negative boundary

Every robust case in both cohorts selects `A_RECENT`; there are **zero robust non-recent cases**.

Thus this experiment does not demonstrate content-specific, semantic, memory-level or abstract causal reasoning. A much simpler explanation remains viable: for next-token prediction in this byte-level task, causal sensitivity is dominated by distance to the prediction boundary. Operator robustness may therefore be robustness of **autoregressive recency/locality**, not of a higher cognitive variable.

This is not hidden by the positive qualification. It blocks amortized-student promotion as an architectural utility claim until the position/content confound is attacked.

## Authority

Qualified narrowly:

`DIRECT_INTERVENTION_OPERATOR_FAMILY_ROBUST_SHADOW_MEASUREMENT`.

Still blocked:

- semantic intervention equivalence;
- semantic causal authority;
- content-specific causal credit;
- amortized/student causal authority;
- replay;
- active control.

## Next hard gate

`CSCA-06C — Position/Content Causal Disentanglement`.

Permute the four candidate contents across their positions while retaining explicit position labels. If causal credit follows `A_RECENT` rather than the moved content identity, the current real-model result is a position/locality mechanism and must not be promoted as a cognitive-content mechanism.

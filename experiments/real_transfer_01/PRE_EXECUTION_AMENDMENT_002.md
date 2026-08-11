# REAL-TRANSFER-01 — Pre-Execution Amendment 002

Date frozen: 2026-08-11
Status: PRE-EXECUTION / NO MODEL OUTPUTS OBSERVED
Parent preregistration commit: `cd23922734bdb6f04d3835a31c291cbf6328f75e`
Amendment 001 commit: `54b4a06ccf7d4925739929176dae0d098356be4d`

## Defect found by pre-implementation null attack

The parent resource rule stated that candidate total resource use must be <= every
required baseline. On HybridQA, `ALWAYS_ACT` intrinsically uses zero external query
units, while every correct target behavior requires `QUERY_COMPLEMENT`. Therefore that
predicate would make a scientifically correct candidate incapable of passing by logical
construction.

A predicate that cannot be satisfied by the frozen gold behavior is not a falsification
gate; it is a malformed gate. This amendment repairs only the matched-cost comparison
relation before implementation or model execution.

## Frozen baseline roles

Required baselines remain unchanged and none may be dropped. They are partitioned into:

### Boundary/null baselines
- `ALWAYS_ACT`
- `ALWAYS_QUERY`
- `ALWAYS_ABSTAIN`

These expose collapse/safety/resource extremes. They are required for reporting and for
specific frozen endpoints, but are not all pairwise matched-cost superiority targets.

### Direct policy comparators
- `MAX_SCORE_MARGIN`
- `MODEL_ID_MAXIMIN`

These are the direct alternatives against which decision-relevant policy superiority may
be claimed when resource accounting is comparable.

## Frozen matched-cost relations

### AVeriTeC

There is no external query operation. `DECISION_RELEVANT` must be resource-matched to
`MAX_SCORE_MARGIN` and `MODEL_ID_MAXIMIN`:

`candidate.model_forward_calls <= comparator.model_forward_calls`
and
`candidate.total_tokens <= comparator.total_tokens`

for each cohort aggregate.

`ALWAYS_ACT` and `ALWAYS_ABSTAIN` remain mandatory safety/collapse nulls but are exempt
from matched-cost superiority because their policy semantics may require fewer model
operations.

### HybridQA

Required resource predicates are:

1. `DECISION_RELEVANT.external_query_units <= ALWAYS_QUERY.external_query_units`;
2. for `MAX_SCORE_MARGIN` and `MODEL_ID_MAXIMIN`,
   `DECISION_RELEVANT.external_query_units <= comparator.external_query_units` **when**
   the comparator reaches necessary-query recall >= 0.90;
3. if a direct comparator has necessary-query recall < 0.90, it remains a safety/null
   comparator for that cohort and no cost-superiority claim against it is permitted;
4. among policies satisfying necessary-query recall >= 0.90, candidate model forward
   calls and total tokens must be <= the direct comparator for a matched-compute claim.

Therefore a low-cost comparator cannot win merely by refusing a gold-required
information operation.

## Authority consequence

If no direct comparator reaches the HybridQA necessary-query eligibility floor in a
cohort, REAL-TRANSFER-01 may still report behavioral transfer but the matched-compute
superiority component is `NOT_TESTED`; full `REAL_TRANSFER_01_PASS` is forbidden.

All behavioral endpoints, thresholds, action mappings, cohort rules, mutation attacks,
and non-promotion boundaries from the parent plus Amendment 001 remain unchanged.

## Temporal boundary

This amendment must be a strict Git ancestor of every REAL-TRANSFER-01 implementation,
model output, result, and verdict artifact.

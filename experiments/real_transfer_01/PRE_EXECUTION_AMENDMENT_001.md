# REAL-TRANSFER-01 — Pre-Execution Amendment 001

Date frozen: 2026-08-11
Status: PRE-EXECUTION / NO MODEL OUTPUTS OBSERVED
Parent preregistration commit: `cd23922734bdb6f04d3835a31c291cbf6328f75e`

## Why this amendment exists

Source-schema inspection performed before implementation exposed two protocol defects
that are independent of any candidate-model output:

1. the AVeriTeC project page names the fourth class
   `Conflicting Evidence/Cherry-picking`, while the authoritative raw development JSON
   uses `Conflicting Evidence/Cherrypicking`;
2. the parent fixed 16+64+64 quota per AVeriTeC label makes executability depend on an
   arbitrary per-class cardinality that was not established before the freeze.

This amendment repairs source normalization and cohort construction only. It does not
change any behavioral endpoint, baseline, authority boundary, or result threshold.

## Frozen AVeriTeC label normalization

The adapter accepts exactly these source literals:

- `Supported` -> canonical `SUPPORTED`
- `Refuted` -> canonical `REFUTED`
- `Not Enough Evidence` -> canonical `NOT_ENOUGH_EVIDENCE`
- `Conflicting Evidence/Cherrypicking` -> canonical `CONFLICTING_EVIDENCE`
- `Conflicting Evidence/Cherry-picking` -> canonical `CONFLICTING_EVIDENCE`

No fuzzy/string-similarity mapping is permitted. Any other label literal fails schema
validation.

Frozen action mapping is unchanged:
- `SUPPORTED` -> `ACT_SUPPORTED`
- `REFUTED` -> `ACT_REFUTED`
- `NOT_ENOUGH_EVIDENCE` -> `ABSTAIN`
- `CONFLICTING_EVIDENCE` -> `REJECT_SINGLE_VERDICT_MODEL`

## Frozen AVeriTeC cohort construction repair

Use every admissible development record, independently within each canonical label.
Order by the parent canonical record SHA-256. For a label with `N` records:

- `n_cal = floor(0.20 * N)`
- `n_primary = floor(0.40 * N)`
- CALIBRATION = first `n_cal`
- PRIMARY = next `n_primary`
- REPLICATION = all remaining records

Minimum-executability predicate per label:
`n_cal >= 5 AND n_primary >= 10 AND n_replication >= 10`.

If any label fails that predicate, AVeriTeC is
`NOT_EXECUTABLE_FROZEN_MINIMUM` and no quota repair is allowed.

This rule is frozen before model execution and consumes the entire external dev split;
it cannot select or discard records based on model performance.

## Frozen HybridQA exact-match normalization

`ACT_ANSWER` exact match uses the standard normalization implemented locally as:

1. Unicode string converted to lowercase;
2. ASCII punctuation removed;
3. English articles `a`, `an`, `the` removed as whole words;
4. whitespace collapsed to single spaces.

EM = 1 iff normalized prediction equals normalized official gold answer.
No semantic/LLM judge, substring credit, or post-hoc alias list is allowed.

HybridQA cohort sizes and all other parent rules remain unchanged.

## Temporal boundary

This amendment must be a strict Git ancestor of every REAL-TRANSFER-01 implementation,
source manifest, model output, result, and verdict artifact. If not, the experiment is
invalid as confirmatory evidence.

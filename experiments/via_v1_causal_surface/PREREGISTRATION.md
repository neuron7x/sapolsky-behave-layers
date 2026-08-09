# VIA-V1 — Causal Compute-Utility Surface: sealed-evidence re-analysis

**Class:** RETROSPECTIVE METHOD VALIDATION ONLY.
**Scientific ascension ceiling:** NONE. This run cannot reopen the WP18 kill rule or authorize VIA-V2.

## Question

Does the newly isolated `cwc.causal` substrate reproduce the direction of already frozen CWC
adaptive-compute evidence, reject additive/collapsed structural nulls, and fail closed under the
prior kill rule?

This is intentionally **not** a new real-workload experiment. All inputs already exist and were
sealed before this implementation.

## Frozen input bundles

1. WP18 prose, tied-K compute axis.
2. WP18 code, tied-K compute axis.
3. WP19 prose, untied-depth compute axis.
4. WP19 code, untied-depth compute axis.
5. AC1 synthetic adaptive-compute positive control.

No other workload may be added after seeing this analysis.

## Estimand

For each replicate matrix, rows are contexts and columns are actions. Across replicate matrices we
estimate the cell means and conservative maximum cell standard error. Primary certificate:

`G_lo = gap_lower_confidence_bound_corrected(plugin_gap(U_hat), max_cell_se, n_contexts, n_actions, 0.05)`

Existing measured routing cost is read from WP18 evidence and is not re-estimated.

## Mandatory method checks

- `destroy_interaction(mean_matrix)` must have oracle gap ≤ 1e-12.
- `collapse_context(mean_matrix)` must have oracle gap ≤ 1e-12.
- context-row permutation is a deterministic diagnostic null (fixed seed); it is not a new
  confirmatory p-value because the source evidence is retrospective.
- AC1 must remain a strong positive control under the same certificate.
- WP18/WP19 real bundles must not be promoted above their frozen status.

## Decision

The only admissible verdicts are:

- `VIA_V1_METHOD_VALIDATED_ASCENSION_BLOCKED` — causal substrate is internally coherent and frozen
  evidence is reproduced, but prior kill rule remains binding.
- `VIA_V1_METHOD_INVALID` — implementation disagrees with sealed evidence or a structural null has
  nonzero opportunity.
- `VIA_V1_VOID` — required frozen evidence is missing/corrupt.

There is deliberately no `VIA_V1_PASS` outcome in this retrospective run.

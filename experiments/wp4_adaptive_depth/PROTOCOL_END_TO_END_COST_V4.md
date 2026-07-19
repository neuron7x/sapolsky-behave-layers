# WP4 End-to-End Cost v4 — Prospective Internal Protocol

Status: `INTERNAL_FREEZE_REQUIRED_BEFORE_IMPLEMENTATION_OR_RUN`.

## Why v4 exists

v3.1 established an allocation advantage only when halt detection was outside the
matched operator-hop budget. In this substrate, however, convergence is detected by
reading the same successor table used to advance the state. A claim about end-to-end
efficiency must therefore charge that read. v4 is a new falsification test; it does not
retroactively alter the valid, narrower v3.1 result.

## Frozen cost model

- Atomic billed operation: one successor-table lookup for one item, cost `1000`
  millihops.
- A lookup both advances a nonterminal item and reveals whether its current node is a
  self-loop. It is billed once, not once as a hop and again as a halt test.
- The adaptive arm must perform and pay for the terminal self-loop lookup needed to
  know that it can halt. It may not inspect `m`, labels, targets, future successors, or
  any unbilled table entry.
- Tensor/vectorization does not change logical cost. Controller arithmetic and random
  scheduling are reported as unpriced limitations; no wall-clock/FLOP claim is allowed.
- Every arm must bill exactly the distribution-specific budget. Surplus after all items
  terminate is explicit paid self-loop padding; an unfinished item at exhaustion fails.

For distribution `d`, the budget is
`1000 * FROZEN_TOTAL_HOPS[d]`, using the prospective, distribution-derived v3.1
totals. It never depends on realized `m`.

## Frozen arms and estimand

1. `input_blind_exact`: exactly the v3.1 randomly permuted floor/ceiling lookup
   allocation; every allocated lookup advances or reads a self-loop.
2. `adaptive_paid_probe`: online active-set scheduling; each selected item consumes one
   lookup, moves if nonterminal, and becomes inactive only after a paid self-loop read.

Primary paired estimand per seed/distribution:
`solved(adaptive_paid_probe) - mean_r solved(input_blind_exact_r)`.

## Frozen data and analysis

- Seeds: exactly `300..315`; all seeds `0..215` are prohibited.
- Batch size: `4096`; input-blind allocation replicates: `32`.
- Distributions and budgets: the same four development and three held-out cells as
  v3.1.
- MDE: `0.02` solved fraction.
- Per-cell 95% bootstrap CI over 16 paired seed effects and exact sign-flip
  randomization p-value; Holm correction across seven cells.
- A cell passes iff its lower CI bound is above `0.02`, Holm-adjusted `p < 0.05`, all
  cost/data invariants hold, and its worst seed effect is positive.
- Overall support requires all four development cells and at least two of three held-out
  cells to pass. Otherwise the verdict is `END_TO_END_ADVANTAGE_NOT_SUPPORTED`.

This protocol is internal and Git-ordered, not externally timestamped or independently
preregistered. Implementation, tests, execution, and interpretation must occur only
after the protocol-only commit.

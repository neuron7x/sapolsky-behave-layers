# CWC-FLAGSHIP-ROUTE-01 — Pre-Execution Amendment 001

Date frozen: 2026-08-11
Status: PRE-EXECUTION / NO MODEL OUTPUTS OBSERVED
Parent preregistration commit: `cc1609ad6b944c613737c8103fc3d695ec9b31c9`

## Defect found before implementation

The parent protocol made the route decision from exit-1 logits. A continued window would therefore
pay an intermediate LM-head evaluation that a fixed-depth-2 baseline does not need, while entropy
and probability-margin features also introduce nonlinear operation costs that are not covered by the
repository's audited dense-FLOP ledger. That would make the primary compute comparison needlessly
ambiguous.

The repair removes this ambiguity before any model output exists. Dataset, architecture depth,
training budget, seeds, cohort files, pass/fail rule, and non-promotion boundary are unchanged.

## Frozen pre-decision representation

After block 1, before any LM-head evaluation, compute the mean hidden state over the 64 positions.
The route representation is exactly:

`z = concat(mean_t(h1[t, :]), family_indicator)`

with 65 scalars (`d_model=64` plus PROSE=0/CODE=1).

This representation is available before the target is observed and before block 2 is executed.
No target, loss, exit-2 state, file/shard identity, case hash, or cohort identity may enter `z`.

## Candidate and generic comparator

Both policies use the exact same standardized 65-dimensional representation and the same fixed
closed-form ridge algorithm (`alpha=1e-3`), fitted on CALIBRATION only:

- `DECISION_RELEVANT`: target = `window_mean_loss_depth1 - window_mean_loss_depth2`;
- `DIFFICULTY_MATCHED`: target = `window_mean_loss_depth1`.

Thus the candidate asks "where does more compute change utility?", while the generic comparator asks
"which cases are hard?". Sensor, feature dimensionality, fit algorithm and score-evaluation cost are
matched.

`DECISION_RELEVANT` continues iff predicted marginal gain per incremental block-2 FLOP exceeds the
family-specific fixed-depth frontier slope frozen from CALIBRATION.

## Revised dynamic baselines

Required dynamic comparators are now:

1. `RANDOM_MATCHED` — deterministic hash ranking, exact candidate continuation count;
2. `HIDDEN_NORM_MATCHED` — highest L2 norm of the same mean hidden vector, exact count;
3. `DIFFICULTY_MATCHED` — highest calibration-fitted predicted depth-1 loss, exact count;
4. `ORACLE_MATCHED` — highest realized depth1-depth2 gain, exact count; diagnostic only;
5. `DECISION_RELEVANT`.

The parent's `ENTROPY_MATCHED` and `MARGIN_MATCHED` are superseded before implementation because
they require an intermediate LM head and an unaudited nonlinear feature-cost convention. They are
not silently dropped; this amendment records the reason and replacement.

## Exact logical compute convention

For one window:

- `B1` = block-1 logical FLOPs;
- `B2` = block-2 logical FLOPs (same architecture, same FLOPs);
- `H` = one LM-head evaluation;
- `R` = route representation + linear score envelope.

`R` is conservatively defined as:
- mean pooling: `64 * 64` additions plus 64 scalar divisions;
- ridge score: `2 * 65` FLOPs;
- scalar comparison: 1 FLOP.

All dynamic policies are charged the same `R`, even RANDOM and HIDDEN_NORM, so a candidate cannot
win from under-accounting its learned decision rule.

Costs:

- fixed depth1: `B1 + H`;
- fixed depth2: `B1 + B2 + H`;
- dynamic halt: `B1 + R + H`;
- dynamic continue: `B1 + R + B2 + H`.

Therefore the only variable dynamic cost is whether block 2 executes. The LM head is evaluated
exactly once on every path.

If `B1 + R + H + q*B2 > B1 + B2 + H`, the candidate lies outside the measured fixed frontier and
the cell fails; no clamping is permitted.

## Revised required comparisons

For every PRIMARY/REPLICATION seed-family cell candidate CE must be:

- strictly lower than `FIXED_FRONTIER` at exact candidate FLOPs;
- strictly lower than `RANDOM_MATCHED`;
- no worse than `HIDDEN_NORM_MATCHED`;
- strictly lower than `DIFFICULTY_MATCHED`;
- no better than `ORACLE_MATCHED` (oracle sanity ordering).

Every other parent endpoint and verdict rule remains unchanged.

## Temporal boundary

This amendment must be a strict Git ancestor of implementation, calibration policy, PRIMARY,
REPLICATION and verdict artifacts.

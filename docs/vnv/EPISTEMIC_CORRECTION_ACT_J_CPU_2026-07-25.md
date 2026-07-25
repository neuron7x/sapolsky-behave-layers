# Epistemic correction: Act-J transformer noninferiority

Date: 2026-07-25

Status: the empirical “adaptive depth is never worse than static at matched
compute” claim is falsified. The analytic budgeted-oracle theorem is not
retracted.

## Trigger

The hermetic CPU merge-request pipeline ran
`test_adaptive_depth_is_never_worse_than_static_at_matched_compute` with the
committed seed and training budget. It returned:

- adaptive accuracy: `0.5825000032782555`;
- static matched accuracy: `0.7850000075995922`;
- compute-matched gain: `-0.20250000432133675`.

The asserted tolerance was `-0.03`, so this is a substantive sign reversal, not
a rounding-boundary failure.

## Error

The old text transferred a property of the analytic oracle to independently
trained finite models. The oracle selects the best available action per context
under a budget. In the transformer pilot, shallow and deep networks are trained
separately; routing by nominal difficulty does not guarantee that the selected
network learned the context-optimal action. Consequently, noninferiority is not
“by construction.”

The prior CUDA artifact remains immutable as a record of what that run observed.
It is not universal evidence across backends, seeds, or training budgets.

## Correction

The executable test now verifies bounds, matched-compute accounting, and the
reported gain identity without assuming its sign. Multi-seed execution emits
`ADAPTIVE_DEPTH_NONINFERIORITY_FALSIFIED` whenever an observed run reverses the
claim. Any renewed positive performance claim requires a preregistered
cross-backend, multi-seed study with uncertainty intervals and an explicit
training-budget sensitivity analysis.

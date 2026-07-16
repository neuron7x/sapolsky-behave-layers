"""Adaptive Metaplasticity Governor (AMG) — the *controlled-plasticity* subsystem.

WHAT
    A four-part apparatus for deciding, per parameter *group*, how much each group
    is allowed to change during continual learning:
      - `contracts`   — the immutable data types (group spec, plasticity decision)
                        that every other part exchanges; no hidden mutable state.
      - `registry`    — deterministic partition of a model's trainable parameters
                        into structured groups (attention.qkv, mlp.down, ...).
      - `importance`  — per-parameter consolidation weight Omega (EWC / SI / MAS).
      - `optimizer`   — applies a group-level decision (mask . lr . consolidation .
                        norm-bound) to the gradients, then steps the base optimizer.

WHY (design argument)
    Plasticity is treated as a *budgeted control problem*, not a free hyperparameter.
    The identifiability theorem (docs/IDENTIFIABILITY_THEORY.md) says an adaptive
    mechanism has measurable value only when a binding budget forbids applying it
    everywhere; the AMG therefore makes the update budget an explicit, first-class
    constraint (`PlasticityDecision.budget`) rather than an emergent side effect of a
    learning rate. Grouping is *structured and deterministic* so that a decision is
    interpretable ("freeze mlp.down of block 3") and reproducible across runs.

INVARIANTS (guaranteed here, tested in experiments/wp3_plasticity_v1)
    - every trainable parameter maps to exactly one group (registry: no duplicate);
    - group ids depend only on the model's parameter names, never on object identity;
    - a group whose mask bit is 0 does NOT move — byte-identical — even under the base
      optimizer's weight decay / momentum (optimizer: snapshot-and-restore);
    - `requires_grad` is never toggled per step; the decision acts on `.grad` only.

NON-CLAIM (anti-pseudo)
    This package provides the *mechanism* and its guarantees. It does NOT assert that
    controlled plasticity improves continual learning: on the shipped unbudgeted
    benchmark the oracle gap is ~0 (CWC-L4 = NOT_TESTED / non-identifiable). The value
    question is open and requires a cost-aware confirmatory run.
"""

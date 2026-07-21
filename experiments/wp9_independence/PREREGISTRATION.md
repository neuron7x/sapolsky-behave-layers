# PREREGISTRATION — WP9 Independence-Assumption Robustness

**Committed before the run.** The corrected certificate's `sd/√|C|` deviation term assumes
per-context independence (flagged in WP7). This tests whether the assumption is load-bearing:
Monte-Carlo the corrected bound's coverage (FPR on a tied null) under CROSS-CONTEXT correlated noise.

## Design (frozen)

Tied null (`G=0`), noise `= √(1−ρ)·ε_cell + √ρ·η_action` inducing cross-context correlation `ρ ∈
{0,0.3,0.6,0.9}`, over shapes {4×4, 2×8, 6×3}, `sd=0.15`, `δ=0.10`, 4000 trials. The tied null is
the least-favorable (worst-case FPR).

## Decision rule (FROZEN)

- **INDEPENDENCE_ROBUST** iff corrected-bound FPR `≤ δ` at every `ρ` and shape (up to `ρ=0.9`) —
  independence is not load-bearing for validity.
- **INDEPENDENCE_LOAD_BEARING** — FPR `> δ` at some `ρ` (the assumption matters; report the ρ).

## Scope

Meta / rigor. Robustness of the corrected bound's coverage to correlation. New claim
`CWC-RIGOR5-independence`.

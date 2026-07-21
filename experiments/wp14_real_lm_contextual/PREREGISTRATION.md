# PREREGISTRATION — WP14 Real-LM Boundary Robustness (contextual difficulty)

**Committed before the confirmatory run.** WP6 found real-LM per-token compute allocation
non-identifiable using UNIGRAM surprisal (a crude difficulty proxy). An expert would object that the
negative might be an artifact of the weak difficulty signal. This re-tests with a **contextual**
signal — BIGRAM surprisal `-log P(target|prev)` (independent of the model) — to check the WP6
negative is robust to the difficulty definition.

## Design (frozen)

Same frozen 66 KB corpus + byte recurrent LM + `K∈{1,2,3}` as WP6, 5 seeds. Difficulty = target-byte
BIGRAM-surprisal tercile. Utility `U_λ[bucket][K] = -loss - λ·K/3`, `λ∈{0,0.3}`. Certificate `G_lo`
(δ=0.05) over 5 seeds + POSITIVE CONTROL on synthetic AC1 (must be `>0`).

## Decision rule (FROZEN)

- **WP14_REAL_LM_NOT_IDENTIFIABLE_ROBUST** iff real-LM `G_lo ≤ 0` at every `λ` AND positive control
  `>0`. The WP6 negative is robust to the difficulty signal.
- **WP14_REAL_LM_IDENTIFIABLE_UNDER_CONTEXTUAL** — real-LM `G_lo > 0` at some `λ` (the boundary was
  an artifact of the unigram proxy; the framework transfers with a better signal — a big positive).
- **WP14_VOID** — positive control fails.

## Scope

Tier `REAL-DATA`. Robustness of the WP6 boundary. New claim `CWC-RD2-real-lm-contextual`.

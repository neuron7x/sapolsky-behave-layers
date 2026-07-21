# PREREGISTRATION — L4k Falsification Boundary of the Plasticity Line

**Committed before the run.** The whole L4 line rests on one foundation: the cost-budget oracle
gap is a genuine **context×arm interaction**, not an artifact of the utility structure. This runs
the most decisive kill-conditions explicitly: destroy the interaction and the gap MUST vanish; if
any null still shows a gap, the whole line is falsified.

## Kill-conditions (each must behave, or the line is falsified)

On the real confirmatory utility `U` (16 seeds, contexts {lexical, relational}, arms {attn, mlp,
head, embed}), λ=1:

1. **REAL (positive control):** `U` unchanged ⇒ `G_lo > 0` and governor recovery `≥ 0.8`.
2. **ADDITIVE null:** replace `U` by its additive ANOVA reconstruction
   `Û[t,a] = mean_a U[t,·] + mean_t U[·,a] − grand_mean` (interaction removed) ⇒ `G_lo ≤ 0` and
   governor recovery `≤ 0.10`.
3. **COLLAPSED null:** both contexts get the same row (`lexical`) ⇒ `G_lo ≤ 0` and recovery `≤ 0.10`.
4. **ARM-SHUFFLE null:** independently permute the arm axis of context 1 (a fixed derangement) so
   the two contexts' best arms coincide by construction ⇒ `G_lo ≤ 0` and recovery `≤ 0.10`.

Certificate `G_lo` via `identifiability_inference` (δ=0.05); governor = reward-only REINFORCE,
train seeds 5–12 / eval 13–20, worst of 8.

## Decision rule (FROZEN)

- **L4K_LINE_SURVIVES** iff the REAL control shows the gap (`G_lo>0`, recovery≥0.8) AND **all
  three nulls vanish** (`G_lo≤0` and recovery≤0.10). The foundation is sound; the line is not
  falsified by its most decisive kill-conditions.
- **L4K_LINE_FALSIFIED** — any null still shows a gap (a "gap" without a real interaction), or the
  REAL control fails: the whole line's foundation is unsound.

## Scope / prohibited

Tier `SYNTHETIC`. A falsification-boundary / foundation check for the L4 line. New claim
`CWC-L4k-falsification-boundary`. Surviving the nulls is necessary, not sufficient, for the
line's external validity (still synthetic, no L7).

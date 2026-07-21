# L4e Mechanism Model — RESULTS (partial explanation, honestly located)

**Verdict: `L4E_MECHANISM_INCOMPLETE`.** Preregistration:
`experiments/wp3_plasticity_v7_mechanism/PREREGISTRATION.md` (with a disclosed 2026-07-21
grid amendment). Reproduce:
`PYTHONPATH=. python -m experiments.wp3_plasticity_v7_mechanism.src.mechanism`.

## The 2-arm ablation vs the full 4-arm governor

| budget N | 2-arm reduced Δ* | full governor Δ* (L4d) |
|---|---|---|
| 1500 | 0.0129 | 0.0567 |
| 3000 | 0.0138 | 0.0350 |
| 6000 | 0.0053 | 0.0250 |
| 12000 | 0.0013 | 0.0140 |
| **log-log exponent** | **−1.117** | **−0.654** |
| noise ratio Δ*(2σ)/Δ*(σ) | 0.364 | 0.500 |

## What the account gets right, and wrong

**Right — noise-as-exploration is a 2-arm effect.** The reduced noise ratio `0.364 < 1`
reproduces the full governor's sign (`0.500 < 1`): more reward noise → SMALLER collapse
margin. The baseline-relative advantage `(R − baseline)` inflating with `σ` and driving
exploration is confirmed as a two-arm phenomenon.

**Wrong — the budget exponent is NOT a pure 2-arm phenomenon.** The 2-arm reduction scales as
`Δ* ∝ N^−1.12` — essentially the **drift-limited** `−1` regime the mechanism note predicted
for pure two-arm logit ascent. But the full 4-arm governor scales as `N^−0.654`, much shallower.
So the two clearly-dominated arms **matter**: suppressing them in the 4-arm softmax dilutes the
probability mass on `b` vs `r` and injects effective **diffusion**, pushing the exponent from
the 2-arm drift limit (`−1.1`) toward the observed `−0.65` (between diffusion `−0.5` and drift
`−1`). The `|−1.117 − (−0.654)| = 0.46 > 0.15` mismatch fails the preregistered test.

## Honest synthesis (this refined the account, not just failed it)

- The derived drift `dg/dt ∝ LR·Δ·π(1−π)` is confirmed super-diffusive: **at 2 arms the
  collapse is nearly drift-limited (`−1.1`)**, exactly as the account said.
- The full governor's shallower `−0.654` is explained as **drift (2-arm) + diffusion from
  dead-arm suppression (4-arm)** — a mixed regime. The naive "collapse is 2-arm" hypothesis is
  falsified; the truer picture is drift-limited-2-arm modulated by 4-arm dilution.
- Noise-as-exploration is robustly 2-arm.

## Consequence for the claim ladder

`CWC-L4e-mechanism` is registered **NOT_SUPPORTED** for the "pure 2-arm" hypothesis (budget
exponent not reproduced), while recording the two mechanistic facts it *did* establish
(2-arm is drift-limited `−1.1`; noise-as-exploration is 2-arm). Frozen. Does not change
L4/L4a/L4b/L4c/L4d.

## Scope

Tier `SYNTHETIC-PARAMETRIC`. Mechanistic characterization of the learned-governor collapse.

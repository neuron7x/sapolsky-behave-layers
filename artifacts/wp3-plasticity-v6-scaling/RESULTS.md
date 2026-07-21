# L4d Higher-Power Scaling Revisit — RESULTS

**Verdict: `L4D_BUDGET_SCALING_VIOLATED`** (a near-miss on the *steep* side — read the
nuance). Preregistration: `experiments/wp3_plasticity_v6_scaling/PREREGISTRATION.md` (with a
disclosed 2026-07-21 grid-range amendment). Reproduce:
`PYTHONPATH=. python -m experiments.wp3_plasticity_v6_scaling.src.scaling`.

## P1 — budget scaling (σ = 0.10 fixed)

| budget N | Δ* | ratio to N=1500 | `1/√(N/1500)` (law) |
|---|---|---|---|
| 1500 | 0.0567 | 1.000 | 1.000 |
| 3000 | 0.0350 | 0.617 | 0.707 |
| 6000 | 0.0250 | 0.441 | 0.500 |
| 12000 | 0.0140 | **0.247** | 0.354 |

`Δ*` decreases **monotonically** with budget — a real power-law collapse-margin scaling. But
the overall ratio **0.247** falls just **below** the preregistered confirm band `[0.25, 0.55]`
(and below the `1/√8 = 0.354` law). Per-doubling ratios (0.617, 0.714, 0.560) average ~0.63
vs the law's 0.707: `Δ*` shrinks as roughly `N^(−0.68)`, **steeper** than the `N^(−0.5)`
sample-complexity law. Honoring the a-priori threshold (`0.247 ∉ [0.25, 0.55]`), the strict
prediction is **VIOLATED** — but on the side of *faster-than-predicted* budget efficiency,
not absence of scaling. I did not move the goalpost to absorb the 0.003 miss.

## P2 — noise scaling, re-tested at 24 seeds

`Δ*(2σ)/Δ*(σ) = 0.500` — neither the sample-complexity value (~2) nor exactly the L4c value
(0.91). It is `< 1`: **more reward noise gives a SMALLER collapse margin (better thin-margin
recovery)**. So L4c's qualitative finding — noise does not hurt and can help — **survives
higher power and strengthens**: the noise axis robustly contradicts the `(σ/Δ)²` law
(consistent with reward noise acting as exploration pressure in REINFORCE).

## Honest synthesis

- The governor's credit-assignment collapse margin **does** scale with the learning budget
  (monotone power law), but with exponent ~`−0.68`, **steeper** than the `−0.5`
  sample-complexity law → the preregistered budget prediction is VIOLATED (near-miss, steep).
- The **noise** axis robustly refutes sample-complexity (ratio 0.5 < 1; noise helps), now at
  higher power than L4c.
- Net: the naive `(σ/Δ)²` sample-complexity law does **not** govern this learner on either
  axis — budget is steeper than `−0.5`, noise runs the wrong way. A cleaner future model would
  treat the REINFORCE step size (advantage ∝ σ) and gradient accumulation explicitly.

## Consequence for the claim ladder

`CWC-L4d-budget-scaling` is registered **NOT_SUPPORTED**: the sample-complexity law is not
confirmed on either axis (budget exponent steeper than −0.5 and outside the a-priori band;
noise anti-scales). The collapse itself and its monotone budget-dependence are real and
recorded. A frozen result. Does not change L4/L4a/L4b/L4c.

## Scope

Tier `SYNTHETIC-PARAMETRIC`. Characterizes the learned-governor mechanism only.

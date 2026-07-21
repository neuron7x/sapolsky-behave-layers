# L4c Thin-Margin Credit-Assignment Collapse — RESULTS (a frozen falsification)

**Verdict: `L4C_SCALING_VIOLATED`.** The preregistered prediction was **FALSIFIED**.
Preregistration: `experiments/wp3_plasticity_v5_thinmargin/PREREGISTRATION.md`. Reproduce:
`PYTHONPATH=. python -m experiments.wp3_plasticity_v5_thinmargin.src.thinmargin`.

## What was predicted, and what happened

I predicted (grounded in the `(σ/Δ)²` sample-complexity law, not fit) that the governor's
credit-assignment collapse margin `Δ*` scales **linearly with noise**:
`Δ*(2σ₀)/Δ*(σ₀) ≈ 2`. It does not.

| noise | Δ=0.40 | 0.20 | 0.10 | 0.05 | 0.02 | interpolated Δ* |
|---|---|---|---|---|---|---|
| σ = 0.10 | +1.00 | +1.00 | +0.88 | +0.63 | +0.38 | 0.035 |
| σ = 0.20 | +1.00 | +1.00 | +0.88 | +0.88 | +0.25 | 0.032 |

**`Δ*(2σ)/Δ*(σ) = 0.91`** — noise-**independent**, not the predicted ≈2.0. The
sqrt-law does NOT govern this learner over the tested range.

## Honest reading (this is the harness killing its own prediction)

1. **A collapse is real:** recovery falls from 1.00 (wide margin) toward ~0.3 as the
   best/runner-up margin `Δ → 0.02` — credit assignment does degrade when arms become
   hard to tell apart at a fixed budget.
2. **But the sample-complexity scaling is refuted.** Note the tell at `σ=0.20, Δ=0.05`:
   recovery **0.88 > 0.63** at `σ=0.10` — *more* reward noise gave *better* recovery. That
   is impossible under pure `(σ/Δ)²` distinguishability. The mechanism: REINFORCE's update
   is `LR·(r−baseline)·∇log π`, and the advantage `(r−baseline)` scales **with σ**, so the
   effective step size grows with noise and partially cancels the harder distinguishability.
   The collapse margin is therefore roughly noise-independent, not `∝ σ`.
3. **Refusal to rescue the prediction.** This is a preregistered result at 8 controller
   seeds and a 5-point `Δ` grid; the `Δ*` interpolation is coarse and the run may be
   underpowered. I did **not** re-run with more seeds / a finer grid to flip the verdict —
   that would be fishing. The prediction stands falsified as recorded; a future
   preregistered higher-power run may revisit the scaling question.

## Consequence for the claim ladder

`CWC-L4c-credit-collapse` is registered **NOT_SUPPORTED** for the scaling hypothesis: the
governor's credit-assignment collapse exists but is **not** governed by the `(σ/Δ)²`
sample-complexity law over `σ ∈ [0.1, 0.2]` — the learner's noise-dependent step size
breaks the naive law. A frozen negative. It does not change L4/L4a/L4b.

## Scope

Tier `SYNTHETIC-PARAMETRIC`. Characterizes (and falsifies a prediction about) the learned
governor mechanism only.

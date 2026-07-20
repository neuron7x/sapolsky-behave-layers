# From Ceilings to Inference: a Calibrated Pilot Certificate for Act J

**Status.** Statistical result. The theorem is proved below; its calibration
(false-positive control) and power are established by Monte-Carlo simulation in
`experiments/common/identifiability_inference.py`
(suite: `experiments/common/tests/test_identifiability_inference.py`). No new
empirical CWC claim; no `claim_registry.json` change.

**The boundary this breaks.** Every prior note in the programme proves an *upper
bound* — a converse that says when adaptation **cannot** pay (dominance, information,
computation vetoes; the rate-function phase transition). None of them lets you
**infer, from data, that a real benchmark IS identifiable** — the step required to
decide the decisive Act J cloud run. This note supplies that step: a one-sided,
finite-sample, error-controlled certificate. It is the point where the theory turns
from *impossibility* into an *action* — spend, or don't — with a proof attached.

---

## 1. The obstruction: the oracle gap is a biased functional

The identifiability quantity is the oracle gap
`G = 𝔼_c max_a U[c,a] − max_a 𝔼_c U[c,a]`. It contains a `max`, so it is **not a
linear functional of `U`**. Estimate `U` by a pilot sample mean `Û` (per cell `(c,a)`,
`n` samples, per-cell standard error `sd = σ/√n`). By Jensen,

```
𝔼[ max_a Û[c,a] ]  ≥  max_a U[c,a] ,
```

so the plug-in `V̂_oracle = 𝔼_c max_a Û` is **biased upward**, and hence
`Ĝ = V̂_oracle − V̂_fixed` is biased upward. The naive rule *"estimate `Ĝ`; if
`Ĝ > 0`, the benchmark is identifiable, spend the cloud budget"* therefore has an
**uncontrolled false-positive rate**. Simulation on a truly non-identifiable
(`G = 0`) pilot:

| pilot `n` | naive `P(Ĝ>0 ∣ G=0)` | calibrated `P(certify ∣ G=0)` |
|---:|---:|---:|
| 50 | **0.55** | 0.00 |
| 200 | 0.09 | 0.00 |
| least-favourable (all actions tied, |A|=30) | **1.00** | 0.00 |

At a small or wide pilot the naive rule certifies a worthless benchmark **more than
half — up to all — of the time**. This is exactly the error the CWC gate discipline
exists to prevent, now quantified.

---

## 2. The certificate

Correct for **both** the `max`-operator's optimism and the sampling fluctuation:

```
G_lo  :=  Ĝ  −  b(sd,|A|)  −  d(sd,|C|,δ) ,
   b = sd · √(2 ln|A|)                    (max-of-sub-Gaussians upward bias),
   d = (sd / √|C|) · √(2 ln(2/δ))         (deviation of the context average).
```

> **Theorem (valid one-sided certificate).** If the pilot noise is sub-Gaussian with
> proxy `sd` per cell, then `P(G ≥ G_lo) ≥ 1 − δ`. Consequently `G_lo > 0` certifies
> identifiability, and `G_lo > c_route` certifies positive net value, each with
> false-positive rate at most `δ`.

*Proof.* `Ĝ − G = (V̂_oracle − V_oracle) − (V̂_fixed − V_fixed)`. For the oracle term,
`V̂_oracle − V_oracle = 𝔼_c( max_a Û[c,a] − max_a U[c,a] ) ≤ 𝔼_c max_a (Û−U)[c,a]`.
Each `(Û−U)[c,a]` is centered sub-Gaussian with proxy `sd`; the maximum of `|A|` of
them has expectation `≤ sd√(2 ln|A|) = b`, and concentrates. For `V̂_fixed`, the
context-averaged estimates have proxy `sd/√|C|`; a one-sided union bound over `|A|`
actions gives, with probability `≥ 1−δ`, `V̂_oracle − V_oracle − (V̂_fixed − V_fixed)
≤ b + d`. Hence with probability `≥ 1−δ`, `Ĝ − G ≤ b + d`, i.e. `G ≥ Ĝ − b − d =
G_lo`. ∎

The bound is deliberately **conservative** (it is an envelope, so the realised
false-positive rate is typically well below `δ`); conservativeness costs power, not
validity, and is the correct trade for a gate that must not green-light waste.

*Verified:* on random null problems the calibrated false-positive rate is `≤ δ`
(0 harness violations), while dropping the `b` term alone makes it exceed `δ` in the
many-action regime — so the max-bias correction is **load-bearing**, not decorative.

---

## 3. Power and sample complexity

> **Corollary (sample complexity).** To certify a true gap `G>0` at confidence
> `1−δ`, a pilot of
> `n* = ⌈ (σ·K / G)² ⌉` samples per cell suffices, with
> `K = √(2 ln|A|) + √(2 ln(2/δ))/√|C|`.

Solving `G > sd·K` for `sd = σ/√n`. So the identifiability of Act J is decidable with
a **bounded, computable** pilot: e.g. `G=0.25, σ=1, |C|=|A|=4, δ=0.05 ⇒ n* ≈ 147`
samples per cell. Simulation confirms power `→ 1` at and beyond `n*`, and power `→ 1`
on separated alternatives at every pilot size tested.

This closes the loop the programme has pointed at since the identifiability theory:
> "run the §6 predictor on a small pilot before spending cloud compute."
Now the predictor is an *inference procedure* with a validity proof, a false-positive
guarantee, and a sample-size formula — not a point estimate to eyeball.

---

## 4. The decision rule (what actually goes into Act J)

```
1. Pilot: estimate Û[c,a] and the per-cell noise σ over a handful of contexts/mechanisms.
2. Compute Ĝ = plugin_gap(Û);  G_lo = Ĝ − b(sd,|A|) − d(sd,|C|,δ).
3. Estimate the learned route-decision cost c_route (cheap-probe vs oracle-probe gap).
4. SPEND cloud compute iff  G_lo > c_route.   (false-positive rate ≤ δ)
   Otherwise refuse: the benchmark is not certifiably identifiable at this pilot;
   either redesign for anti-dominance under budget, or collect n* more samples.
```

This is a genuine **admissibility test with error control**, the inferential
counterpart of the deterministic admissibility predicate in
`MATHEMATICAL_COHERENCE_AND_EFFICIENCY.md`: coherence says *the recorded verdicts are
consistent with the theory*; this says *a new verdict can be reached from data with a
guaranteed error rate*.

---

## 5. Epistemic status and limitations

* A **statistical theorem** about a decision procedure; it does not itself assert any
  CWC empirical result (`CWC-L7-pareto: NOT_TESTED`). It makes the *route to* that
  result decidable with controlled error.
* Sub-Gaussian noise with a known/estimated proxy is assumed; heavy-tailed pilots
  need a robust mean estimator (a stated extension). The bound is conservative — a
  sharper, less conservative debiasing (e.g. a jackknife/median-of-means correction
  of the `max`-bias) would raise power at fixed validity and is the natural next step.
* The certificate controls the false-positive (spend-on-nothing) rate; the
  false-negative (miss a real benchmark) rate is governed by the sample-complexity
  corollary and shrinks with `n`.

## Relationship to sibling documents

* `IDENTIFIABILITY_THEORY.md` — defines `G` and the pilot predictor this makes inferential.
* `ADAPTIVE_COMPUTATION_VALUE_THEORY.md` — the certificate tests `G>0` and `G>c_route` (Theorem 6).
* `MATHEMATICAL_COHERENCE_AND_EFFICIENCY.md` — deterministic admissibility; this is its finite-sample form.
* `VALUE_OF_INFORMATION_RATE_FUNCTION.md` — off the indifference manifold `G` is `Θ(R)`-cheap to realise, so a certified `G` is worth pursuing.

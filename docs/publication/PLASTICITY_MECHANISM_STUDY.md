# The Cost-Budget Plasticity Governor: A Falsification-Disciplined Mechanism Study

*Consolidated technical report of the L4 sub-line (claims `CWC-L4`, `CWC-L4a`…`CWC-L4f`).
Every result below is preregistered, gated, checksummed, and reproduced under
`make -f Makefile.cwc verify`. Tier: SYNTHETIC / SYNTHETIC-PARAMETRIC unless stated.*

## 0. One-paragraph summary

Under a hard parameter-cost budget, a context-conditioned plasticity allocation beats every
fixed allocation (the metaplasticity **oracle gap** is real). A reward-only learned governor
recovers that gap out-of-sample; its realisable value is bounded by the information the
observation carries about the context, tracking the master inequality quantitatively; and its
credit-assignment collapse under thin margins is **not** governed by the naive sample-complexity
law but by a drift-limited, arm-count-dependent dynamics we map exactly. Two claim-tier
positives, four frozen negatives — the negatives are what make the account trustworthy.

## 1. The result chain (each row is a committed, gated claim)

| # | Question | Verdict | Key number | Artifact |
|---|---|---|---|---|
| L4 | Is the cost-budget oracle gap real, out-of-sample? | **SUPPORTED_NARROWED** | `G_lo=0.111>0`, 16/16 held-out seeds, λ frozen a priori | `wp3-plasticity-v2-confirmatory` |
| L4a | Does a *learned* (reward-only) governor recover it? | **SUPPORTED** | recovery 1.00 held-out (8/8), NULL falsifier 0 | `wp3-plasticity-v3-governor` |
| L4b | Is its value bounded by context information? | **SUPPORTED** | recovery = 1−2.146·p, tracks `I(C;Z)` to 3 decimals; abstains at `p*≈0.466` | `wp3-plasticity-v4-inferred` |
| L4c | Does the collapse follow the `(σ/Δ)²` noise law? | **NOT_SUPPORTED** | `Δ*(2σ)/Δ*(σ)=0.91`, noise HELPS | `wp3-plasticity-v5-thinmargin` |
| L4d | …the `(σ/Δ)²` budget law, at higher power? | **NOT_SUPPORTED** | `Δ*∝N^−0.65` (steeper than −0.5); noise anti-scales (0.5) | `wp3-plasticity-v6-scaling` |
| L4e | Is the collapse a pure 2-arm phenomenon? | **NOT_SUPPORTED** | 2-arm is drift-limited `N^−1.12`; dead arms add diffusion | `wp3-plasticity-v7-mechanism` |
| L4f | Does the exponent scale monotonically with arm count? | **SUPPORTED** | `−1.03→−0.09` over `K=2..8`, monotone | `wp3-plasticity-v8-armscaling` |
| L4g | Is the gap robust to the cost model? | **SUPPORTED** | `G_lo>0` under linear/sqrt/log/square | `wp3-plasticity-v9-costrobust` |
| L4h | Does it generalize to more contexts? | **SUPPORTED** | `G_lo` 0.084→0.685, recovery ≥0.95 for `|C|=2..6` | `wp3-plasticity-v10-contexts` |
| L4i | Does the governor realise the rate function `V*(R)`? | **SUPPORTED** | `V_gov≤V*(I)`, saturation ≥0.924 | `wp3-plasticity-v11-ratebridge` |
| L4j | Is the sub-line registry↔evidence consistent? | **SUPPORTED** | 0 mismatches, 0 orphans | `wp3-plasticity-v12-consistency` |
| L4k | Does the line survive its decisive nulls? | **SUPPORTED** | gap vanishes under every interaction-destroying null | `wp3-plasticity-v13-killtest` |

## 2. The positives, in order

**L4 — identifiability, confirmed out-of-sample.** The exploratory revival (gap ≈ 0.19 at
λ=1 on seeds 0–4, λ chosen post-hoc) was promoted only after (a) a preregistered pilot
certificate green-lit it (`G_lo=0.081>0`, controls passed) and (b) a confirmatory run on **16
fresh held-out seeds with λ frozen a priori** returned `G_lo=0.111>0`, present in every seed.
The gap is the theory's context×choice interaction γ realised under a binding budget: the
oracle spends the cheap `head` group on *lexical* (which head already solves) and reserves the
expensive `attn` for *relational* (structurally attn-only).

**L4a — a learned governor achieves it.** A per-context softmax policy trained by REINFORCE
from **reward only** (never the oracle label), on train seeds and evaluated on held-out seeds,
recovers 100% of the gap in 8/8 controller initializations; a NULL falsifier (collapsed reward)
returns 0. This discharged L4's standing "no learned governor" limitation.

**L4b — value is information-bounded (the theory bridge).** When the governor sees only a noisy
observation z of the context, its realised recovery tracks the grounded prediction
`recovery(p)=1−2.146·p` to ±0.001, is monotone in `I(C;Z)`, and the governor **abstains** at
zero information (rational inattention) at the predicted boundary `p*≈0.466`. This is the master
inequality `V_realized ≤ oracle_gap − c_route` made quantitative on a real mechanism.

## 3. The negatives, and what they taught

The naive sample-complexity intuition — that the thin-margin collapse margin scales as
`Δ*∝σ/√N` — is **wrong on both axes**:

- **Noise (L4c, L4d):** more reward noise gives a *smaller* collapse margin (ratio < 1). REINFORCE's
  advantage `(R−baseline)` scales with σ, so the step size grows with noise and acts as
  exploration, not estimation error.
- **Budget (L4d):** `Δ*∝N^−0.65`, steeper than the `−0.5` law.
- **Mechanism (L4e, L4f):** the 2-arm reduction is nearly **drift-limited** (`N^−1.12`,
  matching `dg/dt∝Δ·π(1−π)`); adding dead arms dilutes the b-vs-r mass and shallows the exponent
  **monotonically** (`−1.03→−0.09` over `K=2..8`). The real governor lives at K≥3, in this
  arm-count-dependent mixed regime — which is exactly why the two-arm sample-complexity law fails.

## 4. Method discipline (why to believe it)

- Every experiment has a `PREREGISTRATION.md` that is a **strict Git ancestor** of its results
  commit (verified). Two grid-range amendments (L4d, L4e/f) were disclosed as instrument
  defects, not results, per `PROTOCOL_AMENDMENT_AND_DEVIATION_POLICY`.
- Every claim carries controls that **can fail**: NULL falsifiers, negative controls (refused),
  positive controls (certified). A frozen falsification (L4c) was kept, not re-run to green.
- One threshold was missed by 0.003 (L4d budget ratio 0.247 vs band floor 0.25) and reported as
  **VIOLATED** — the goalpost was not moved.

## 5. Boundary — what this study does NOT establish

Synthetic toy `GroupedModel`; given-context / wide-margin regimes; no real workload; no
compute-equivalent Pareto (L7, cloud-blocked); no energy/latency; no independent replication.
The L4 line is a **mechanism study**, not an architectural result. Its value is a
falsification-disciplined map of when a cost-budget plasticity governor pays and how it fails.

## 5a. Validity envelope (L4g–L4k)

The positive core (L4/L4a/L4b) is now bounded by four validity checks, all passed:

- **Cost-model robustness (L4g):** the gap survives every monotone cost transform (`G_lo>0` for
  linear/sqrt/log/square) — it is the cost *ordering*, not the curvature, that matters. The
  magnitude is cost-shape dependent (`log` compresses `G_lo` to 0.035).
- **Context generalization (L4h):** identifiability *strengthens* and the governor still recovers
  (≥0.95) as `|C|` grows to 6 at matched per-context budget — contexts do not interfere.
- **Rate-function bridge (L4i):** the learned governor's realised value stays under the master
  `V*(R)` ceiling and nearly saturates it (≥92.4%) — the plasticity analog of Act-J's
  `TRAINED_CONTROLLER_REALISES_V_STAR`. The theory is non-vacuous on a real learned mechanism.
- **Foundation nulls (L4k):** the gap appears *only* with a real context×arm interaction and
  vanishes under additive/collapsed/aligned-best nulls. (The harness first caught a mis-specified
  null of mine and I fixed it via a disclosed amendment — the falsification machinery works on the
  experimenter too.)
- **Internal consistency (L4j):** every claim's registry status matches its artifact verdict; no
  orphan evidence.

## 5b. Final ladder snapshot (this sub-line)

Two positives at the top (L4 identifiability, L4a learned governor, L4b information bound), a ring
of validity checks (L4g–L4k), and three frozen negatives at the mechanism level (L4c/L4d/L4e — the
sample-complexity law fails, the collapse is drift-limited-plus-diffusion). The line is a complete,
internally consistent, falsification-tested **mechanism study on a synthetic benchmark** — not an
architectural result. The single remaining lever is L7 (real workload, compute-equivalent Pareto),
which is cloud-blocked.

## 6. Reproduce

```
make -f Makefile.cwc verify           # all L4* experiment tests + gates
make -f Makefile.cwc verify-evidence  # checksum every L4* bundle
```

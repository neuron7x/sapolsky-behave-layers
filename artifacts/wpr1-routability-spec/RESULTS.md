# WP-R1 — Routability Specification (RESULTS)

**Prereg:** `5ad1313`, committed before any result. **Verdict:** `SPEC_PREDICTS_CERTIFICATE`.
**Not** the ascension act's WP20 (causal controller), which stays `BLOCKED`.
**Class ceiling:** a screening instrument. No mechanism claim; cannot unblock L7 or L8.

## The problem it solves
WP18's kill rule left one legitimate question: *what property must a workload have for routing to
pay?* Answering it by testing candidate workloads one at a time until one passes is exactly the
behaviour the discipline forbids. So instead: derive the condition up front, then test whether the
condition actually predicts the certificate's verdict on evidence that already exists and cannot be
tuned.

## The specification (derived, not fitted)
Both correction terms of the corrected certificate are **exactly linear in `se`** (verified against
the shipped implementation, not assumed), so for a fixed design they collapse to one constant:

> **routable ⟺ `Ĝ > c_route + κ·se`**, with **κ = 4.9007** for `n_c = n_a = 3`, `δ = 0.05`.

**The oracle gap must exceed ≈5 standard errors, and also the measured route cost.** Since
`se = σ/√n`, this converts directly into a budget requirement:

> `n ≥ (κ·σ / (Ĝ − c_route))²`

`κ` is read off `oracle_bias_bound` / `deviation_bound`; `c_route = 0.0006` is the WP17
**measurement**. Nothing here is tuned to an outcome.

## Test 1 — every frozen certificate-bearing bundle (out-of-sample, un-tunable)
| bundle | G/se | required | screen | certificate | `G_lo` | |
|---|---|---|---|---|---|---|
| AC1 synthetic positive | 665.5 | 5.54 | pass | pass | +0.6195 | ✅ |
| WP6 real-LM (unigram) | 0.00 | 4.92 | fail | fail | −0.1438 | ✅ |
| WP14 real-LM (bigram) | 0.00 | 4.91 | fail | fail | −0.2930 | ✅ |
| WP18 prose (tied K) | 0.00 | 4.92 | fail | fail | −0.2004 | ✅ |
| WP18 code (tied K) | 0.00 | 4.92 | fail | fail | −0.1709 | ✅ |
| WP19 prose (untied depth) | 0.04 | 4.91 | fail | fail | −0.4841 | ✅ |
| WP19 code (untied depth) | 0.00 | 4.91 | fail | fail | −0.2338 | ✅ |

**0/7 mismatches.** These bundles were recorded, checksummed and frozen *before* this specification
existed.

## Test 2 — the boundary sweep (where the screen can actually lose)
Test 1 is weak on its own and this is disclosed: no frozen bundle sits near the threshold
(negatives at `G/se ≈ 0`, the positive at 665), so a naive "big gap ⇒ yes" rule would also score
7/7. It tests the *functional form*, not the *threshold value*.

So a real frozen dataset (AC1) was swept continuously across the boundary by shrinking its
interaction term while leaving its main effects and noise intact:

- 61 points, **0 mismatches**, **7 points inside the near-threshold band** `[κ/2, 2κ]`.
- The certificate's flip is bracketed by `G/se ∈ [5.068, 6.311]`; the predicted threshold
  (`κ + c_route/se = 5.786`) lies **inside** that bracket — the strongest statement a discrete grid
  supports.

**Two self-inflicted errors were caught and fixed during this test, not hidden:**
1. The first sweep used a *linear* α-grid and put **zero** points in the near-threshold band — it
   still wasn't testing where the spec could fail. Fixed with a log-spaced grid.
2. The bracket check first compared against `κ` alone, dropping the `c_route/se` term, and reported
   `OUTSIDE`. That was a reporting bug in the check, not a spec failure; the route cost is part of
   the condition. Fixed, and asserted by a test.

## What this buys
A candidate workload can now be screened **before** any budget is committed: run a cheap pilot,
measure `Ĝ` and the cell `σ`, and the closed form says whether routing could *ever* be certified —
and if so, at what cost. Machine-derived in `verdict.json` (`budget_requirement`), not written by
hand:

| workload | aggregate `Ĝ − c_route` | replicates now | replicates needed |
|---|---|---|---|
| WP18 prose (tied K) | **≤ 0** | 60 | **no `n` suffices** |
| WP18 code (tied K) | **≤ 0** | 60 | **no `n` suffices** |
| WP19 code (untied depth) | **≤ 0** | 15 | **no `n` suffices** |
| WP19 prose (untied depth) | > 0 | 15 | **≈ 3.7 × 10⁵** (~25,000×) |
| AC1 synthetic positive | > 0 | 8 | < 1 (already far past) |

**This corrects an error I made twice.** WP18's results said "order 10⁶ replicate units"; an earlier
draft of this document said "~10⁷". Both were computed from the sd of the *gap statistic*. The
certificate consumes the **cell** standard deviation, which is ~150× larger; using the wrong one
understates the requirement by ~4 orders of magnitude. Deriving the number in code rather than prose
is what caught it, and the corrected picture is *simpler and stronger* than either estimate:

- For three of the four real-workload arms the **aggregate gap does not exceed the route cost at
  all** — so no sample size whatsoever would certify them. They are not underpowered; they are
  unroutable at this scale.
- Only WP19 prose — the one arm where WP19 found a genuine context × resource interaction — has a
  positive margin, and it would need ~25,000× its current replicates. That is the precise, honest
  price of the interaction that does exist.

## Scope
- `κ` is **design-specific** (`n_c = n_a = 3`, δ = 0.05, this estimator). It is not a universal
  constant and must be re-derived for any other design.
- Passing the screen does **not** show a workload is routable — it only fails to exclude it.
- L7 and L8 remain `NOT_TESTED`; this WP does not touch them.

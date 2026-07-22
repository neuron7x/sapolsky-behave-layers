# WP-R1 — Routability Specification (PREREGISTRATION)

**Numbering note:** this is **not** the ascension act's WP20 (causal autonomous controller), which
remains `BLOCKED` by the WP18 kill rule. `R1` = *requirements*, outside the act's numbering.
Committed separately, before any result exists.

## Why this, and why it is not claim-hunting
WP18's kill rule stopped architecture work; my own closure document then named the prior question:
*find a workload whose context × resource interaction is large enough to pay for its own routing
decision.* Hunting workloads one at a time until one passes is exactly the behaviour the discipline
forbids. The legitimate move is the opposite: **derive, up front, the condition a workload must
satisfy, and test whether that condition actually predicts the certificate's verdict.**

This WP raises no mechanism claim and cannot unblock L7. Its deliverable is a **screening
instrument**: a closed-form test applied to a cheap pilot that says whether a candidate workload
could *ever* be certified, before any budget is committed.

## The specification (derived, not fitted)
The corrected certificate is `G_lo = Ĝ − b(se, n_a) − 2·d(se, n_c, δ/2)`. Both correction terms are
**linear in `se`**, so for a fixed design (`n_c = n_a = 3`, `δ = 0.05`) they collapse to a single
constant `κ` measured directly from the implementation:

> **Routability condition:  `G > c_route + κ · se`**, with `κ ≈ 4.9` for this design.

Equivalently, in units of the pilot's own noise: **the oracle gap must exceed ≈5 standard errors**
and also exceed the measured route cost. Since `se = σ/√n`, this converts into a sample-size
requirement `n ≥ (κ·σ / (G − c_route))²`.

`κ` is read off the shipped `oracle_bias_bound` / `deviation_bound` implementations, not tuned to
any outcome; `c_route = 0.0006` is the WP17 **measurement**.

## Frozen hypothesis and decision rule
**H1:** the sign of the corrected certificate is predicted by the closed-form condition above, on
every certificate-bearing evidence bundle already frozen in this repository.

**Test set (named now, not chosen later):** *every* existing bundle that reports a certificate
outcome — the synthetic positives (AC1/L4 family), the real-data negatives (WP6, WP14, WP18), and
the untied-depth negatives (WP19). These are **frozen, checksummed and un-tunable**: they were
recorded before this specification existed, so this is an out-of-sample structural test.

- `SPEC_PREDICTS_CERTIFICATE` iff the predicted sign matches the recorded certificate sign on
  **100%** of the test set.
- `SPEC_REFUTED` on **any** mismatch. A single disagreement kills it; there is no "mostly works"
  branch, and no bundle may be excluded after seeing the result.

## What each outcome means (frozen)
- **Predicts** → the programme gains a cheap screening test: measure `G` and `σ` on any candidate
  workload at pilot scale and know, in closed form, whether routing could ever be certified. The
  prior question becomes answerable **without** cloud spend.
- **Refuted** → the certificate's behaviour is not captured by the linear-correction picture, which
  would itself be an important negative about the instrument the whole programme relies on.

## Prohibited extrapolations
- No architecture claim; L7 and L8 remain `NOT_TESTED` and this WP does not touch them.
- The spec is design-specific (`n_c = n_a = 3`, δ = 0.05, this estimator). `κ` must be re-derived
  for any other design; it is not a universal constant.
- A workload passing the screen is **not** thereby shown to be routable — it is merely not excluded.

# PREREGISTRATION — WP11 Pinsker Dichotomy Certification (de-curated)

**Committed before the run.** The audit flagged the small-rate dichotomy (regular
`V*(R)=Θ(R)`, exponent ≈1; critical `V*(R)=Θ(√R)`, exponent ≈0.5) as *sketch + curated numerics on
~4 hand-picked instances*. This addresses the **curated** critique: certify the dichotomy over a
**random sample** of regular instances and a **constructed family** of critical instances.

## Design (frozen)

- **Regular family:** ≥120 random `2×{2,3}` utility matrices (generic ⇒ regular; instances the
  classifier flags critical are skipped), uniform prior. Exponent = `small_rate_exponent` (log-log
  slope of `V*(R)` at small `R`).
- **Critical family:** ≥120 symmetric `[[x,y],[y,x]]` matrices (tied columns ⇒ on the indifference
  manifold ⇒ critical), random `x,y`.
- Deterministic PRNG.

## Decision rule (FROZEN)

- **PINSKER_DICHOTOMY_CERTIFIED** iff: regular exponent mean ∈ `[0.85,1.15]` with ≥85% of instances
  in band, AND critical exponent mean ∈ `[0.40,0.65]` with ≥90% in band.
- **PINSKER_DICHOTOMY_NOT_CERTIFIED** otherwise.

## Honest scope

This is a **numerical certification over a random sample**, NOT a closed proof of the general
dichotomy. The remaining `β(0⁺)<∞` finiteness for regular problems is argued (concavity + a
strictly positive prior-optimal gap) but not proved in full generality here; the critical
manifold is measure-zero. New claim `CWC-RIGOR3-pinsker`. It upgrades "curated" to "sampled",
which was the audit's specific complaint.

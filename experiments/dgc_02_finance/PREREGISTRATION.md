# DGC-02 Financial Verification — Development Preregistration

Status: `DEVELOPMENT_ONLY / NON-PROMOTING`.

## Hypothesis

Target `F-H1`: DGC can reduce total inference cost by at least 30% relative to a quality-admissible fixed-compute reference while preserving decision quality.

This file does not authorize the claim. The confirmatory cohort must be untouched and separately frozen.

## Primary estimands

- aggregate `NetInferenceSavings = 1 - mean(C_DGC_total)/mean(C_ref)`;
- conservative `LCB(NetInferenceSavings)` using fixed-n Hoeffding bounds split across frozen A-E strata with Bonferroni family-wise error control for paired cost delta and reference cost;
- `DeltaQuality = mean(loss_ref - loss_dgc)` and its lower bound where needed.

## Development workload

Reuse frozen DGC-01 regimes A-E. `B0_FIXED` is the development quality-admissible reference because it always purchases the perfect diagnostic and therefore has zero decision loss. B1/B2 remain reported as routing baselines but are not the reference for an equal-quality savings claim when their decision loss is non-zero.

## Governance overhead sweep

Evaluate fixed additional per-decision overhead values:

`{0.000, 0.0025, 0.0050, 0.0075, 0.0100, 0.0125, 0.0150}` normalized cost units.

Primary development threshold is evaluated at zero unmeasured overhead only to recover the core-compute ceiling. The **break-even overhead for 30% savings** is reported and must later be replaced by live metered governance cost.

## Gates

Development threshold status is `DEVELOPMENT_THRESHOLD_MET` only if:

1. `LCB(NetInferenceSavings) >= 0.30` versus B0;
2. `DeltaQuality >= 0` exactly or `LCB(DeltaQuality) >= 0`;
3. no change in task coverage;
4. no unmetered cost is represented as zero in a production claim.

Development success cannot promote `CWC-DGC-H1` or authorize a client/commercial savings claim.

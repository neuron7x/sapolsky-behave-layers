# DGC Pre-Inference Mechanism Lane v1

Status: `FROZEN_PRE_EXECUTION / PRODUCT_PROMOTION_FORBIDDEN`  
Date: 2026-09-24

## Purpose

SWE-bench Verified and Terminal-Bench 2.1 are appropriate for measuring real-workload execution quality and operational cost, but neither benchmark natively supplies the preregistered DGC `catastrophic_regret` endpoint.

Therefore they must not be forced into the existing three-endpoint product P9 by inventing a post-outcome proxy.

This lane preserves the existing product claim and creates a narrower external mechanism claim:

> On the two frozen real software-agent workload families, DGC reduces total operational cost relative to every preregistered B0-B3 baseline while preserving quality within the frozen non-inferiority margin and full matched coverage.

This is not a product qualification claim.

## Frozen external families

1. `SWE_BENCH_VERIFIED`
2. `TERMINAL_BENCH_2_1`

No family may be replaced after confirmatory outcomes are inspected.

## Frozen baseline panel

- B0 Fixed Compute
- B1 Uncertainty Router
- B2 Learned Cost/Quality Router
- B3 Sequential Verification

DGC must pass against every baseline on the same paired task population.

## Mechanism endpoints

For each family × baseline pair:

1. `baseline_total_operational_cost - DGC_total_operational_cost`
2. `DGC_quality - baseline_quality`

Full matched coverage is mandatory and is not treated as a third stochastic endpoint.

Global FWER = `0.05`.

Multiplicity family:

`2 families × 4 baselines × 2 endpoints = 16 claims`.

Frozen per-claim allocation:

`0.05 / 16 = 0.003125`.

Within one family, `alpha = 0.025` and the simultaneous four-baseline/two-endpoint certificate allocates `0.025 / 8` to each paired mean bound.

Quality non-inferiority margin remains `0.02`.

## Separation from product qualification

A successful mechanism lane may authorize only:

`REAL_WORKLOAD_MECHANISM_SUPPORTED`.

It must not authorize:

- `CATASTROPHIC_REGRET_NONINFERIORITY_SUPPORTED`;
- `PRODUCT_QUALIFIED`;
- `CLIENT_VERIFIED`;
- `COMMERCIAL_CLAIM_ALLOWED`;
- production control.

Product qualification still requires a separate pre-outcome, scientifically defensible risk qualification lane with a frozen `catastrophic_regret` operationalization and evidence source.

## Fail-closed rules

- Do not map benchmark failure to catastrophic regret.
- Do not define risk severity after viewing outcomes.
- Do not use a custom scorer when upstream benchmark scoring is available.
- Do not omit DGC/router/governor/tool/retry/infra cost.
- Do not weaken or remove a baseline after confirmatory outcomes.
- Do not change task population, model pool, tools, budget, pricing or scorer across policy arms.
- Missing physical-cost telemetry invalidates the trial; it does not imply zero cost.
- Missing risk evidence blocks product qualification but does not invalidate a correctly scoped mechanism result.

## Implementation authority

- `cwc/governance/mechanism_evidence_plan.py`
- `tests/test_dgc_mechanism_evidence_plan.py`

The existing three-endpoint product plan remains unchanged and remains the authority for any product-level risk claim.

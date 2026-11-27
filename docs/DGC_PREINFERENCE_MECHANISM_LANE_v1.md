# DGC Pre-Inference Mechanism Lane v1

Status: `FROZEN_PRE_EXECUTION / PRODUCT_PROMOTION_FORBIDDEN`  
Date: 2026-09-24

## Purpose

SWE-bench Verified and Terminal-Bench 2.1 are appropriate for measuring real-workload execution quality and operational cost, but neither benchmark natively supplies the preregistered DGC `catastrophic_regret` endpoint.

Therefore they must not be forced into the existing three-endpoint product P9 by inventing a post-outcome proxy.

This lane preserves the existing product claim and creates a narrower external mechanism claim:

> On the two frozen real software-agent workload families, DGC reduces total operational cost relative to every preregistered B0-B3 baseline while preserving quality within the frozen non-inferiority margin and full matched coverage.

This is not a product qualification claim.

## Pre-outcome decision for issue #17

Decision recorded 2026-11-27. Retire V5.1 product confirmatory execution for
`SWE_BENCH_VERIFIED` (revision `03e151cf5560b1af6a4363c6a9d766deaaea6b56`) and
`TERMINAL_BENCH_2_1` (revision `7131e4375048a0e408a8fb404b5f499d726b695b`).
SWE-bench resolution measures test outcomes. Terminal-Bench native reward
measures task performance. Neither source supplies an observation of consequence
severity or a counterfactual loss under a reference action. There is no
identified external catastrophic-regret estimand for these populations under V5.1.
[SWE-bench Verified scoring](https://openai.com/index/introducing-swe-bench-verified/#background-on-swe-bench)
· [Terminal-Bench 2.1 scope](https://github.com/harbor-framework/terminal-bench-2-1/blob/7131e4375048a0e408a8fb404b5f499d726b695b/README.md#L1-L5)

The existing mechanism V1 protocol is the replacement path for these
populations. It retains the fixed multiplicity allocation and quality margin
below. Final sizing depends on future calibration-only observations.
The product root builder and verifier reject both families under the retired
product authority schema. The [V5.1 product protocol](../artifacts/dgc-product-v1/PREREGISTRATION.md)
remains archived in place. Any renewed product claim requires a separate
preregistered generation with independently justified risk evidence and a new
authority contract.

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

The mechanism lane is now structurally risk-free end to end:

- `cwc/governance/mechanism_evidence_plan.py` — two-endpoint statistical claim;
- `cwc/governance/mechanism_execution_freeze.py` — exact 11-component execution freeze that rejects `risk_endpoint_manifest`;
- `cwc/governance/mechanism_learned_baseline.py` — B2 utility over quality and cost only;
- `cwc/governance/mechanism_b2_fit_receipt.py` and `mechanism_b2_fit_authority.py` — calibration-only B2 evidence with no risk field in the input schema;
- `cwc/governance/mechanism_harness_freeze.py` — B0-B3+DGC controlled-comparison frame without risk/CCF/product authority;
- `cwc/governance/mechanism_execution_authority.py` — bounded execution authority;
- `cwc/governance/frozen_mechanism_executor.py` and `mechanism_execution_bundle.py` — risk-field-rejecting execution/replay;
- `cwc/governance/mechanism_trial_sizing.py` — eight baseline×endpoint calibration comparisons.

The generic product execution freeze and product harness remain unchanged and continue to require an explicit frozen `catastrophic_regret` endpoint. Risk-free mechanism evidence cannot be substituted into product qualification.


## Frozen mechanism execution authority

The mechanism lane has a separate execution authority and evidence bundle. It does not reuse the product confirmatory root or product execution bundle.

Pre-outcome sequence:

`materialize → mechanism execution freeze (risk-free) → partition → mechanism B2 calibration/authority → mechanism sizing → mechanism harness freeze → mechanism authority → mechanism execution bundle → mechanism Pareto certificate`

After materialization and the risk-free execution freeze, create the partition
receipt with `scripts/dgc_freeze_task_partition.py --mechanism-execution-freeze`.
The partition binds the task manifest, materialization reference and partition
plan to the verified freeze before writing any task split.

The mechanism sizing receipt is bound to the SHA-256 of the canonical calibration evidence artifact. It freezes the maximum required within-task repeat count across the exact eight baseline×endpoint comparisons.

The mechanism execution authority binds:

- exact execution-freeze digest;
- exact final harness digest and comparison frame;
- exact confirmatory task IDs/digest;
- exact semantic B0-B3 + DGC policy mapping;
- exact two-endpoint mechanism plan;
- calibration-derived repeat count;
- frozen per-unit cost cap and full worst-case global budget.

The mechanism bundle contains only `quality` and certified total operational cost outcomes. Any `catastrophic_regret` or `risk_endpoint_*` field is invalid in this lane.

A complete mechanism bundle may feed `REAL_WORKLOAD_MECHANISM_SUPPORTED` only. It cannot authorize risk qualification, product promotion, client verification, commercial claims, or production control.

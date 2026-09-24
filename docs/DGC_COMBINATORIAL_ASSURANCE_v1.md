# DGC Combinatorial Assurance v1

Status: `COVERAGE_MEASUREMENT_IMPLEMENTED / COVERING_PLAN_NOT_YET_EXTERNAL`

## Purpose

Replace qualitative claims such as “many fault/shift tests were run” with an exact, hash-bound measure of the interactions covered by a frozen test population.

The design follows NIST combinatorial testing / input-space coverage principles: faults are often interaction-triggered, so statement/branch/mutation coverage alone does not measure whether relevant environmental and configuration combinations were exercised.

## Contract

A `FactorSchema` freezes named factors and allowed values. Every `CoverageCase` must assign every and only those factors. For strength `t`, the authority enumerates the exact unconstrained universe of all t-way factor/value interactions and measures the subset present in the test population.

Certificate fields include:

- schema digest;
- interaction strength `t`;
- case count;
- exact interaction-universe size;
- covered interactions;
- coverage fraction;
- number and digest of missing interactions;
- case-population digest;
- complete/not-complete flag.

Promotion policies may require a minimum fraction or complete t-way coverage. Unknown factor values, partial assignments and duplicate case IDs fail closed.

## Current targeted authority

Local targeted tests: `6/6 PASS`.

Adversarial gate: `4/4 attacks killed`.

A canonical example demonstrates why the metric matters: four cases can achieve complete pairwise coverage of three binary factors while covering only half of the 3-way interaction universe.

## Claim boundary

This measures **input-space interaction coverage**, not correctness. A passing test suite gives evidence only for combinations actually exercised under the declared oracle. The relevant factors/values, constraints, oracles and target interaction strength remain design obligations.

DGC will use this authority to quantify coverage across future fault, provider, drift, workload-domain, economics and deployment-regime factors. External G1-G5/generalization coverage is not yet claimed.

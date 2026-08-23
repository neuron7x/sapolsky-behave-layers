# DGC Product Claim v1

Status: `FROZEN_PRE_PRODUCT_CLAIM`
Date: 2026-08-22

## Primary claim

> On defined real agentic workloads, DGC reduces the total operational cost of reaching an accepted successful decision relative to the strongest preregistered baseline, without exceeding preregistered quality, catastrophic-regret, coverage, or safety degradation limits.

This claim is a verification target, not an established product claim.

## Primary product metric

`CPS = total operational cost / accepted successful outcomes`

A trial contributes to an accepted successful outcome only when the frozen scorer marks it accepted and all required quality/risk/coverage gates pass.

## Total-cost boundary

`C_total = C_model + C_router + C_countermodels + C_retrieval + C_tools + C_verification + C_human + C_infra + C_retry + C_failure_loss`

No component may be moved to an unmetered subsystem. Token savings alone are not inference savings.

## Frozen comparison panel

- `B0_FIXED_COMPUTE`
- `B1_UNCERTAINTY_ROUTER`
- `B2_LEARNED_COST_QUALITY_ROUTER`
- `B3_SEQUENTIAL_VERIFICATION`
- `B4_DGC`

The product comparison is against the best preregistered admissible baseline, not a post-hoc selected weak baseline.

## Frozen decision gates

Product evidence requires all of:

1. identical task population / scorer / model pool / tools / budget envelope across compared policies;
2. quality non-inferiority against the best preregistered baseline under a preregistered margin;
3. catastrophic-regret non-inferiority;
4. equal task coverage or explicit preregistered abstention accounting;
5. total-cost superiority after all DGC overhead is included;
6. statistically valid uncertainty bounds under the declared sampling regime;
7. external real-workload evidence before any product promotion;
8. independent replication before `PRODUCT_QUALIFIED`.

## Commercial target

`NetSaving >= 30%` is a commercial verification target only.

It is not a mathematical constant and is not required for scientific support. A smaller reproducible positive net saving may still support the scientific mechanism.

## Prohibited extrapolations

Until their dedicated gates pass, do not claim:

- guaranteed 30% savings;
- universal compute savings;
- frontier superiority;
- production readiness;
- safety guarantee;
- client-verified savings;
- ARR or ROI from hypothetical customers;
- general superiority over routing/adaptive compute;
- novelty of value-of-computation or metareasoning itself.

## Current authority

Current status remains `RESEARCH_ARCHITECTURE_WITH_NARROW_VERIFIED_COMPONENTS`.

Promotion chain:

`RESEARCH_HYPOTHESIS -> EXPERIMENTALLY_SUPPORTED -> REAL_WORKLOAD_SUPPORTED -> INDEPENDENTLY_REPLICATED -> PRODUCT_QUALIFIED`

No status may be skipped.

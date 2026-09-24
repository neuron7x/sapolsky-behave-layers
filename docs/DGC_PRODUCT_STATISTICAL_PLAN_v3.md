# DGC Product Statistical Plan v3

Status: `FROZEN_PRE_EXECUTION_STATISTICAL_PLAN_V3`
Protocol generation: `DGC_PRODUCT_PAIRED_CLUSTER_AWARE_V3_WITH_G1_HOLDOUT`
External confirmatory outcomes observed before this generation: **false**.

This generation supersedes v1/v2 for future product-evidence execution. Earlier files remain historical records and are not silently rewritten.

## 1. Frozen workload and policy panel

Primary product evidence requires both frozen external workload families and exact comparison against all four baselines:

- B0 Fixed Compute;
- B1 Uncertainty/Entropy Router;
- B2 Learned Cost/Quality Router;
- B3 Sequential Verification.

The five-arm execution population is `B0/B1/B2/B3/DGC`. No strongest-baseline selection is permitted after outcomes.

## 2. Three disjoint task populations

For every primary workload family, deterministic `DGC-SPLIT-V3` creates:

- calibration: `20%`;
- primary confirmatory: `60%`;
- G1 unseen-task holdout: `20%`.

All three populations are non-empty, disjoint and exhaustive. The verifier reconstructs the split from the full task union and frozen fractions.

B2 may use only calibration tasks. Both primary-confirmatory and G1 tasks are forbidden during B2 fitting.

## 3. Endpoints and signs

For every family × baseline × paired `(task, replicate)` observation:

1. `C = baseline_total_operational_cost - DGC_total_operational_cost`;
2. `Q = DGC_quality - baseline_quality`;
3. `R = baseline_catastrophic_regret - DGC_catastrophic_regret`.

Positive values favor DGC for all three definitions.

Physical cost uses the full ten-component operational boundary, not a token-meter proxy.

## 4. Frozen margins and error allocation

Global primary familywise alpha: `0.05`.

Primary multiplicity family:

`2 workload families × 4 baselines × 3 endpoints = 24 claims`.

Therefore

`delta_primary = 0.05 / 24 = 0.0020833333333333333`.

Frozen non-inferiority margins:

- quality: `0.02`;
- catastrophic regret: `0.01`.

Minimum cost effect of interest for **planning only**: `0.05` normalized total-cost effect.

Scientific primary cost threshold remains lower confidence bound `> 0`. The `0.05` planning effect is not silently substituted for that threshold.

The commercial `>=30%` net-saving target remains separate from the scientific P9 gate.

## 5. Exact finite-panel statement

For the complete frozen confirmatory `task × replicate` panel and each B0-B3 baseline, compute exact means of `C`, `Q`, `R`.

Exact panel success requires:

- `mean(C) > 0`;
- `mean(Q) >= -0.02`;
- `mean(R) >= -0.01`;
- full paired coverage.

This is an unconditional arithmetic statement about the executed panel. It is not statistical generalization.

Authority: `EXACT_FROZEN_FINITE_PANEL_PARETO_V1`.

## 6. Primary bounded inference

Primary inferential support uses the complete paired `(task, replicate)` population without first averaging replicates away.

For each baseline/endpoint, use the one-sided empirical-Bernstein lower bound corresponding to Maurer & Pontil (2009), Theorem 11:

`LB = mean - sqrt(2 V_n log(2/delta)/n) - 7 L log(2/delta)/(3(n-1))`,

with sample variance `V_n`, support range `L`, and `delta = 0.05/24`.

Scientific lower-bound success requires:

- cost `LB > 0`;
- quality `LB >= -0.02`;
- catastrophic regret `LB >= -0.01`;
- every B0-B3 baseline passes.

The theorem is invoked conditionally on the preregistered cross-pair independence assumption. Identical distributions are not required. Dependence within each paired baseline-vs-DGC observation is permitted.

## 7. Randomness protocol and assumption boundary

Pairing protocol: `DGC_PAIRED_COMMON_RANDOM_NUMBERS_V1`.

For a frozen generation root, task and replicate, the seed is deterministic and shared across policies in the pair. Provider request IDs must be unique across work units.

The system verifies the schedule and request identities. It does not claim that these facts alone prove provider-internal stochastic independence.

Therefore the confidence statement is explicitly conditional on

`CROSS_TASK_REPLICATE_PROVIDER_REQUESTS_CONDITIONALLY_INDEPENDENT`.

Exact finite-panel facts do not depend on this assumption.

## 8. Planning and repetition count

Cluster-aware variance decomposition remains a conservative planning diagnostic:

`Var(mean) = sigma_between²/N_tasks + sigma_within²/(N_tasks × R)`.

It is not the final primary inference theorem.

A separate empirical-Bernstein planning proxy may choose the smallest `R` satisfying

`sqrt(2 v log(2/delta)/(N_tasks R)) + 7 L log(2/delta)/(3(N_tasks R - 1)) <= target_width`,

for calibration-derived variance proxy `v`.

Both calculations are planning-only. Final promotion recomputes the confidence bound using observed confirmatory variance.

Frozen repetition constraints remain:

- minimum `R = 5`;
- maximum `R = 50`.

If the frozen resource cap cannot meet the planning criterion, the generation is underpowered and must not weaken its evidence standard post hoc.

## 9. CCF preregistration

Counterfactual-oracle quantization, cost/value/latency/risk units and resource budgets are frozen before B2/confirmatory outcomes. CCF headroom is a required diagnostic audit; no post-hoc headroom threshold is invented.

## 10. G1-G5 preregistration and multiplicity

Before B2 outcomes, freeze exact manifests for:

- G1 unseen tasks;
- G2 unseen domain;
- G3 unseen model/provider;
- G4 changed economics/pricing;
- G5 perturbation shift.

No policy retuning is allowed.

A separate G1-G5 familywise alpha of `0.05` is allocated over

`5 axes × 4 baselines × 3 endpoints = 60 claims`,

so

`delta_G = 0.05/60 = 1/1200 = 0.0008333333333333334`.

Each axis uses the same exact+bounded-inference conjunction as primary P9.

## 11. Scientific promotion gates

`P9_SUPPORTED` requires:

- complete external confirmatory execution;
- complete physical-cost accounting;
- exact finite-panel success against B0-B3;
- empirical-Bernstein lower-bound success against B0-B3 under the frozen assumption;
- exact multiplicity allocation;
- complete CCF audit;
- raw-subject replay and digest lineage equality.

`GENERALIZATION_SUPPORTED` requires exact + bounded-inference success on every preregistered G1-G5 axis.

Neither status implies universal superiority.

## 12. Downstream boundary

After primary and G1-G5 support, a fresh externally attributable independent-replication/review subject is still required. Then P19 sealing, evidence-bundle completeness and operational qualification remain separate gates.

`PRODUCT_QUALIFIED=false` until those gates are actually satisfied.

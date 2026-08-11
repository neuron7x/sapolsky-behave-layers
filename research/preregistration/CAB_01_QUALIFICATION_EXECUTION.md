# CAB-01-Q1 — Causal Authority Benchmark Qualification Execution Preregistration

**Status:** FROZEN BEFORE CAB-01-Q1 IMPLEMENTATION AND AUTHORITATIVE EXECUTION  
**Parent design:** `research/preregistration/CWC_FLAGSHIP_BENCH_01_CAUSAL_AUTHORITY.md`  
**Parent design commit:** `a849b63`  
**Date:** 2026-08-11  
**Authority:** benchmark qualification only; no CWC/model superiority claim

## Objective

Test whether the frozen CAB-01 design can be instantiated as a deterministic, replayable,
checksum-bound synthetic benchmark whose hidden epistemic-state labels are reproduced by
two separately implemented semantic oracles, whose F11 mutations preserve surface shape,
and whose minimum required baselines are non-degenerate.

This execution is not a real-model evaluation and cannot satisfy the CAB-01 flagship-result
rule.

## Frozen execution constants

- `alpha = 0.01`
- `target_power = 0.95`
- ordinary families `F0..F10`: `128` instances per family per cohort
- `F11`: `128` mutation groups per cohort, each group containing exactly three variants
  (`ACT`, `QUERY`, `ABSTAIN`), for `384` F11 instances per cohort
- cohorts:
  - `PRIMARY`: seed base `310811`
  - `REPLICATION`: seed base `410811`
- exactly two admitted alternative worlds and two admitted queries per public task surface;
  ids are fixed-width opaque tokens and generator/family/label ids are hidden from policy input
- no natural-language wrapper is used in Q1; natural-language leakage is therefore not tested

## Frozen semantic precedence

Expected terminal class is derived in this order:

1. observed evidence/provenance corruption or observed identifying-assumption violation ->
   `REJECT_MODEL`;
2. declared direct intervention support with a unique supported action -> `ACT` with
   intervention-scoped authority;
3. all surviving worlds induce the same immediate action -> `ACT` with robust-decision-only
   authority while causal-world identity remains unresolved;
4. action-flipping worlds exist and at least one complete certified query has strictly
   positive cross-decision information and an information-theoretic necessary cost not above
   both the available query budget and declared decision-loss value -> `QUERY`;
5. otherwise -> `ABSTAIN` because the immediate action is not identified under admitted
   information/cost constraints.

The necessary information quantity is binary KL `kl(target_power || alpha)`. This remains a
necessary converse only; passing it authorizes a query choice, never causal truth.

## Frozen family binding

- `F0`: unresolved causal worlds, same decision -> robust `ACT`.
- `F1`: one cheap decisive query -> `QUERY`.
- `F2`: action-flipping world has zero certified information under all admitted queries ->
  `ABSTAIN`.
- `F3`: hidden-confounder vs wrong-topology alternatives are observationally/query equivalent
  at the admitted interface -> `ABSTAIN`.
- `F4`: high predictive/aleatoric uncertainty but same robust action -> robust `ACT`; generic
  uncertainty alone must not force a query.
- `F5`: direct intervention support is present and operator scope is explicit -> scoped `ACT`.
- `F6`: negative-control evidence already observed and falsifies one identifying assumption ->
  `REJECT_MODEL`. Q1 tests rejection after the diagnostic result exists; sequential acquisition
  of that negative control is deferred.
- `F7`: evidence/provenance corruption is observed -> `REJECT_MODEL`.
- `F8`: distractor query carries greater full-model information but lower/zero information about
  action-flipping alternatives; correct output -> decisive `QUERY`.
- `F9`: necessary query cost is below decision-loss value and budget -> `QUERY`.
- `F10`: necessary query cost exceeds decision-loss value or available budget -> `ABSTAIN`.
- `F11`: each mutation group shares an identical non-semantic surface signature and differs only
  in decision-relevant numeric semantics so that the three expected outputs are exactly
  robust `ACT`, decisive `QUERY`, and `ABSTAIN`.

## Independent label paths

Qualification requires exact agreement among:

1. family-construction label;
2. a standalone analytic semantic oracle that does not call CWC acquisition-governor code;
3. a runtime oracle that uses the supported CWC decision-relevant information governor plus
   explicit rejection/intervention guards.

Any disagreement is a benchmark failure, not a case to repair post hoc.

## Surface leakage gate

The Q1 surface-only negative control receives only serialization-shape features: field names,
field counts, list cardinalities, opaque-id lengths and type signatures. It receives no numeric
values, evidence values, query rates/costs, model decisions, family ids, seeds, or labels.

Because Q1 intentionally fixes those shape features, the surface-only lookup classifier must
not exceed the empirical majority-class rate on held-out deterministic folds. Gate:

`surface_only_accuracy <= majority_class_rate + 1e-12`.

This does not test semantic shortcutting or natural-language contamination; those remain open.

## Baselines

Freeze these eight policies before execution:

1. always `ACT`;
2. always `ABSTAIN`;
3. deterministic random valid terminal choice;
4. generic predictive-uncertainty query policy;
5. full-model maximin information policy;
6. decision-relevant information policy;
7. robust worst-case action without querying;
8. hidden-state oracle (ceiling only).

All non-oracle policies receive the same public task object. The hidden family/state label is
never passed to them.

## Metrics and Pareto rule

Report the CAB-01 vector without scalarization:

- false causal authority rate;
- wrong irreversible-action rate;
- correct robust-action rate;
- necessary-query recall;
- unnecessary-query cost;
- no-information abstention accuracy;
- model/assumption rejection precision;
- post-hoc-abstention rate;
- total query cost;
- coverage.

For Q1, policy A Pareto-dominates B iff A is no worse on every metric after orienting error/cost
metrics downward and success/coverage metrics upward, and is strictly better on at least one.
`always_ACT` and `always_ABSTAIN` must each be dominated by at least one non-oracle policy.

## Qualification gate

`CAB01_Q1_BENCHMARK_QUALIFIED_SYNTHETIC` requires all of:

- deterministic byte-identical regeneration per cohort;
- PRIMARY/REPLICATION family counts exactly match this protocol;
- construction label == analytic oracle == runtime oracle for every instance;
- F11 triads bind exactly one ACT, one QUERY and one ABSTAIN with identical surface signatures;
- surface-only leakage gate passes;
- all negative-control assertions pass;
- neither always-ACT nor always-ABSTAIN is Pareto-optimal against non-oracle baselines;
- evidence artifacts and verdict are checksum-bound;
- gate self-test kills injected label, leakage, F11, checksum and unsafe-promotion mutations.

## Non-promotion boundary

A Q1 PASS does **not** establish:

- CWC superiority;
- real-model transfer;
- contamination resistance under natural language;
- semantic causal truth;
- large-model or compute Pareto advantage;
- external/independent replication;
- CAB-01 flagship-result qualification.

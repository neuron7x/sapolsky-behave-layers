# CWC-VIA-02 — First-Principles Execution Report

**Execution branch:** `agent/cwc-via-v1b-first-principles`
**Scientific frontier after execution:** `VIA-V1`
**Ascension status:** blocked; no VIA-V2 authorization

## 1. Problem decomposition corrected

The VIA programme now separates **latent/per-instance action opportunity** from **controller-state
observability**. The required ordering is encoded and tested:

```
best fixed <= regime oracle <= instance oracle
```

This preserves WP18/WP19 exactly within their registered bucket-conditioned scope while preventing a
negative result for one context proxy from being silently promoted to “no latent opportunity”.
Observable-state search remains a VIA-V2 problem and is still blocked.

## 2. New first-principles machinery

Implemented `cwc/causal/opportunity.py` with:

- exhaustive quality/compute replay validation;
- instance-oracle and regime-oracle values;
- Lagrangian utility `quality - lambda * compute`;
- exact pairwise action-ranking critical lambdas;
- interval-representative evaluation without arbitrary grid search;
- controller-compute break-even allowance;
- fail-closed opportunity-capture ratio.

## 3. Candidate mechanism selected and preregistered

The candidate compute axis is **adaptive attention horizon**, scientifically distinct from the prior
weight-tied iteration and untied-depth axes. The controlled qualification protocol was committed
before execution as commit `851c0991d8248808d6157c0413d539389d591576`.

The qualification uses exact enumeration of all 8-bit prefixes under two dependency regimes:

- local dependency: both H=2 and H=8 contain the necessary information;
- long dependency: only H=8 contains the first-bit dependency.

The resource unit is explicitly a controlled visible-symbol proxy, not FLOPs, latency, or energy.

## 4. Controlled qualification result

Verdict:

```
ATTENTION_HORIZON_MECHANISM_QUALIFIED_CONTROL_ONLY
```

Observed exact surface:

| regime | short quality / compute | full quality / compute |
|---|---:|---:|
| local | 1.0 / 2 | 1.0 / 8 |
| long | 0.5 / 2 | 1.0 / 8 |

Computed from the exact finite-action opportunity geometry:

- critical lambdas: `1/24`, `1/12`, `1/6`;
- maximum regime-oracle gap across evaluated ranking regions: `0.125`;
- maximum instance-oracle gap: `0.1875`;
- maximum controlled controller-compute allowance: `3.0` visible-symbol proxy units;
- action-ranking reversal across regimes: PASS;
- information-ordering invariant: PASS.

This is **not** a trained-model or real-workload result and cannot pass VIA-V1.

## 5. Frozen evidence sufficiency audit

A structural audit was executed against existing WP18/WP19 raw artifacts.

WP18:

- 24 raw-run files;
- 120 shard records;
- stored granularity: difficulty-bucket × action means;
- paired per-independent-unit action outcomes: absent.

WP19:

- 18 raw-run files;
- 90 shard records;
- stored granularity: difficulty-bucket mean per separately trained depth;
- paired per-independent-unit action outcomes: absent.

Verdict:

```
VIA_V1_INSTANCE_OPPORTUNITY_UNIDENTIFIED_FROM_FROZEN_REAL_EVIDENCE
```

This does not weaken the registered WP18/WP19 claims. It means only that their sealed aggregation
level cannot answer the newly separated `G_instance` estimand. The correct value is `UNKNOWN`, not
zero and not positive.

Future VIA-V1 evidence is now required to preserve before aggregation:

```
independent_unit_id
immutable_unit_payload_hash
cluster_id
action_id
raw_quality
raw_compute
action_execution_identity
same-unit outcomes for all actions
```

## 6. Verification

Executed after evidence sealing:

- `tests/via`: **26 passed**;
- targeted existing assurance/theory regression suite: **116 passed**;
- total explicitly passed in this execution: **142 tests**.

Programme gates:

- VIA gate: PASS;
- architecture gate: PASS;
- hermeticity gate: PASS;
- complexity gate: PASS;
- inference-integrity gate: PASS;
- verdict-binding gate: PASS (`41` claims bound; `2` NOT_TESTED unbound by design).

Full-suite collection remains environment-blocked by missing optional/runtime dependencies:
`rustbpe`, `tomli`, `hypothesis`, and `pyarrow`. Collection reached 274 tests before 7 import errors.
No full-suite PASS is claimed.

## 7. Scientific decision

The programme does **not** ascend to VIA-V2.

The next admissible scientific experiment is a new prospectively frozen VIA-V1 attention-horizon
pilot that records same-unit outcomes under all horizon actions before aggregation and measures raw
quality and real execution cost separately. Only a positive, preregistered real-workload opportunity
certificate may reopen the observability stage.
